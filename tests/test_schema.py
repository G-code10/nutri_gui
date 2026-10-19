"""Tests du schéma de validation : un DataFrame nettoyé passe, chaque défaut est refusé."""

from pathlib import Path

import pandas as pd
import pandera.pandas as pa
import pytest

from src import cleaning, schema

NA = pd.NA
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_raw.parquet"


@pytest.fixture
def clean_df():
    """Un produit valide, passé par clean() : c'est exactement ce que le chargement recevra."""
    raw = pd.DataFrame([{
        "code": "0012345", "product_name": "Biscuit", "brands": "Marque", "ingredients_text": "sucre",
        "allergens": "", "serving_size": "30 g", "energy_kcal_100g": 450.0, "energy_kj_100g": 1883.0,
        "fat_100g": 20.0, "saturated_fat_100g": 8.0, "carbohydrates_100g": 60.0, "sugars_100g": 25.0,
        "fiber_100g": 3.0, "proteins_100g": 6.0, "salt_100g": 0.5, "sodium_100g": 0.2,
        "fruits_vegetables_legumes_100g": 0.0, "completeness": 0.5, "nutriscore_score": 12,
        "nutriscore_grade": "d", "nova_group": 4, "food_groups_tag_1": "en:biscuits",
        "categories_tags": ["en:snacks"],
    }])
    res, _ = cleaning.clean(raw)
    assert len(res) == 1
    return res


def with_value(df, **changes):
    """Copie du DataFrame avec quelques colonnes modifiées."""
    res = df.copy()
    for column, value in changes.items():
        res[column] = value
    return res


def test_valid_dataframe_passes(clean_df):
    assert len(schema.validate(clean_df)) == 1


def test_missing_nutrient_is_accepted(clean_df):
    schema.validate(with_value(clean_df, fiber_100g=float("nan")))


def test_energy_bound_is_inclusive(clean_df):
    # 900 kcal est à la borne (accepté), 901 est au-delà
    schema.validate(with_value(clean_df, energy_kcal_100g=900.0))
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(with_value(clean_df, energy_kcal_100g=901.0))


def test_duplicate_code_is_refused(clean_df):
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(pd.concat([clean_df, clean_df], ignore_index=True))


def test_code_with_spaces_is_refused(clean_df):
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(with_value(clean_df, code=pd.array([" 0012345"], dtype="string")))


def test_grade_outside_a_to_e_is_refused(clean_df):
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(with_value(clean_df, nutriscore_grade="f"))


def test_sugars_above_carbohydrates_is_refused(clean_df):
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(with_value(clean_df, sugars_100g=61.0))   # glucides = 60, tolérance 0,5


def test_empty_categories_are_refused(clean_df):
    with pytest.raises(pa.errors.SchemaErrors):
        schema.validate(with_value(clean_df, categories_tags=pd.Series([[]], dtype=object)))


def test_all_errors_are_reported_at_once(clean_df):
    bad = with_value(clean_df, nutriscore_grade="f", energy_kcal_100g=901.0)
    with pytest.raises(pa.errors.SchemaErrors) as error:
        schema.validate(bad)
    assert len(error.value.failure_cases) >= 2


@pytest.mark.skipif(not SAMPLE_PATH.exists(), reason="échantillon réel absent")
def test_cleaned_real_sample_passes():
    cleaned, _ = cleaning.clean(pd.read_parquet(SAMPLE_PATH))
    schema.validate(cleaned)