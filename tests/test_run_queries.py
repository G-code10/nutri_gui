"""Tests de src/storage/run_queries.py : lecture du SQL, contrôles sur le Parquet, comparaison avec la base de TEST.

Les tests avec base lisent TEST_DATABASE_URL (jamais la vraie base) et sont ignorés sans elle.
"""

import os
from pathlib import Path

import pandas as pd
import psycopg
import pytest

from src import cleaning, create_db, load_db
from src.storage import convert_parquet
from src.storage import run_queries as rq

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL absente (base PostgreSQL de test)")


def raw_product(code, **changes):
    """Un produit brut valide, avec toutes les colonnes d'extract.py ; `changes` écrase des colonnes."""
    row = {
        "code": code, "product_name": "Produit " + code, "brands": "Marque", "categories_tags": ["en:snacks"],
        "main_category": "en:snacks", "food_groups_tag_1": "en:sugary-snacks", "allergens": "",
        "ingredients_text": "sucre", "additives_n": 1, "nova_group": 4, "nutriscore_score": 12,
        "nutriscore_grade": "d", "serving_size": "30 g", "completeness": 0.5,
        "created_t": 1600000000, "last_modified_t": 1700000000,
        "energy_kcal_100g": 450.0, "energy_kj_100g": 1883.0, "fat_100g": 20.0, "saturated_fat_100g": 8.0,
        "carbohydrates_100g": 60.0, "sugars_100g": 25.0, "fiber_100g": 3.0, "proteins_100g": 6.0,
        "salt_100g": 0.5, "sodium_100g": 0.2, "fruits_vegetables_legumes_100g": 0.0,
    }
    return {**row, **changes}


@pytest.fixture(scope="module")
def clean_df():
    """Six produits nettoyés : trois rayons dont unknown, les grades a, d, e, not-applicable et unknown (-> null),
    un couple nom + marque répété, des sucres au-dessus des glucides mais dans la tolérance."""
    raw = pd.DataFrame([
        raw_product("0012345", product_name="Biscuit"),
        raw_product("2000002", product_name="Biscuit", nutriscore_grade="e"),
        raw_product("3000003", food_groups_tag_1="en:beverages", nutriscore_grade="a",
                    carbohydrates_100g=10.0, sugars_100g=10.3),
        raw_product("4000004", food_groups_tag_1=None, nutriscore_grade="not-applicable"),
        raw_product("5000005", food_groups_tag_1="en:beverages", nutriscore_grade="unknown"),
        raw_product("6000006", nutriscore_grade="b"),
    ])
    res, _ = cleaning.clean(raw)
    assert len(res) == 6
    return res


@pytest.fixture(scope="module")
def parquet_dir(clean_df, tmp_path_factory):
    """Dossier partitionné produit par convert_parquet à partir du nettoyé."""
    folder = tmp_path_factory.mktemp("parquet")
    source = folder / "products_clean.parquet"
    clean_df.to_parquet(source, index=False)
    output = folder / "produits"
    convert_parquet.convert(source, output)
    return output


@pytest.fixture(scope="module")
def parquet_run(parquet_dir):
    """Les cinq contrôles exécutés en DuckDB sur le Parquet."""
    return rq.run_parquet(parquet_dir, rq.load_queries())


def _rows_as_dict(result, key, value):
    """{valeur de la colonne key: valeur de la colonne value} pour un résultat de requête."""
    return dict(zip(rq._column(result, key), rq._column(result, value)))


# --- Lecture du fichier SQL ---
def test_load_queries_reads_the_five_named_queries_in_order():
    assert list(rq.load_queries()) == list(rq.TITLES)


def test_load_queries_replaces_every_parameter_with_cleaning_constants():
    queries = rq.load_queries()
    assert not any("$" in query for query in queries.values())
    assert f"+ {cleaning.SUGARS_TOLERANCE:g}" in queries["bornes_coherences"]


