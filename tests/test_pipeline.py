"""Tests du pipeline : sans base (rapport et volumes), puis avec une base PostgreSQL de TEST (TEST_DATABASE_URL)."""

import os

import pandas as pd
import pytest
from psycopg.conninfo import conninfo_to_dict

from src import pipeline

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
def database_conf():
    """Configuration de la base de TEST, déduite de TEST_DATABASE_URL."""
    params = conninfo_to_dict(TEST_DATABASE_URL)
    name = params.pop("dbname")
    return {**params, "database": name}


def test_pipeline_without_database_writes_the_report_and_counts_rows(source, tmp_path):
    report_path = tmp_path / "docs" / "rapport.md"
    summary = pipeline.run(source, report_path, load_to_db=False)
    assert (summary["rows_read"], summary["rows_clean"]) == (3, 2)   # le doublon est écarté
    assert summary["tables"] is None
    assert report_path.exists()


def test_main_no_db_option_stops_after_the_report(source, tmp_path):
    report_path = tmp_path / "rapport.md"
    pipeline.main(["--source", str(source), "--report", str(report_path), "--no-db"])
    assert report_path.exists()


@needs_db
def test_pipeline_loads_the_cleaned_data_into_the_database(source, tmp_path, database_conf):
    summary = pipeline.run(source, tmp_path / "rapport.md", conf=database_conf)
    assert summary["tables"]["products"] == 2
    assert summary["controls"]["codes en double"] == [(0,)]


@needs_db
def test_pipeline_can_be_replayed(source, tmp_path, database_conf):
    first = pipeline.run(source, tmp_path / "rapport.md", conf=database_conf)
    second = pipeline.run(source, tmp_path / "rapport.md", conf=database_conf)
    assert first["tables"] == second["tables"]   # rechargement complet : jamais de doublon