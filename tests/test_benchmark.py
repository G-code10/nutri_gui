"""Tests de src/storage/benchmark.py : mêmes résultats entre moteurs, mesure en sous-processus, rapport.

Données : un petit nettoyé fabriqué (trois marques d'au moins 20 produits, trois rayons dont unknown).
Les tests avec base lisent TEST_DATABASE_URL (jamais la vraie base) et sont ignorés sans elle.
"""

import json
import os
import subprocess
import sys

import pandas as pd
import psycopg
import pytest

from src import cleaning, config, create_db, load_db, utils
from src.storage import benchmark as bm
from src.storage import convert_parquet

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL absente (base PostgreSQL de test)")
LOCAL_ENGINES = ["pandas", "duckdb", "duckdb_flat"]


def raw_product(index: int) -> dict:
    """Produit brut n° index : marques A (40), B (30), C (25), D (5) ; rayons boissons, snacks sucrés, inconnu."""
    brand = "A" if index < 40 else "B" if index < 70 else "C" if index < 95 else "D"
    aisle = [bm.BEVERAGES_TAG, "en:sugary-snacks", None][index % 3]
    return {
        "code": f"{index:013d}", "product_name": f"Produit {index}", "brands": f"Marque {brand}",
        "categories_tags": ["en:snacks"], "main_category": "en:snacks", "food_groups_tag_1": aisle,
        "allergens": "", "ingredients_text": "sucre", "additives_n": 1, "nova_group": 4, "nutriscore_score": 5,
        "nutriscore_grade": "abcde"[index % 5] if index % 4 else "unknown", "serving_size": "30 g",
        "completeness": 0.5, "created_t": 1600000000, "last_modified_t": 1700000000,
        "energy_kcal_100g": 4 * 60.0 + 4 * 6.0 + 9 * 20.0, "energy_kj_100g": (4 * 60.0 + 4 * 6.0 + 9 * 20.0) * 4.184,
        "fat_100g": 20.0, "saturated_fat_100g": 8.0, "carbohydrates_100g": 60.0,
        "sugars_100g": None if index % 7 == 0 else round(10 + index * 0.37 % 50, 2),
        "fiber_100g": 3.0, "proteins_100g": 6.0, "salt_100g": round(index % 11 * 0.1, 1),
        "sodium_100g": round(index % 11 * 0.1, 1) / 2.5, "fruits_vegetables_legumes_100g": 0.0,
    }


@pytest.fixture(scope="module")
def clean_df():
    res, _ = cleaning.clean(pd.DataFrame([raw_product(index) for index in range(100)]))
    assert len(res) == 100
    return res


@pytest.fixture(scope="module")
def supports(clean_df, tmp_path_factory):
    """(Parquet nettoyé, Parquet partitionné) construits à partir du même nettoyé."""
    folder = tmp_path_factory.mktemp("benchmark")
    clean_path = folder / "products_clean.parquet"
    clean_df.to_parquet(clean_path, index=False)
    parquet_dir = folder / "produits"
    convert_parquet.convert(clean_path, parquet_dir, durations_path=folder / "durees.jsonl")
    return clean_path, parquet_dir


# --- Mêmes résultats d'un moteur à l'autre ---
@pytest.mark.parametrize("query", list(bm.QUERIES))
def test_local_engines_return_the_same_rows(supports, query):
    measures = [bm.measure(engine, query, *supports) for engine in LOCAL_ENGINES]
    assert measures[0]["rows"] > 0
    assert all(bm.same_result(measures[0], other) for other in measures[1:])


def test_profile_excludes_unknown_and_is_sorted(supports, clean_df):
    rows = bm.run_query("duckdb", "profil_rayon", *supports)
    labels = [row[0] for row in rows]
    assert labels == sorted(labels) and config.UNKNOWN_AISLE not in labels
    assert sum(row[1] for row in rows) == clean_df["food_groups_tag_1"].notna().sum()   # sans rayon : exclus


def test_beverages_are_the_most_sugared_first(supports):
    rows = bm.run_query("pandas", "boissons_sucrees", *supports)
    sugars = [row[2] for row in rows]
    assert len(rows) == bm.TOP and sugars == sorted(sugars, reverse=True)


def test_brands_below_the_threshold_are_left_out(supports):
    rows = bm.run_query("duckdb_flat", "completude_marques", *supports)
    assert [row[0] for row in rows] == ["Marque A", "Marque B", "Marque C"]   # D : 5 produits seulement
    assert all(row[1] >= bm.MIN_PRODUCTS_PER_BRAND for row in rows)


