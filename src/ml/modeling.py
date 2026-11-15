"""Pipeline du modèle Nutri-Score : une seule préparation, partagée par tous les modèles, et garde-fou contre la fuite.

La préparation (features dérivées, imputation + indicateur, standardisation, one-hot) est entièrement dans le
pipeline : la validation croisée la réajuste à chaque pli, sans jamais voir le pli de validation.
"""

from __future__ import annotations

from collections.abc import Iterator, Sequence

import pandas as pd
from sklearn.base import BaseEstimator
from sklearn.compose import ColumnTransformer
from sklearn.impute import SimpleImputer
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import FunctionTransformer, OneHotEncoder, StandardScaler

from src.ml.features import ALL_NUMERIC_FEATURES, CATEGORICAL_FEATURES, DERIVED_FEATURES, FORBIDDEN, add_derived_features

RANDOM_STATE = 42       # graine de tous les modèles et des plis
MIN_FREQUENCY = 0.01    # un rayon présent dans moins de 1 % des produits du fit rejoint la colonne « infrequent »


def _derived_feature_names(transformer: FunctionTransformer, input_names: Sequence[str]) -> list[str]:
    """Noms en sortie du calcul des features dérivées : colonnes d'entrée puis les 4 dérivées.

    Fonction de module (et non lambda) : le pipeline reste sérialisable par joblib.
    """
    return [*input_names, *DERIVED_FEATURES]


def build_preprocessor(min_frequency: float = MIN_FREQUENCY) -> Pipeline:
    """Préparation commune, neuve à chaque appel : features dérivées, puis traitement par type de colonne."""
    numeric = Pipeline([
        ("imputer", SimpleImputer(strategy="median", add_indicator=True)),   # médiane + colonne 0/1 « était manquante »
        ("scaler", StandardScaler()),
    ])
    categorical = OneHotEncoder(handle_unknown="ignore", min_frequency=min_frequency, sparse_output=False)
    columns = ColumnTransformer([
        ("num", numeric, ALL_NUMERIC_FEATURES),
        ("cat", categorical, CATEGORICAL_FEATURES),
    ])
    derive = FunctionTransformer(add_derived_features, feature_names_out=_derived_feature_names)
    return Pipeline([("derive", derive), ("columns", columns)])


def build_pipeline(model: BaseEstimator, min_frequency: float = MIN_FREQUENCY) -> Pipeline:
    """Préparation commune suivie de `model` ; les réglages du modèle se changent par set_params(model__...)."""
    return Pipeline([("preprocessor", build_preprocessor(min_frequency)), ("model", model)])


def _column_transformers(estimator: BaseEstimator) -> Iterator[ColumnTransformer]:
    """Tous les ColumnTransformer de `estimator`, à n'importe quelle profondeur de pipelines imbriqués."""
    if isinstance(estimator, ColumnTransformer):
        yield estimator
    for _, step in getattr(estimator, "steps", []):
        yield from _column_transformers(step)


def _read_columns(column_transformer: ColumnTransformer) -> set[str]:
    """Noms des colonnes lues par un ColumnTransformer (listes de noms ou nom seul)."""
    read = set()
    for _, _, columns in column_transformer.transformers:
        read |= {columns} if isinstance(columns, str) else {column for column in columns if isinstance(column, str)}
    return read


def check_no_leak(pipeline: BaseEstimator, X: pd.DataFrame, forbidden: frozenset[str] = FORBIDDEN) -> None:
    """Lève ValueError si une colonne interdite est dans X ou lue par un ColumnTransformer du pipeline.

    Lève aussi ValueError si le pipeline ne contient aucun ColumnTransformer : rien ne pourrait alors être vérifié.
    """
    in_data = forbidden & set(X.columns)
    if in_data:
        raise ValueError(f"Colonne interdite dans les données d'entrée : {sorted(in_data)}")

    column_transformers = list(_column_transformers(pipeline))
    if not column_transformers:
        raise ValueError("Aucun ColumnTransformer dans le pipeline : colonnes lues impossibles à vérifier")
    in_pipeline = forbidden & set().union(*(_read_columns(ct) for ct in column_transformers))
    if in_pipeline:
        raise ValueError(f"Colonne interdite lue par le préprocesseur : {sorted(in_pipeline)}")