"""Évaluation du modèle Nutri-Score : plis, métriques, et mesure sur les produits sans jumeau.

Un jumeau est un produit d'entraînement aux 13 features strictement identiques. Le split figé sépare les produits
par code-barres, pas par contenu : ~20 % des produits de validation ont un jumeau, que les modèles profonds
reconnaissent par mémoire. La mesure « without_twin » donne la capacité de généralisation réelle.
"""

from __future__ import annotations

import time

import numpy as np
import pandas as pd
from sklearn.base import BaseEstimator, clone
from sklearn.metrics import accuracy_score, balanced_accuracy_score, f1_score
from sklearn.model_selection import StratifiedKFold

from src.ml.features import FEATURES
from src.ml.modeling import RANDOM_STATE

N_SPLITS = 5

# Un seul dictionnaire de métriques, partagé par tous les modèles : nom -> fonction (vraies valeurs, prédictions)
METRICS = {
    "f1_macro": lambda y_true, y_pred: f1_score(y_true, y_pred, average="macro", zero_division=0),
    "f1_weighted": lambda y_true, y_pred: f1_score(y_true, y_pred, average="weighted", zero_division=0),
    "accuracy": accuracy_score,
    "balanced_accuracy": balanced_accuracy_score,
}


def make_cv() -> StratifiedKFold:
    """Plis de la validation croisée : 5 plis stratifiés, mélangés avec une graine fixe (mêmes plis à chaque appel)."""
    return StratifiedKFold(n_splits=N_SPLITS, shuffle=True, random_state=RANDOM_STATE)


def fingerprint(X: pd.DataFrame) -> pd.Series:
    """Empreinte de chaque produit calculée sur ses 13 features : deux produits identiques ont la même empreinte.

    Les autres colonnes de X (code, score...) sont ignorées : la définition d'un jumeau ne dépend que des features.
    """
    return pd.util.hash_pandas_object(X[FEATURES], index=False)


def _score(y_true: pd.Series, y_pred: np.ndarray) -> dict[str, float]:
    """Les métriques de METRICS ; NaN pour toutes si aucun produit (sous-ensemble vide)."""
    if len(y_true) == 0:
        return {name: np.nan for name in METRICS}
    return {name: metric(y_true, y_pred) for name, metric in METRICS.items()}


def evaluate_model(
    pipeline: BaseEstimator,
    X: pd.DataFrame,
    y: pd.Series,
    cv: StratifiedKFold | None = None,
    fingerprints: pd.Series | None = None,
) -> tuple[dict[str, float], pd.Series]:
    """Validation croisée de `pipeline` : métriques sur tous les produits et sur ceux sans jumeau, temps.

    `cv` : tout objet doté de split(X, y) (make_cv() par défaut) ; `fingerprints` : fingerprint(X) par défaut.
    Renvoie (moyennes et écarts-types ddof=0 sur les plis, prédictions hors pli alignées sur y).
    Clés du résumé : <métrique>_mean, <métrique>_std, <métrique>_without_twin_mean / _std, fit_time_s_*, predict_time_s_*.
    """
    cv = cv or make_cv()
    fingerprints = fingerprint(X) if fingerprints is None else fingerprints
    fold_rows = []
    oof_predictions = pd.Series(index=y.index, dtype=object)

    for train_idx, val_idx in cv.split(X, y):
        model = clone(pipeline)   # copie neuve à chaque pli : rien n'est appris d'un pli à l'autre

        start = time.perf_counter()
        model.fit(X.iloc[train_idx], y.iloc[train_idx])
        fit_time = time.perf_counter() - start

        start = time.perf_counter()
        y_pred = model.predict(X.iloc[val_idx])
        predict_time = time.perf_counter() - start

        y_val = y.iloc[val_idx]
        has_twin = fingerprints.iloc[val_idx].isin(set(fingerprints.iloc[train_idx])).to_numpy()

        row = {"fit_time_s": fit_time, "predict_time_s": predict_time}
        row |= _score(y_val, y_pred)
        row |= {f"{name}_without_twin": value for name, value in _score(y_val[~has_twin], y_pred[~has_twin]).items()}
        fold_rows.append(row)
        oof_predictions.iloc[val_idx] = y_pred

    folds = pd.DataFrame(fold_rows)
    summary = {f"{column}_mean": folds[column].mean() for column in folds}
    # Écart-type de population (ddof=0), comme numpy dans cross_validate
    summary |= {f"{column}_std": folds[column].std(ddof=0) for column in folds}
    return summary, oof_predictions