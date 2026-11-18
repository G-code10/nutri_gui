"""Tests de src/ml/features.py : listes de features, chargement, split, features dérivées."""

import numpy as np
import pandas as pd
import pytest

from src import config
from src.ml import features
from src.ml.features import (
    ALL_NUMERIC_FEATURES,
    CATEGORICAL_FEATURES,
    DERIVED_FEATURES,
    ENERGY_GAP,
    ENERGY_GAP_MAX,
    FEATURES,
    FORBIDDEN,
    NUMERIC_FEATURES,
    GRADE_CODES,
    add_derived_features,
    decode_target,
    encode_target,
    features_and_target,
    load_features,
    split_train_test,
)
from src.storage.export_features import SPLIT, TARGET, TEST, TRAIN


def _nutrients(**values) -> pd.DataFrame:
    """Une ligne de nutriments neutres (tout à 1), avec les valeurs données remplacées ; énergie = 4/4/9 exacte."""
    row = {column: 1.0 for column in NUMERIC_FEATURES}
    row.update(values)
    if "energy_kcal_100g" not in values:
        row["energy_kcal_100g"] = 4 * row["carbohydrates_100g"] + 4 * row["proteins_100g"] + 9 * row["fat_100g"]
    return pd.DataFrame([row])


@pytest.fixture
def products() -> pd.DataFrame:
    """Six produits complets (features, cible, split, code, score), dont deux en test."""
    rng = np.random.default_rng(0)
    df = pd.DataFrame({column: rng.uniform(0.5, 20, 6) for column in NUMERIC_FEATURES})
    df["aisle"] = ["en-sugary-snacks", "en-beverages", "unknown", "en-sugary-snacks", "en-beverages", "unknown"]
    df["aisle2"] = ["en-sweets", "en-fruit-juices", "unknown", "en-sweets", "en-fruit-juices", "unknown"]
    df["code"] = [f"{i:013d}" for i in range(6)]
    df["nutriscore_score"] = [10, 2, -3, 15, 4, 0]
    df[TARGET] = ["d", "b", "a", "e", "c", "a"]
    df[SPLIT] = [TRAIN, TRAIN, TRAIN, TRAIN, TEST, TEST]
    return df


# --- Listes de features ---
def test_features_are_the_13_raw_columns():
    assert len(CATEGORICAL_FEATURES) == 2
    assert len(NUMERIC_FEATURES) == 11
    assert FEATURES == CATEGORICAL_FEATURES + NUMERIC_FEATURES


def test_no_forbidden_column_in_features():
    assert not FORBIDDEN & set(FEATURES)
    assert not FORBIDDEN & set(ALL_NUMERIC_FEATURES)
    assert "nutriscore_score" in FORBIDDEN


# --- Chargement ---
def test_load_features_reads_the_given_path(tmp_path, products):
    path = tmp_path / "features_nutriscore_20261115.parquet"
    products.to_parquet(path)
    pd.testing.assert_frame_equal(load_features(path), products)


def test_load_features_finds_the_latest_export(tmp_path, monkeypatch, products):
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path)
    products.to_parquet(tmp_path / "features_nutriscore_20261101.parquet")
    products.head(2).to_parquet(tmp_path / "features_nutriscore_20261110.parquet")
    assert len(load_features(day=pd.Timestamp("2026-11-15").date())) == 2


def test_load_features_without_export_raises(tmp_path, monkeypatch):
    monkeypatch.setattr(config, "EXPORTS_DIR", tmp_path)
    with pytest.raises(FileNotFoundError, match=features.EXPORT_HINT):
        load_features()


# --- Split et (X, y) ---
def test_split_train_test_follows_the_split_column(products):
    train, test = split_train_test(products)
    assert len(train) == 4 and len(test) == 2
    assert set(train[SPLIT]) == {TRAIN} and set(test[SPLIT]) == {TEST}
    assert not set(train["code"]) & set(test["code"])


