"""Tests de src/ml/evaluation.py : plis, empreinte des jumeaux, validation croisée, évaluation sur le test."""

import numpy as np
import pandas as pd
import pytest
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import NotFittedError
from sklearn.model_selection import cross_validate
from sklearn.tree import DecisionTreeClassifier

from src.ml.evaluation import METRICS, N_SPLITS, evaluate_model, evaluate_on_test, fingerprint, make_cv
from src.ml.features import FEATURES, NUMERIC_FEATURES
from src.ml.modeling import RANDOM_STATE, build_pipeline

N_PRODUCTS = 200


@pytest.fixture
def products() -> tuple[pd.DataFrame, pd.Series]:
    """200 produits fabriqués, tous différents, grades a à e liés au sel (le modèle a quelque chose à apprendre)."""
    rng = np.random.default_rng(RANDOM_STATE)
    X = pd.DataFrame({column: rng.uniform(1, 20, N_PRODUCTS) for column in NUMERIC_FEATURES})
    X["aisle"] = rng.choice(["en-sugary-snacks", "en-beverages"], N_PRODUCTS)
    X["aisle2"] = rng.choice(["en-sweets", "en-fruit-juices"], N_PRODUCTS)
    y = pd.Series(pd.cut(X["salt_100g"], 5, labels=list("abcde")).astype(str), name="nutriscore_grade")
    return X[FEATURES], y


# --- Plis ---
def test_make_cv_gives_the_same_folds_twice(products):
    """Point de contrôle 6 : deux appels à split rendent exactement les mêmes indices."""
    X, y = products
    first, second = list(make_cv().split(X, y)), list(make_cv().split(X, y))
    assert len(first) == N_SPLITS
    for (train_a, val_a), (train_b, val_b) in zip(first, second):
        np.testing.assert_array_equal(train_a, train_b)
        np.testing.assert_array_equal(val_a, val_b)


def test_make_cv_is_stratified(products):
    X, y = products
    overall = y.value_counts(normalize=True).sort_index()
    for _, val_idx in make_cv().split(X, y):
        fold = y.iloc[val_idx].value_counts(normalize=True).sort_index()
        np.testing.assert_allclose(fold, overall, atol=0.03)


# --- Empreinte des jumeaux ---
def test_fingerprint_identical_products_share_it(products):
    X, _ = products
    doubled = pd.concat([X.head(3), X.head(3)], ignore_index=True)
    prints = fingerprint(doubled)
    assert prints.iloc[0] == prints.iloc[3]
    assert prints.iloc[0] != prints.iloc[1]


def test_fingerprint_ignores_non_feature_columns(products):
    X, _ = products
    with_code = X.assign(code=[f"{i:013d}" for i in range(len(X))], nutriscore_score=0)
    pd.testing.assert_series_equal(fingerprint(with_code), fingerprint(X))


# --- Évaluation ---
def test_evaluate_model_summary_keys(products):
    X, y = products
    summary, _ = evaluate_model(build_pipeline(DummyClassifier()), X, y)
    for name in [*METRICS, "fit_time_s", "predict_time_s"]:
        assert f"{name}_mean" in summary and f"{name}_std" in summary
    for name in METRICS:
        assert f"{name}_without_twin_mean" in summary and f"{name}_without_twin_std" in summary


def test_evaluate_model_matches_cross_validate(products):
    """Mêmes plis, mêmes chiffres que cross_validate (moyenne et écart-type ddof=0) : comparabilité avec le TP 14."""
    X, y = products
    pipeline = build_pipeline(RandomForestClassifier(n_estimators=20, random_state=RANDOM_STATE))
    summary, _ = evaluate_model(pipeline, X, y, make_cv())
    reference = cross_validate(pipeline, X, y, cv=make_cv(), scoring=["f1_macro", "accuracy", "balanced_accuracy"])
    for name in ["f1_macro", "accuracy", "balanced_accuracy"]:
        assert summary[f"{name}_mean"] == pytest.approx(reference[f"test_{name}"].mean())
        assert summary[f"{name}_std"] == pytest.approx(reference[f"test_{name}"].std())


def test_evaluate_model_majority_baseline(products):
    """Point de contrôle 1 en miniature : la classe majoritaire a pour accuracy sa propre part, et un F1 macro bien plus bas."""
    X, y = products
    summary, _ = evaluate_model(build_pipeline(DummyClassifier(strategy="most_frequent")), X, y)
    assert summary["accuracy_mean"] == pytest.approx(y.value_counts(normalize=True).max(), abs=0.02)
    assert summary["f1_macro_mean"] < summary["accuracy_mean"]


