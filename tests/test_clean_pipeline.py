"""Tests de src/clean_pipeline.py : sans base (rapport, nettoyé écrit et volumes), puis avec une base PostgreSQL de TEST (TEST_DATABASE_URL)."""

import json
import os

import duckdb
import pandas as pd
import pytest
from psycopg.conninfo import conninfo_to_dict

from src import clean_pipeline, config
from src.storage import convert_parquet

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL absente (base PostgreSQL de test)")


def raw_product(code, **changes):
    """Un produit brut valide ; `changes` écrase des colonnes."""
    row = {
        "code": code, "product_name": "Biscuit", "brands": "Marque", "ingredients_text": "sucre",
        "allergens": "", "serving_size": "30 g", "energy_kcal_100g": 450.0, "energy_kj_100g": 1883.0,
        "fat_100g": 20.0, "saturated_fat_100g": 8.0, "carbohydrates_100g": 60.0, "sugars_100g": 25.0,
        "fiber_100g": 3.0, "proteins_100g": 6.0, "salt_100g": 0.5, "sodium_100g": 0.2,
        "fruits_vegetables_legumes_100g": 0.0, "completeness": 0.5, "nutriscore_score": 12,
        "nutriscore_grade": "d", "nova_group": 4, "food_groups_tag_1": "en:biscuits",
        "categories_tags": ["en:snacks"],
    }
    return {**row, **changes}


# Colonnes du brut produit par extract.py qui ne servent pas au nettoyage, mais que la conversion Parquet exige
EXTRACT_ONLY_COLUMNS = {
    "main_category": "en:biscuits", "additives_n": 2,
    "created_t": 1600000000, "last_modified_t": 1700000000,
}


@pytest.fixture
def source(tmp_path):
    """Parquet brut de trois lignes : un produit, son doublon (code avec espaces), un autre produit."""
    path = tmp_path / "raw.parquet"
    pd.DataFrame([
        raw_product("0012345"),
        raw_product(" 0012345 ", completeness=0.1),
        raw_product("2000002"),
    ]).to_parquet(path)
    return path


@pytest.fixture
def full_source(tmp_path):
    """Même brut que `source`, avec toutes les colonnes d'extract.py (pour enchaîner sur la conversion Parquet)."""
    path = tmp_path / "raw_full.parquet"
    pd.DataFrame([
        raw_product("0012345", **EXTRACT_ONLY_COLUMNS),
        raw_product(" 0012345 ", completeness=0.1, **EXTRACT_ONLY_COLUMNS),
        raw_product("2000002", **EXTRACT_ONLY_COLUMNS),
    ]).to_parquet(path)
    return path


@pytest.fixture
def clean_path(tmp_path):
    """Emplacement du nettoyé dans le dossier temporaire (jamais le vrai data/clean/ du dépôt)."""
    return tmp_path / "clean" / "products_clean.parquet"


@pytest.fixture
def database_conf():
    """Configuration de la base de TEST, déduite de TEST_DATABASE_URL."""
    params = conninfo_to_dict(TEST_DATABASE_URL)
    name = params.pop("dbname")
    return {**params, "database": name}


def test_pipeline_without_database_writes_the_report_and_counts_rows(source, tmp_path, clean_path):
    report_path = tmp_path / "docs" / "rapport.md"
    summary = clean_pipeline.run(source, report_path, load_to_db=False, clean_path=clean_path)
    assert (summary["rows_read"], summary["rows_clean"]) == (3, 2)   # le doublon est écarté
    assert summary["tables"] is None
    assert report_path.exists()


def test_main_no_db_option_stops_after_the_report(source, tmp_path, clean_path):
    report_path = tmp_path / "rapport.md"
    clean_pipeline.main([
        "--source", str(source), "--report", str(report_path), "--clean-out", str(clean_path), "--no-db",
    ])
    assert report_path.exists()


def test_pipeline_writes_the_clean_file(source, tmp_path, clean_path):
    """Le nettoyé est écrit et compte autant de lignes que le pipeline en annonce."""
    summary = clean_pipeline.run(source, tmp_path / "rapport.md", load_to_db=False, clean_path=clean_path)
    assert summary["clean_path"] == clean_path
    assert len(pd.read_parquet(clean_path)) == summary["rows_clean"]


def test_clean_file_keeps_leading_zero(source, tmp_path, clean_path):
    """Le code-barres reste du texte dans le nettoyé écrit : le zéro de tête survit."""
    clean_pipeline.run(source, tmp_path / "rapport.md", load_to_db=False, clean_path=clean_path)
    assert "0012345" in set(pd.read_parquet(clean_path)["code"])


