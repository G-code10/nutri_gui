"""Tests du rapport : les chiffres sont justes, et il se régénère à l'identique (à la date près)."""

import pandas as pd
import pytest

from src import cleaning, report


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
def raw():
    """Trois lignes brutes : une valide, son doublon (code avec espaces), un produit à sucres 74 000 g et sel 5 000 g."""
    return pd.DataFrame([
        raw_product("0012345"),
        raw_product(" 0012345 ", completeness=0.1),
        raw_product("2000002", sugars_100g=74000.0, salt_100g=5000.0),
    ])


@pytest.fixture
def cleaned(raw):
    after, reports = cleaning.clean(raw)
    return after, reports


def test_business_anomalies_counts_each_defect_once(raw):
    found = report.business_anomalies(raw)
    assert found["sugars_100g hors de [0 ; 100]"] == 1
    assert found["salt_100g hors de [0 ; 100]"] == 1
    assert found["sucres > glucides + 0,5"] == 1
    assert found["sel ≠ sodium × 2,5 (écart > 0,1)"] == 1
    assert found["codes en double (lignes en trop)"] == 1   # le code avec espaces compte comme le même code


def test_business_anomalies_are_zero_after_cleaning(cleaned):
    after, _ = cleaned
    assert sum(report.business_anomalies(after).values()) == 0


def test_report_contains_every_section_and_the_credit(raw, cleaned):
    after, reports = cleaned
    text = report.build_report(raw, after, reports, "data/sample_raw.parquet", date="2026-01-01")
    assert "Open Food Facts" in text and "ODbL" in text
    assert "- Date : 2026-01-01" in text and "`data/sample_raw.parquet`" in text
    for title in ("## 1.", "## 2.", "## 3.", "## 4.", "## 5.", "## 6."):
        assert title in text
    assert "| Lignes | 3 | 2 |" in text   # 3 lignes brutes, 2 après la déduplication


def test_report_is_identical_when_regenerated_except_for_the_date(raw, cleaned):
    after, reports = cleaned
    first = report.build_report(raw, after, reports, "src", date="2026-01-01")
    second = report.build_report(raw, after, reports, "src", date="2026-01-01")
    other_day = report.build_report(raw, after, reports, "src", date="2026-02-02")
    assert first == second
    assert first.replace("2026-01-01", "2026-02-02") == other_day   # seule la date change


def test_generate_report_writes_the_file_with_unix_line_endings(raw, cleaned, tmp_path):
    after, reports = cleaned
    path = report.generate_report(raw, after, reports, tmp_path / "docs" / "data" / "rapport.md", "src")
    assert path.exists()
    assert b"\r" not in path.read_bytes()   # même fichier sous Windows et sous Linux


def test_main_reads_a_parquet_and_writes_the_report(raw, tmp_path):
    source, out = tmp_path / "raw.parquet", tmp_path / "rapport.md"
    raw.to_parquet(source)
    report.main(["--source", str(source), "--out", str(out)])
    assert "## 3. Anomalies métier avant / après" in out.read_text(encoding="utf-8")