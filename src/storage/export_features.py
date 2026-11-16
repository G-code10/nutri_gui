"""Export features daté pour prédire le Nutri-Score, avec son split train / test figé dans un parquet

Entrée : le Parquet partitionné par rayon (convert_parquet), refusé s'il n'a pas le marqueur _SUCCESS
Sortie : data/exports/features_nutriscore_<AAAAMMJJ>.parquet et features_nutriscore_<AAAAMMJJ>.schema.json

Un export est figé : il n'est jamais réécrit sans --force, split tiré avec une graine fixe, 
aucune date dans les données, licence en métadonnées

Split : colonne `split` (train ou test),tirage en une fois stratifié sur le grade

Usage : via le pipeline (python -m nutriscope.pipeline export, voir nutriscope/pipeline.py)
seul : python -m src.storage.export_features [--source …] [--out-dir …] [--force]

Données : © Open Food Facts contributors — ODbL (rappel écrit dans le Parquet et dans le schéma).
"""

import argparse
import json
import os
from datetime import date
from pathlib import Path

import duckdb
import numpy as np
import pyarrow as pa
from sklearn.model_selection import train_test_split

from src import cleaning, config
from src.storage.convert_parquet import SUCCESS_MARKER
from src.utils import (
    aisle_slug_sql,
    display_path,
    duckdb_parquet_options,
    file_sha256,
    format_int,
    require_input,
    sql_literal,
    today,
)

DEFAULT_OUT_DIR = config.EXPORTS_DIR
EXPORT_PREFIX = "features_nutriscore"

TARGET = "nutriscore_grade"
IDENTIFIER = "code"
SPLIT = "split"
GRADES = ["a", "b", "c", "d", "e"]

# Split train / test : graine fixe (écrite dans le schéma) et part de test, la même pour chaque grade
SPLIT_SEED = 42
TEST_FRACTION = 0.2
TRAIN, TEST = "train", "test"

# Ratios calculés dans la requête : nom -> description (les noms sont importés par src/ml/features.py)
RATIOS = {
    "sugars_carbohydrates_ratio": "part des sucres dans les glucides",
    "saturated_fat_ratio": "part des acides gras saturés dans les lipides",
    "fat_energy_ratio": "part de l'énergie apportée par les lipides (9 kcal/g)",
}
RATIO_MAX = 1.0

# Colonnes de l'export dans l'ordre
COLUMNS = {
    "code": ("VARCHAR", None, "code-barres (texte, zéros de tête conservés)", "identifiant"),
    "aisle": ("VARCHAR", None, "rayon : slug de food_groups_tag_1, unknown si absent", "feature"),
    "aisle2": ("VARCHAR", None, "sous-groupe : slug de food_groups_tag_2, unknown si absent", "feature"),
    "energy_kcal_100g": ("DOUBLE", "kcal/100 g", "énergie", "feature"),
    "fat_100g": ("DOUBLE", "g/100 g", "lipides", "feature"),
    "saturated_fat_100g": ("DOUBLE", "g/100 g", "acides gras saturés", "feature"),
    "carbohydrates_100g": ("DOUBLE", "g/100 g", "glucides", "feature"),
    "sugars_100g": ("DOUBLE", "g/100 g", "sucres", "feature"),
    "proteins_100g": ("DOUBLE", "g/100 g", "protéines", "feature"),
    "salt_100g": ("DOUBLE", "g/100 g", "sel", "feature"),
    "fiber_100g": ("DOUBLE", "g/100 g", "fibres", "feature"),
    "fruits_vegetables_legumes_100g": ("DOUBLE", "g/100 g", "fruits, légumes et légumineuses", "feature"),
    "additives_n": ("SMALLINT", "nombre", "nombre d'additifs", "feature"),
    "nova_group": ("TINYINT", "groupe 1 à 4", "degré de transformation NOVA", "feature"),
    "sugars_carbohydrates_ratio": ("DOUBLE", "ratio 0 à 1", RATIOS["sugars_carbohydrates_ratio"], "feature"),
    "saturated_fat_ratio": ("DOUBLE", "ratio 0 à 1", RATIOS["saturated_fat_ratio"], "feature"),
    "fat_energy_ratio": ("DOUBLE", "ratio 0 à 1", RATIOS["fat_energy_ratio"], "feature"),
    "nutriscore_score": ("SMALLINT", "points", "score Nutri-Score dont le grade est déduit", "interdit"),
    "nutriscore_grade": ("VARCHAR", None, "grade Nutri-Score a à e", "cible"),
    SPLIT: ("VARCHAR", None, f"{TRAIN} ou {TEST} : split figé, stratifié sur le grade (graine {SPLIT_SEED})", "split"),
}

FILTERS = [
    "grade Nutri-Score connu (a à e)",
    *[f"{column} renseigné" for column in config.CORE_NUTRIENTS],
    "énergie strictement positive",
    f"sucres <= glucides + {cleaning.SUGARS_TOLERANCE} (garde-fou, tolérance du nettoyage)",
    f"saturés <= lipides + {cleaning.SATURATED_TOLERANCE} (garde-fou, tolérance du nettoyage)",
]