def test_clean_file_has_license(source, tmp_path, clean_path):
    """La licence ODbL est dans les métadonnées du nettoyé."""
    clean_pipeline.run(source, tmp_path / "rapport.md", load_to_db=False, clean_path=clean_path)
    rows = duckdb.sql(
        f"SELECT decode(value) FROM parquet_kv_metadata('{clean_path.as_posix()}') WHERE decode(key) = 'license'"
    ).fetchall()
    assert rows and "ODbL" in rows[0][0]


def test_clean_file_no_temporary_left(source, tmp_path, clean_path):
    """Après écriture, seul le fichier final reste dans le dossier du nettoyé (le .tmp a été renommé)."""
    clean_pipeline.run(source, tmp_path / "rapport.md", load_to_db=False, clean_path=clean_path)
    assert sorted(p.name for p in clean_path.parent.iterdir()) == ["products_clean.parquet"]


def test_main_clean_out_option(source, tmp_path):
    """--clean-out écrit le nettoyé à l'emplacement demandé."""
    output = tmp_path / "ailleurs" / "nettoye.parquet"
    clean_pipeline.main([
        "--source", str(source), "--report", str(tmp_path / "r.md"), "--clean-out", str(output), "--no-db",
    ])
    assert output.exists()


def test_clean_file_feeds_convert_parquet(full_source, tmp_path, clean_path):
    """Le nettoyé écrit par le pipeline est accepté tel quel par la conversion, sans perte de ligne."""
    summary = clean_pipeline.run(full_source, tmp_path / "rapport.md", load_to_db=False, clean_path=clean_path)
    count = convert_parquet.convert(clean_path, tmp_path / "parquet" / "products")
    assert count == summary["rows_clean"]


@needs_db
def test_pipeline_loads_the_cleaned_data_into_the_database(source, tmp_path, clean_path, database_conf):
    summary = clean_pipeline.run(source, tmp_path / "rapport.md", conf=database_conf, clean_path=clean_path)
    assert summary["tables"]["products"] == 2
    assert summary["controls"]["codes en double"] == [(0,)]


@needs_db
def test_pipeline_can_be_replayed(source, tmp_path, clean_path, database_conf):
    first = clean_pipeline.run(source, tmp_path / "rapport.md", conf=database_conf, clean_path=clean_path)
    second = clean_pipeline.run(source, tmp_path / "rapport.md", conf=database_conf, clean_path=clean_path)
    assert first["tables"] == second["tables"]   # rechargement complet : jamais de doublon


@needs_db
def test_database_and_parquet_count_the_same_products(full_source, tmp_path, clean_path, database_conf):
    """Base et Parquet partent du même nettoyé : même nombre de produits (règle du TP 12, étape 2.3)."""
    summary = clean_pipeline.run(full_source, tmp_path / "rapport.md", conf=database_conf, clean_path=clean_path)
    count = convert_parquet.convert(clean_path, tmp_path / "parquet" / "products")
    assert count == summary["tables"]["products"]


def test_pipeline_logs_the_duration_of_each_step(source, tmp_path, clean_path):
    """Sans base : lecture, nettoyage, écriture du nettoyé et rapport sont inscrits au journal des durées."""
    log = tmp_path / "durations.jsonl"
    clean_pipeline.run(source, tmp_path / "rapport.md", load_to_db=False, clean_path=clean_path, durations_path=log)
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [entry["step"] for entry in entries] == [
        config.STEP_READ, config.STEP_CLEAN, config.STEP_WRITE_CLEAN, config.STEP_REPORT,
    ]
    assert entries[0]["rows"] == 3 and entries[1]["rows"] == 2


def test_clean_returns_volumes_and_written_files(source, tmp_path, clean_path):
    """clean() seule (étape clean du pipeline) : volumes, nettoyé et rapport écrits, sans toucher à la base."""
    report_path = tmp_path / "reports" / "cleaning_report.md"
    summary = clean_pipeline.clean(source, clean_path, report_path)
    assert (summary["rows_read"], summary["rows_clean"]) == (3, 2)
    assert summary["clean_path"].exists() and summary["report_path"] == report_path and report_path.exists()


@needs_db
def test_load_database_loads_the_written_clean_file(source, tmp_path, clean_path, database_conf):
    """load_database() seule (étape load_db) : relit le nettoyé sur disque et le charge entièrement."""
    clean_pipeline.clean(source, clean_path, tmp_path / "rapport.md")
    summary = clean_pipeline.load_database(clean_path, database_conf)
    assert summary["tables"]["products"] == 2
    assert summary["controls"]["codes en double"] == [(0,)]