def test_load_queries_refuses_sql_before_the_first_marker(tmp_path):
    path = tmp_path / "bad.sql"
    path.write_text("SELECT 1;\n-- @nom: a\nSELECT 2;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="premier marqueur"):
        rq.load_queries(path)


def test_load_queries_refuses_duplicate_name_and_unknown_parameter(tmp_path):
    path = tmp_path / "bad.sql"
    path.write_text("-- @nom: a\nSELECT 1;\n-- @nom: a\nSELECT 2;\n", encoding="utf-8")
    with pytest.raises(ValueError, match="double"):
        rq.load_queries(path)
    path.write_text("-- @nom: a\nSELECT $inconnu;\n", encoding="utf-8")
    with pytest.raises(KeyError):
        rq.load_queries(path)


# --- Contrôles sur le Parquet ---
def test_every_query_runs_on_the_parquet(parquet_run):
    assert parquet_run.total == 6
    assert set(parquet_run.results) == set(rq.TITLES)
    assert all(result.rows for result in parquet_run.results.values())


def test_count_by_aisle_totals_the_dataset_with_one_row_per_aisle(parquet_run):
    counts = _rows_as_dict(parquet_run.results["comptage_par_rayon"], "rayon", "produits")
    assert counts == {"en-sugary-snacks": 3, "en-beverages": 2, "unknown": 1}
    assert sum(counts.values()) == parquet_run.total


def test_no_duplicate_code_and_repeated_name_brand_pairs_reported(parquet_run):
    duplicates = _rows_as_dict(parquet_run.results["doublons"], "controle", "groupes")
    assert duplicates["codes en double"] == 0
    assert duplicates["couples nom + marque répétés"] == 1   # Biscuit / Marque, deux fois


def test_bounds_are_zero_and_tolerance_is_applied(parquet_run):
    counts = _rows_as_dict(parquet_run.results["bornes_coherences"], "ordre", "produits")
    assert all(count == 0 for count in counts.values())   # sucres 10,3 > glucides 10 : dans la tolérance de 0,5


def test_grade_distribution_keeps_not_applicable_and_counts_unknown_as_null(parquet_run):
    grades = _rows_as_dict(parquet_run.results["distribution_nutriscore"], "grade", "produits")
    assert grades == {"a": 1, "b": 1, "d": 1, "e": 1, "not-applicable": 1, "null": 1}


def test_checks_pass_except_missing_grade_c(parquet_run):
    results = dict(rq.checks(parquet_run))
    assert results["0 code en double"] and results["0 valeur hors bornes"]
    assert not results["les cinq grades a-e sont présents"]   # pas de grade c dans ce petit jeu


def test_run_parquet_refuses_an_incomplete_folder(parquet_dir, tmp_path):
    with pytest.raises(FileNotFoundError, match="convert_parquet"):
        rq.run_parquet(tmp_path / "vide", rq.load_queries())


# --- Comparaison et rapport ---
def test_compare_detects_a_different_value(parquet_run):
    other = rq.ControlRun("autre", parquet_run.total, dict(parquet_run.results))
    result = parquet_run.results["comptage_par_rayon"]
    other.results["comptage_par_rayon"] = rq.QueryResult(result.columns, [result.rows[0][:1] + (999,) + result.rows[0][2:]])
    same = rq.compare(parquet_run, other)
    assert same["comptage_par_rayon"] is False
    assert same["doublons"] is True


def test_markdown_has_five_tables_license_and_is_reproducible(parquet_run):
    first = rq.build_markdown(parquet_run, "data/parquet/produits", date="2026-01-01")
    second = rq.build_markdown(parquet_run, "data/parquet/produits", date="2026-01-01")
    assert first == second
    assert "ODbL" in first and "- Date : 2026-01-01" in first
    for title in rq.TITLES.values():
        assert f"## {title}" in first
    assert "Base non interrogée" in first


def test_main_without_database_writes_the_report(parquet_dir, tmp_path):
    output = tmp_path / "docs" / "controle.md"
    rq.main(["--parquet", str(parquet_dir), "--out", str(output), "--no-db"])
    assert "## 1. Comptage par rayon" in output.read_text(encoding="utf-8")


# --- Avec la base de test ---
@pytest.fixture
def conn(clean_df):
    """Base de test rechargée avec le même nettoyé que le Parquet."""
    connection = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    create_db.create_schema(connection)
    load_db.load(clean_df, connection)
    yield connection
    connection.close()


@needs_db
def test_database_and_parquet_give_the_same_results(conn, parquet_run):
    database = rq.run_postgres(conn, rq.load_queries())
    same = rq.compare(parquet_run, database)
    assert all(same.values()), same


@needs_db
def test_a_missing_product_in_the_database_is_detected(conn, parquet_run):
    conn.execute("DELETE FROM products WHERE code = '6000006'")
    database = rq.run_postgres(conn, rq.load_queries())
    same = rq.compare(parquet_run, database)
    assert not same["volumétrie"] and not same["comptage_par_rayon"]
    text = rq.build_markdown(parquet_run, "x", database, date="2026-01-01")
    assert "**différents**" in text and "Résultat de la base, différent" in text


@needs_db
def test_run_writes_the_comparison(conn, parquet_dir, tmp_path):
    params = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    conf = {**params, "database": params.pop("dbname")}
    summary = rq.run(parquet_dir, output=tmp_path / "controle.md", conf=conf)
    assert all(summary["identical"].values())
    assert "résultats identiques" in Path(summary["output"]).read_text(encoding="utf-8")