# --- Mesure ---
def test_peak_memory_is_measured():
    assert bm.peak_memory_bytes() > 0


def test_module_import_loads_no_engine_library():
    """Importer le module ne charge ni pandas, ni DuckDB, ni psycopg : chaque mesure ne paie que son moteur."""
    code = "import sys, src.storage.benchmark; print(sorted({'pandas', 'duckdb', 'psycopg'} & set(sys.modules)))"
    output = subprocess.run([sys.executable, "-c", code], cwd=config.ROOT, capture_output=True, text=True, check=True)
    assert output.stdout.strip() == "[]"


def test_spawn_returns_a_measure_from_a_fresh_process(supports):
    result = bm.spawn("duckdb", "boissons_sucrees", *supports)
    assert result["rows"] == bm.TOP and result["seconds"] > 0 and result["peak_bytes"] > 0
    json.dumps(result)   # transmissible tel quel


def test_baseline_measures_imports_only(supports):
    result = bm.measure("duckdb", bm.BASELINE, *supports)
    assert result["rows"] == 0 and result["first"] is None


def test_verify_stops_on_a_different_result():
    same = {"rows": 2, "first": ["a", 1.0]}
    different = {"rows": 2, "first": ["a", 1.5]}
    bm.verify({"q": {bm.REFERENCE_ENGINE: same, "pandas": dict(same)}})
    with pytest.raises(RuntimeError, match="Résultats différents"):
        bm.verify({"q": {bm.REFERENCE_ENGINE: same, "pandas": different}})


def test_summarize_takes_median_time_and_maximum_peak():
    measures = [{"seconds": s, "peak_bytes": p, "rows": 3} for s, p in [(3.0, 10), (1.0, 30), (2.0, 20)]]
    assert bm.summarize(measures) == {"seconds": 2.0, "peak_bytes": 30, "rows": 3, "repeat": 3}


# --- Coût de construction (journal des durées) ---
def test_build_costs_use_the_latest_entry_and_show_missing_steps(tmp_path):
    log = tmp_path / "durees.jsonl"
    utils.append_duration(config.STEP_CONVERT, 9.0, 10, "ancien.parquet", log)
    utils.append_duration(config.STEP_CONVERT, 2.0, 10, "data/clean/products_clean.parquet", log)
    costs = {cost["support"]: cost for cost in bm.build_costs(bm.read_durations(log))}
    converted = costs[bm.PARTITIONED_SUPPORT]
    assert converted["seconds"] == 2.0 and converted["sources"] == ["data/clean/products_clean.parquet"]
    assert costs[bm.DATABASE_SUPPORT]["seconds"] is None
    assert costs[bm.DATABASE_SUPPORT]["missing"] == [config.STEP_DB_SCHEMA, config.STEP_DB_LOAD]


def test_read_durations_without_log_is_empty(tmp_path):
    assert bm.read_durations(tmp_path / "absent.jsonl") == []


# --- Rapport ---
def test_run_without_database_writes_the_report(supports, tmp_path):
    output = tmp_path / "benchmark_mesures.md"
    context = bm.run(*supports, output=output, use_db=False, repeat=1, engines=["duckdb"],
                     durations_path=tmp_path / "absent.jsonl")
    text = output.read_text(encoding="utf-8")
    for title in ("## Ce que mesure ce rapport", "## Les requêtes", "## Résultats", "### 1. ",
                  "## Coût de construction des supports", "## Référence : imports seulement",
                  "## Vérification avant chronomètre", "## Méthode", "## Machine et versions"):
        assert title in text
    assert "Dont requête (Mo)" in text and "Temps médian (ms)" in text
    assert "ODbL" in text and "non mesuré" in text
    assert set(context["results"]) == set(bm.QUERIES)


# --- Avec la base de test ---
@needs_db
@pytest.mark.parametrize("query", list(bm.QUERIES))
def test_postgres_returns_the_same_rows_as_duckdb(supports, clean_df, query, monkeypatch):
    with psycopg.connect(TEST_DATABASE_URL, autocommit=True) as conn:
        create_db.create_schema(conn)
        load_db.load(clean_df, conn)
    params = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    monkeypatch.setenv(bm.DB_ENV, json.dumps(load_db.connection_params({**params, "database": params.pop("dbname")})))
    assert bm.same_result(bm.measure("duckdb", query, *supports), bm.measure("postgres", query, *supports))