def test_evaluate_model_out_of_fold_predictions(products):
    X, y = products
    _, oof = evaluate_model(build_pipeline(DummyClassifier()), X, y)
    assert oof.index.equals(y.index)
    assert oof.notna().all()
    assert set(oof) <= set(y)


def test_without_twin_equals_all_when_no_product_is_duplicated(products):
    X, y = products
    summary, _ = evaluate_model(build_pipeline(RandomForestClassifier(n_estimators=10, random_state=RANDOM_STATE)), X, y)
    assert summary["f1_macro_without_twin_mean"] == pytest.approx(summary["f1_macro_mean"])


class _CopySplit:
    """Découpage imposé en un pli : entraînement sur la 1re copie des produits, validation sur la 2de."""

    def __init__(self, n_products: int):
        self.n_products = n_products

    def split(self, X, y):
        yield np.arange(self.n_products), np.arange(self.n_products, 2 * self.n_products)


def test_without_twin_is_nan_when_every_validation_product_has_a_twin(products):
    """Chaque produit de validation a son jumeau exact dans l'entraînement : aucun produit « sans jumeau »."""
    X, y = products
    X_doubled = pd.concat([X, X], ignore_index=True)
    y_doubled = pd.concat([y, y], ignore_index=True)
    summary, _ = evaluate_model(build_pipeline(DummyClassifier()), X_doubled, y_doubled, cv=_CopySplit(len(X)))
    assert np.isnan(summary["f1_macro_without_twin_mean"])
    assert not np.isnan(summary["f1_macro_mean"])


def test_twins_are_recognised_by_a_memorising_model(products):
    """Un arbre complet (sans tirage aléatoire des produits) reconnaît ses jumeaux : score parfait."""
    X, y = products
    X_doubled = pd.concat([X, X], ignore_index=True)
    y_doubled = pd.concat([y, y], ignore_index=True)
    model = build_pipeline(DecisionTreeClassifier(random_state=RANDOM_STATE))
    summary, _ = evaluate_model(model, X_doubled, y_doubled, cv=_CopySplit(len(X)))
    assert summary["f1_macro_mean"] == pytest.approx(1.0)


# --- Évaluation sur le test ---
def test_evaluate_on_test_summary_and_predictions(products):
    X, y = products
    X_train, y_train, X_test, y_test = X.iloc[:150], y.iloc[:150], X.iloc[150:], y.iloc[150:]
    summary, predictions, _ = evaluate_on_test(build_pipeline(DummyClassifier()), X_train, y_train, X_test, y_test)

    for name in METRICS:
        assert name in summary and f"{name}_without_twin" in summary
    assert {"fit_time_s", "predict_time_s", "twin_share"} <= set(summary)
    assert predictions.index.equals(y_test.index)


def test_evaluate_on_test_matches_a_manual_fit(products):
    X, y = products
    X_train, y_train, X_test, y_test = X.iloc[:150], y.iloc[:150], X.iloc[150:], y.iloc[150:]
    pipeline = build_pipeline(RandomForestClassifier(n_estimators=20, random_state=RANDOM_STATE))
    summary, predictions, _ = evaluate_on_test(pipeline, X_train, y_train, X_test, y_test)

    manual = pipeline.fit(X_train, y_train).predict(X_test)
    np.testing.assert_array_equal(predictions.to_numpy(), manual)
    assert summary["f1_macro"] == pytest.approx(METRICS["f1_macro"](y_test, manual))


def test_evaluate_on_test_returns_a_fitted_copy(products):
    X, y = products
    pipeline = build_pipeline(DummyClassifier())
    _, _, fitted = evaluate_on_test(pipeline, X.iloc[:150], y.iloc[:150], X.iloc[150:], y.iloc[150:])
    assert fitted is not pipeline
    fitted.predict(X.head(1))                  # la copie est ajustée
    with pytest.raises(NotFittedError):
        pipeline.predict(X.head(1))            # l'original n'est pas touché


def test_evaluate_on_test_without_twin_when_test_has_no_twin(products):
    X, y = products
    summary, _, _ = evaluate_on_test(build_pipeline(DummyClassifier()), X.iloc[:150], y.iloc[:150], X.iloc[150:], y.iloc[150:])
    assert summary["twin_share"] == 0.0
    assert summary["f1_macro_without_twin"] == pytest.approx(summary["f1_macro"])


def test_evaluate_on_test_every_test_product_has_a_twin(products):
    X, y = products
    summary, _, _ = evaluate_on_test(build_pipeline(DummyClassifier()), X, y, X.iloc[:50], y.iloc[:50])
    assert summary["twin_share"] == 1.0
    assert np.isnan(summary["f1_macro_without_twin"])