USAGE = {
    "prevu": "entraînement et évaluation d'un modèle prédisant nutriscore_grade sur le split de ce fichier",
    "interdits": [
        "recalculer le split : utiliser la colonne split telle quelle",
        "utiliser nutriscore_score comme feature : le grade en est déduit (fuite de la cible)",
        "utiliser code comme feature : identifiant, sans information nutritionnelle",
        "utiliser product_name ou brands comme features (absents de l'export)",
    ],
}
SPLIT_RULES = [
    "fit (modèle, imputation, normalisation) sur le train seulement",
    "le test n'est regardé qu'une fois, à la fin",
    "la validation croisée se fait à l'intérieur du train",
]
SPLIT_METHOD = (
    f"stratifié sur {TARGET} : sklearn.model_selection.train_test_split "
    "(stratify = grade, random_state = graine) appliqué aux produits triés par code"
)


def export_paths(out_dir: Path, frozen_on: date) -> tuple[Path, Path]:
    """(Parquet, schéma) de l'export daté : features_nutriscore_<AAAAMMJJ>.parquet et .schema.json."""
    stem = f"{EXPORT_PREFIX}_{frozen_on.strftime('%Y%m%d')}"
    return out_dir / f"{stem}.parquet", out_dir / f"{stem}.schema.json"


def _check_source(source: Path) -> None:
    """Lève FileNotFoundError si le dossier partitionné est absent ou incomplet (sans _SUCCESS)."""
    if not (source / SUCCESS_MARKER).exists():
        raise FileNotFoundError(
            f"Parquet partitionné absent ou incomplet (pas de {SUCCESS_MARKER}) : {display_path(source)} "
            "(lancer d'abord python -m nutriscope.pipeline parquet, qui appelle convert_parquet)"
        )


def _build_query(source: Path) -> str:
    """SELECT de l'export : produits utilisables (FILTERS), colonnes typées, triés par code (sortie reproductible)."""
    pattern = sql_literal((source / "**" / "*.parquet").as_posix())
    return f"""
        SELECT
            code,
            aisle,
            {aisle_slug_sql("food_groups_tag_2")} AS aisle2,
            energy_kcal_100g,
            fat_100g,
            saturated_fat_100g,
            carbohydrates_100g,
            sugars_100g,
            proteins_100g,
            salt_100g,
            fiber_100g,
            fruits_vegetables_legumes_100g,
            additives_n,
            nova_group,
            CASE WHEN carbohydrates_100g = 0 THEN (CASE WHEN sugars_100g = 0 THEN 0.0 END)
                ELSE least(sugars_100g / carbohydrates_100g, 1.0) END AS sugars_carbohydrates_ratio,
            CASE WHEN fat_100g = 0 THEN (CASE WHEN saturated_fat_100g = 0 THEN 0.0 END)
                ELSE least(saturated_fat_100g / fat_100g, 1.0) END AS saturated_fat_ratio,
            CASE WHEN energy_kcal_100g = 0 THEN (CASE WHEN fat_100g = 0 THEN 0.0 END)
                ELSE least(9 * fat_100g / energy_kcal_100g, 1.0) END AS fat_energy_ratio,
            nutriscore_score,
            nutriscore_grade
        FROM read_parquet({pattern}, hive_partitioning = true)
        WHERE nutriscore_grade IN ('a', 'b', 'c', 'd', 'e')
          AND energy_kcal_100g IS NOT NULL
          AND fat_100g IS NOT NULL
          AND saturated_fat_100g IS NOT NULL
          AND carbohydrates_100g IS NOT NULL
          AND sugars_100g IS NOT NULL
          AND proteins_100g IS NOT NULL
          AND salt_100g IS NOT NULL
          AND energy_kcal_100g > 0
          AND sugars_100g <= carbohydrates_100g + {cleaning.SUGARS_TOLERANCE}
          AND saturated_fat_100g <= fat_100g + {cleaning.SATURATED_TOLERANCE}
        ORDER BY code
    """


def assign_split(codes: np.ndarray, grades: np.ndarray, seed: int = SPLIT_SEED,
                 test_fraction: float = TEST_FRACTION) -> np.ndarray:
    """train ou test pour chaque produit, stratifié sur le grade
    """
    if list(codes) != sorted(codes):
        raise ValueError("assign_split attend des produits triés par code (affectation reproductible)")
    split = np.full(len(codes), TRAIN, dtype=object)
    positions = np.arange(len(codes))
    # train ignoré, le tableau est déja remplis de TRAIN
    _, positions_test = train_test_split(
        positions, test_size=test_fraction, stratify=grades, random_state=seed
    )
    split[positions_test] = TEST
    return split


