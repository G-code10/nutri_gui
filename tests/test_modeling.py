"""Tests de src/ml/modeling.py : préparation commune, pipeline, garde-fou contre la fuite."""

import pickle

import numpy as np
import pandas as pd
import pytest
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, StandardScaler

from src.ml.features import ALL_NUMERIC_FEATURES, CATEGORICAL_FEATURES, FEATURES, NUMERIC_FEATURES
from src.ml.modeling import RANDOM_STATE, build_pipeline, build_preprocessor, check_no_leak

N_PRODUCTS = 200
OPTIONAL_COLUMNS = ["fiber_100g", "fruits_vegetables_legumes_100g", "nova_group", "additives_n"]


@pytest.fixture
def products() -> tuple[pd.DataFrame, pd.Series]:
    """200 produits fabriqués : nutriments positifs, colonnes optionnelles en partie manquantes, rayons, grades a à e."""
    rng = np.random.default_rng(RANDOM_STATE)
    X = pd.DataFrame({column: rng.uniform(1, 20, N_PRODUCTS) for column in NUMERIC_FEATURES})
    for column in OPTIONAL_COLUMNS:
        X.loc[rng.random(N_PRODUCTS) < 0.4, column] = np.nan
    X["aisle"] = rng.choice(["en-sugary-snacks", "en-beverages", "unknown"], N_PRODUCTS)
    X["aisle2"] = rng.choice(["en-sweets", "en-fruit-juices", "unknown"], N_PRODUCTS)
    X.loc[0, "aisle2"] = "en-offals"   # sous-groupe rare : 1 produit sur 200 (< 1 %)
    y = pd.Series(rng.choice(list("abcde"), N_PRODUCTS), name="nutriscore_grade")
    return X[FEATURES], y


# --- Préparation commune ---
def test_preprocessor_output_columns(products):
    X, _ = products
    names = build_preprocessor().fit(X).get_feature_names_out()

    numeric = [name for name in names if name.startswith("num__") and "missingindicator" not in name]
    indicators = [name for name in names if "missingindicator" in name]
    one_hot = [name for name in names if name.startswith("cat__")]

    assert len(numeric) == len(ALL_NUMERIC_FEATURES)          # 11 brutes + 4 dérivées
    assert len(indicators) == len(OPTIONAL_COLUMNS)           # seules les colonnes avec des manquants au fit
    assert len(one_hot) == 3 + 3 + 1                          # aisle : 3 ; aisle2 : 3 fréquents + infrequent


def test_rare_aisle_is_grouped_as_infrequent(products):
    X, _ = products
    names = build_preprocessor().fit(X).get_feature_names_out()
    assert "cat__aisle2_infrequent_sklearn" in names
    assert "cat__aisle2_en-offals" not in names


def test_preprocessor_output_has_no_missing_value(products):
    X, _ = products
    assert not np.isnan(build_preprocessor().fit_transform(X)).any()


def test_preprocessor_learns_on_fit_data_only(products):
    """Point de contrôle 3 : moyenne standardisée nulle sur les données du fit, pas sur d'autres."""
    X, _ = products
    fit_part, other_part = X.iloc[:150], X.iloc[150:].copy()
    other_part["salt_100g"] += 5          # autre jeu, de moyenne différente

    preprocessor = build_preprocessor().fit(fit_part)
    salt = list(preprocessor.get_feature_names_out()).index("num__salt_100g")
    assert abs(preprocessor.transform(fit_part)[:, salt].mean()) < 1e-9
    assert abs(preprocessor.transform(other_part)[:, salt].mean()) > 1e-9


def test_unknown_aisle_does_not_break_transform(products):
    X, _ = products
    preprocessor = build_preprocessor().fit(X)
    new_product = X.head(1).assign(aisle="en-never-seen", aisle2="en-never-seen-either")
    assert preprocessor.transform(new_product).shape[0] == 1


def test_build_preprocessor_returns_a_new_object_each_time():
    assert build_preprocessor() is not build_preprocessor()


# --- Pipeline complet ---
def test_build_pipeline_fits_and_predicts(products):
    X, y = products
    pipeline = build_pipeline(RandomForestClassifier(n_estimators=10, random_state=RANDOM_STATE)).fit(X, y)
    assert set(pipeline.predict(X)) <= set("abcde")


def test_build_pipeline_model_settings_are_reachable(products):
    pipeline = build_pipeline(RandomForestClassifier(random_state=RANDOM_STATE))
    pipeline.set_params(model__class_weight="balanced")
    assert pipeline.named_steps["model"].class_weight == "balanced"


def test_fitted_pipeline_is_picklable(products):
    """Prépare la sauvegarde (joblib) du TP 15 : aucune lambda dans le pipeline."""
    X, y = products
    pipeline = build_pipeline(DummyClassifier(strategy="most_frequent")).fit(X, y)
    restored = pickle.loads(pickle.dumps(pipeline))
    np.testing.assert_array_equal(restored.predict(X), pipeline.predict(X))


# --- Garde-fou contre la fuite ---
def test_check_no_leak_accepts_the_honest_pipeline(products):
    X, _ = products
    check_no_leak(build_pipeline(DummyClassifier()), X)   # ne lève rien


def test_check_no_leak_detects_forbidden_column_in_data(products):
    X, _ = products
    with pytest.raises(ValueError, match="données d'entrée.*nutriscore_score"):
        check_no_leak(build_pipeline(DummyClassifier()), X.assign(nutriscore_score=0))


def test_check_no_leak_detects_forbidden_column_read_by_preprocessor(products):
    X, _ = products
    leaky = Pipeline([
        ("columns", ColumnTransformer([("num", StandardScaler(), ["salt_100g", "nutriscore_score"])])),
        ("model", DummyClassifier()),
    ])
    with pytest.raises(ValueError, match="lue par le préprocesseur.*nutriscore_score"):
        check_no_leak(leaky, X)


def test_check_no_leak_finds_column_transformer_behind_an_extra_step(products):
    """Une étape ajoutée en fin de préparation (ex. nettoyage des noms pour LightGBM) ne cache pas le ColumnTransformer."""
    X, _ = products
    leaky = Pipeline([
        ("preprocessor", Pipeline([
            ("columns", ColumnTransformer([("cat", "passthrough", CATEGORICAL_FEATURES + ["code"])])),
            ("rename", FunctionTransformer()),
        ])),
        ("model", DummyClassifier()),
    ])
    with pytest.raises(ValueError, match="code"):
        check_no_leak(leaky, X)


def test_check_no_leak_without_column_transformer_raises(products):
    X, _ = products
    with pytest.raises(ValueError, match="Aucun ColumnTransformer"):
        check_no_leak(Pipeline([("model", DummyClassifier())]), X)