"""Features du modèle Nutri-Score : listes de colonnes, chargement de l'export, split, features dérivées.

Les features dérivées se calculent ligne par ligne, sans rien apprendre des données : elles entrent dans le pipeline
par un FunctionTransformer (modeling.py), jamais à la main sur le DataFrame.

Données : © Open Food Facts contributors — ODbL.
"""

from __future__ import annotations

import datetime
from pathlib import Path

import pandas as pd

from src import config
from src.storage.export_features import EXPORT_PREFIX, IDENTIFIER, RATIO_MAX, RATIOS, SPLIT, TARGET, TEST, TRAIN
from src.utils import require_input

CATEGORICAL_FEATURES = ["aisle", "aisle2"]
NUMERIC_FEATURES = [
    *config.CORE_NUTRIENTS,               # les 7 nutriments obligatoires
    "fiber_100g",
    "fruits_vegetables_legumes_100g",
    "nova_group",                         # traité en nombre, comme le TP
    "additives_n",
]
FEATURES = CATEGORICAL_FEATURES + NUMERIC_FEATURES

ENERGY_GAP = "energy_gap_ratio"
DERIVED_FEATURES = [*RATIOS, ENERGY_GAP]             # 3 ratios de l'export + écart d'énergie relatif
ALL_NUMERIC_FEATURES = NUMERIC_FEATURES + DERIVED_FEATURES

# Colonnes jamais features : identifiant, split, cible et score dont le grade est déduit (fuite)
FORBIDDEN = frozenset({IDENTIFIER, SPLIT, TARGET, "nutriscore_score"})

# Plafond de l'écart d'énergie : ~0,1 % de fiches aberrantes (jusqu'à ~1 150) fausseraient la standardisation et la logistique
ENERGY_GAP_MAX = 1.0

EXPORT_HINT = "python -m src.storage.export_features"


def load_features(path: Path | None = None, day: datetime.date | None = None) -> pd.DataFrame:
    """Export features : `path` s'il est donné, sinon la version datée de `day` (aujourd'hui par défaut) ou la plus récente avant.

    Lève FileNotFoundError, avec la commande à lancer, si aucun export n'existe.
    """
    path = path or require_input(config.EXPORTS_DIR, EXPORT_PREFIX, ".parquet", day, EXPORT_HINT)
    return pd.read_parquet(path)


def split_train_test(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """(train, test) selon la colonne split figée de l'export, toutes colonnes gardées (code utile à l'analyse d'erreurs)."""
    return df[df[SPLIT] == TRAIN], df[df[SPLIT] == TEST]


def features_and_target(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series]:
    """(X, y) : les 13 features et la cible ; lève KeyError si une feature manque dans `df`."""
    return df[FEATURES], df[TARGET]


def _safe_ratio(numerator: pd.Series, denominator: pd.Series) -> pd.Series:
    """Ratio borné à RATIO_MAX, mêmes règles que l'export : 0 si 0/0, manquant si seul le dénominateur vaut 0."""
    ratio = (numerator / denominator.where(denominator != 0)).clip(upper=RATIO_MAX)
    return ratio.mask((denominator == 0) & (numerator == 0), 0.0)


def add_derived_features(X: pd.DataFrame) -> pd.DataFrame:
    """Copie de X avec les 4 features dérivées ajoutées ; X n'est pas modifié."""
    X = X.copy()
    X["sugars_carbohydrates_ratio"] = _safe_ratio(X["sugars_100g"], X["carbohydrates_100g"])
    X["saturated_fat_ratio"] = _safe_ratio(X["saturated_fat_100g"], X["fat_100g"])
    X["fat_energy_ratio"] = _safe_ratio(9 * X["fat_100g"], X["energy_kcal_100g"])

    # Écart d'énergie relatif (règle 14) : (déclarée - calculée 4/4/9) / calculée ; manquant si calculée = 0,
    # plafonné à ±ENERGY_GAP_MAX
    computed_energy = 4 * X["carbohydrates_100g"] + 4 * X["proteins_100g"] + 9 * X["fat_100g"]
    energy_gap = (X["energy_kcal_100g"] - computed_energy) / computed_energy.where(computed_energy != 0)
    X[ENERGY_GAP] = energy_gap.clip(-ENERGY_GAP_MAX, ENERGY_GAP_MAX)
    return X