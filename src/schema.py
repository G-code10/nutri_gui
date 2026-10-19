"""Schéma de validation (pandera) du DataFrame nettoyé, vérifié avant son chargement en base.

Les bornes viennent de cleaning.RANGES : une seule source, aucun chiffre recopié.
Le schéma n'est pas strict : les colonnes qu'il ne cite pas (textes libres, drapeaux
<col>_missing) sont acceptées. Un nutriment manquant (NA) est accepté aussi : seule une
valeur présente est contrôlée, comme dans les contraintes CHECK de la base.
"""

import pandera.pandas as pa

from src import cleaning

# Un nutriment : décimal, nullable, dans les bornes du nettoyage
NUTRIENTS = {
    column: pa.Column("float64", pa.Check.in_range(low, high), nullable=True)
    for column, (low, high) in cleaning.RANGES.items()
}

# Les trois drapeaux stockés en base : jamais NA
STORED_FLAGS = {
    column: pa.Column("boolean", nullable=False)
    for column in ("grade_not_applicable", "saturated_fat_100g_missing", "energy_kcal_100g_missing")
}


def _subpart_within_total(df, subpart, total, tolerance):
    """Vrai pour chaque ligne où la sous-partie ne dépasse pas son total (ou si l'un des deux manque)."""
    return (df[subpart] <= df[total] + tolerance) | df[subpart].isna() | df[total].isna()


SCHEMA = pa.DataFrameSchema(
    {
        "code": pa.Column(
            "string",
            pa.Check(lambda s: (s.ne("") & s.eq(s.str.strip())).fillna(False), error="code vide ou avec espaces"),
            unique=True,
            nullable=False,
        ),
        "nutriscore_grade": pa.Column(checks=pa.Check.isin(list("abcde")), nullable=True),
        # Étendue observée dans les données (le brut contient des scores de -17 à 55)
        "nutriscore_score": pa.Column(checks=pa.Check.in_range(-17, 55), nullable=True),
        "nova_group": pa.Column(checks=pa.Check.in_range(1, 4), nullable=True),
        "completeness": pa.Column(checks=pa.Check.ge(0), nullable=True),
        "categories_tags": pa.Column(
            checks=pa.Check(
                lambda s: s.map(lambda tags: hasattr(tags, "__len__") and len(tags) > 0),
                error="catégories vides",
            ),
        ),
        **NUTRIENTS,
        **STORED_FLAGS,
    },
    checks=[
        pa.Check(
            lambda df: _subpart_within_total(df, "sugars_100g", "carbohydrates_100g", cleaning.SUGARS_TOLERANCE),
            error="sucres supérieurs aux glucides",
        ),
        pa.Check(
            lambda df: _subpart_within_total(df, "saturated_fat_100g", "fat_100g", cleaning.SATURATED_TOLERANCE),
            error="saturées supérieures aux lipides",
        ),
    ],
    strict=False,
)


def validate(df):
    """Valide le DataFrame nettoyé et le renvoie. Lève pandera.errors.SchemaErrors avec toutes les anomalies."""
    return SCHEMA.validate(df, lazy=True)