def test_features_and_target(products):
    X, y = features_and_target(products)
    assert list(X.columns) == FEATURES
    assert y.name == TARGET
    assert not FORBIDDEN & set(X.columns)


def test_features_and_target_missing_feature_raises(products):
    with pytest.raises(KeyError):
        features_and_target(products.drop(columns="aisle2"))


# --- Codage de la cible ---
def test_grade_codes_follow_nutriscore_order():
    assert GRADE_CODES == {"a": 0, "b": 1, "c": 2, "d": 3, "e": 4}


def test_encode_then_decode_gives_back_the_grades(products):
    _, y = features_and_target(products)
    codes = encode_target(y)
    assert codes.dtype == "int64"
    assert codes.index.equals(y.index) and codes.name == y.name
    pd.testing.assert_series_equal(decode_target(codes), y)


def test_decode_target_on_array_returns_array():
    np.testing.assert_array_equal(decode_target(np.array([4, 0, 2])), np.array(["e", "a", "c"]))


def test_encode_target_unknown_grade_raises():
    with pytest.raises(ValueError, match="inconnues"):
        encode_target(pd.Series(["a", "unknown", "e"]))


@pytest.mark.parametrize("codes", [np.array([0, 5]), np.array([-1, 2]), np.array([1.5, 2.0])])
def test_decode_target_invalid_code_raises(codes):
    with pytest.raises(ValueError, match="invalides"):
        decode_target(codes)


# --- Features dérivées : ratios ---
@pytest.mark.parametrize(
    ("sugars", "carbohydrates", "expected"),
    [
        (5.0, 20.0, 0.25),      # division normale
        (10.3, 10.0, 1.0),      # plafonné à RATIO_MAX
        (0.0, 0.0, 0.0),        # 0/0 -> 0
        (2.0, 0.0, np.nan),     # seul le dénominateur vaut 0 -> manquant
    ],
)
def test_ratio_rules(sugars, carbohydrates, expected):
    result = add_derived_features(_nutrients(sugars_100g=sugars, carbohydrates_100g=carbohydrates))
    np.testing.assert_allclose(result["sugars_carbohydrates_ratio"].iloc[0], expected)


def test_fat_energy_ratio_uses_9_kcal_per_gram():
    result = add_derived_features(_nutrients(fat_100g=10.0, energy_kcal_100g=300.0))
    assert result["fat_energy_ratio"].iloc[0] == pytest.approx(90 / 300)


# --- Features dérivées : écart d'énergie ---
def test_energy_gap_is_relative():
    # calculée = 4*10 + 4*10 + 9*0 = 80 ; déclarée 88 -> +10 %
    row = _nutrients(carbohydrates_100g=10.0, proteins_100g=10.0, fat_100g=0.0, energy_kcal_100g=88.0)
    assert add_derived_features(row)[ENERGY_GAP].iloc[0] == pytest.approx(0.10)


def test_energy_gap_is_capped():
    row = _nutrients(carbohydrates_100g=1.0, proteins_100g=0.0, fat_100g=0.0, energy_kcal_100g=400.0)   # +9 900 %
    assert add_derived_features(row)[ENERGY_GAP].iloc[0] == ENERGY_GAP_MAX


def test_energy_gap_missing_when_computed_energy_is_zero():
    row = _nutrients(carbohydrates_100g=0.0, proteins_100g=0.0, fat_100g=0.0, energy_kcal_100g=5.0)
    assert np.isnan(add_derived_features(row)[ENERGY_GAP].iloc[0])


# --- Features dérivées : forme du résultat ---
def test_add_derived_features_adds_the_4_columns_without_modifying_input(products):
    X, _ = features_and_target(products)
    before = X.copy()
    result = add_derived_features(X)
    assert list(result.columns) == FEATURES + DERIVED_FEATURES
    pd.testing.assert_frame_equal(X, before)