def _split_counts(con: duckdb.DuckDBPyConnection, table: str) -> dict[str, dict]:
    """Effectifs train et test par grade, et part de test en %, lus dans le fichier écrit"""
    rows = con.execute(
        f"SELECT {TARGET}, count(*) FILTER ({SPLIT} = '{TRAIN}'), count(*) FILTER ({SPLIT} = '{TEST}') "
        f"FROM read_parquet({table}) GROUP BY {TARGET} ORDER BY {TARGET}"
    ).fetchall()
    return {
        grade: {TRAIN: train, TEST: test, "test_pct": round(100 * test / (train + test), 2)}
        for grade, train, test in rows
    }


def _write_schema(con, path: Path, export: Path, source: Path, frozen_on: date) -> dict:
    """Écrit le schéma de l'export et le renvoie"""
    table = sql_literal(export.as_posix())
    rows = con.execute(f"SELECT count(*) FROM read_parquet({table})").fetchone()[0]
    missing = con.execute(
        "SELECT " + ", ".join(f"count(*) - count({name})" for name in COLUMNS) + f" FROM read_parquet({table})"
    ).fetchone()
    distribution = dict(con.execute(
        f"SELECT {TARGET}, count(*) FROM read_parquet({table}) GROUP BY {TARGET} ORDER BY {TARGET}"
    ).fetchall())

    columns = []
    for (name, (sql_type, unit, description, role)), missing_count in zip(COLUMNS.items(), missing):
        columns.append({
            "name": name, "type": sql_type, "unit": unit, "description": description, "role": role,
            "missing_pct": round(100 * missing_count / rows, 2) if rows else 0.0,
        })
    schema = {
        "name": export.stem,
        "frozen_on": frozen_on.isoformat(),
        "source": display_path(source),
        "rows": rows,
        "sha256": file_sha256(export),
        "target": TARGET,
        "identifier": IDENTIFIER,
        "filters": FILTERS,
        "target_distribution": distribution,
        "split": {
            "column": SPLIT,
            "method": SPLIT_METHOD,
            "seed": SPLIT_SEED,
            "test_fraction": TEST_FRACTION,
            "counts": _split_counts(con, table),
            "rules": SPLIT_RULES,
        },
        "ratios": {
            "bornes": f"0 à {RATIO_MAX} ; 0 si numérateur et dénominateur valent 0 ; NULL si seul le dénominateur vaut 0",
        },
        "columns": columns,
        "usage": USAGE,
        "license": config.LICENSE,
    }
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return schema


def export(source: Path, out_dir: Path, frozen_on: date | None = None, force: bool = False) -> dict:
    """Écrit l'export features daté, avec son split, et son schéma ; renvoie le schéma.
    Le Parquet est écrit dans un fichier temporaire puis renommé : un export interrompu ne laisse pas de fichier.
    """
    _check_source(source)
    # date de gel, aujourd'hui par défaut
    frozen_on = frozen_on or today()
    parquet_path, schema_file = export_paths(out_dir, frozen_on)
    if parquet_path.exists() and not force:
        raise FileExistsError(f"Export déjà présent : {display_path(parquet_path)} (--force pour le réécrire)")

    out_dir.mkdir(parents=True, exist_ok=True)
    temporary = parquet_path.with_suffix(".parquet.tmp")
    with duckdb.connect() as con:
        con.execute(f"CREATE TEMP TABLE features AS {_build_query(source)}")
        selected = con.execute(f"SELECT {IDENTIFIER}, {TARGET} FROM features ORDER BY {IDENTIFIER}").fetchnumpy()
        split = assign_split(selected[IDENTIFIER], selected[TARGET])
        con.register("splits", pa.table({IDENTIFIER: selected[IDENTIFIER], SPLIT: split.astype(str)}))
        con.execute(
            f"COPY (SELECT f.*, s.{SPLIT} FROM features f JOIN splits s USING ({IDENTIFIER}) ORDER BY {IDENTIFIER}) "
            f"TO {sql_literal(temporary.as_posix())} (FORMAT PARQUET, {duckdb_parquet_options()})"
        )
        os.replace(temporary, parquet_path)
        return _write_schema(con, schema_file, parquet_path, source, frozen_on)


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Exporte les features datées pour prédire le Nutri-Score.")
    parser.add_argument("--source", type=Path, help="dossier Parquet partitionné (défaut : le plus récent)")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="dossier des exports")
    parser.add_argument("--force", action="store_true", help="réécrire l'export du jour s'il existe")
    args = parser.parse_args(argv)

    source = args.source or require_input(
        config.PARQUET_DIR, config.PRODUCTS_PREFIX, "", None, "python -m nutriscope.pipeline parquet", require_success=True
    )
    schema = export(source, args.out_dir, force=args.force)
    parquet_path, schema_file = export_paths(args.out_dir, date.fromisoformat(schema["frozen_on"]))
    print(f"{format_int(schema['rows'])} produits écrits dans {display_path(parquet_path)} ; "
          f"schéma : {display_path(schema_file)} ; SHA-256 : {schema['sha256']}")


if __name__ == "__main__":
    main()