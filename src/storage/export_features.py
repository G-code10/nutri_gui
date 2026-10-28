"""Export features daté pour prédire le Nutri-Score (TP 12, étape 5).

Entrée : le Parquet partitionné par rayon (convert_parquet), refusé s'il n'a pas son marqueur _SUCCESS.
Sortie : data/exports/features_nutriscore_<AAAAMMJJ>.parquet et features_nutriscore_<AAAAMMJJ>.schema.json.

Un export est figé : il n'est jamais réécrit sans --force (un jeu d'entraînement qui change en silence
rendrait les modèles incomparables). Réécrit avec --force à partir des mêmes données, il est identique
octet pour octet (même SHA-256) : lignes triées par code, aucune date dans les données, licence en métadonnées.
Le découpage entraînement / test n'est pas fait ici (TP 13).

Usage (depuis la racine du dépôt) :
    python -m src.storage.export_features
    python -m src.storage.export_features --source data/parquet/produits --out-dir data/exports --force

Données : © Open Food Facts contributors — ODbL (rappel écrit dans le Parquet et dans le schéma).
"""

import argparse
import hashlib
import json
import os
import subprocess
from datetime import date, datetime
from pathlib import Path

import duckdb

from src import cleaning, config
from src.storage.convert_parquet import PARTITION_KEY, SUCCESS_MARKER
from src.utils import display_path, duckdb_parquet_options, format_int, sql_literal

DEFAULT_SOURCE = config.PRODUCTS_PARQUET_DIR
DEFAULT_OUT_DIR = config.EXPORTS_DIR
EXPORT_PREFIX = "features_nutriscore"

TARGET = "nutriscore_grade"
IDENTIFIER = "code"
GRADES = ["a", "b", "c", "d", "e"]

# Ratios : nom -> (numérateur SQL, dénominateur SQL, description)
RATIOS = {
    "sugars_carbohydrates_ratio": ("sugars_100g", "carbohydrates_100g", "part des sucres dans les glucides"),
    "saturated_fat_ratio": ("saturated_fat_100g", "fat_100g", "part des acides gras saturés dans les lipides"),
    "fat_energy_ratio": ("9 * fat_100g", "energy_kcal_100g", "part de l'énergie apportée par les lipides (9 kcal/g)"),
}
RATIO_MAX = 1.0

_G = "g/100 g"

# Colonnes de l'export, dans l'ordre : nom -> (type, unité, description, rôle)
COLUMNS = {
    "code": ("VARCHAR", None, "code-barres (texte, zéros de tête conservés)", "identifiant"),
    "aisle": ("VARCHAR", None, "rayon : slug de food_groups_tag_1, unknown si absent", "feature"),
    "energy_kcal_100g": ("DOUBLE", "kcal/100 g", "énergie", "feature"),
    "fat_100g": ("DOUBLE", _G, "lipides", "feature"),
    "saturated_fat_100g": ("DOUBLE", _G, "acides gras saturés", "feature"),
    "carbohydrates_100g": ("DOUBLE", _G, "glucides", "feature"),
    "sugars_100g": ("DOUBLE", _G, "sucres", "feature"),
    "proteins_100g": ("DOUBLE", _G, "protéines", "feature"),
    "salt_100g": ("DOUBLE", _G, "sel", "feature"),
    "fiber_100g": ("DOUBLE", _G, "fibres", "feature"),
    "fruits_vegetables_legumes_100g": ("DOUBLE", _G, "fruits, légumes et légumineuses", "feature"),
    "additives_n": ("SMALLINT", "nombre", "nombre d'additifs", "feature"),
    "nova_group": ("TINYINT", "groupe 1 à 4", "degré de transformation NOVA", "feature"),
    **{name: ("DOUBLE", "ratio 0 à 1", description, "feature") for name, (_, _, description) in RATIOS.items()},
    "nutriscore_score": ("SMALLINT", "points", "score Nutri-Score dont le grade est déduit", "interdit"),
    "nutriscore_grade": ("VARCHAR", None, "grade Nutri-Score a à e", "cible"),
}

# Colonnes jamais manquantes : filtrées (nutriments clés, cible) ou toujours renseignées (code, rayon)
NEVER_MISSING = {IDENTIFIER, PARTITION_KEY, TARGET, *config.CORE_NUTRIENTS}
NEVER_MISSING_POLICY = "aucune : jamais manquante dans l'export"
DEFAULT_POLICY = "flag"   # colonnes absentes de cleaning.DEFAULT_MISSING_STRATEGY (additives_n, ratios)

FILTERS = [
    (f"{TARGET} IN ({', '.join(sql_literal(grade) for grade in GRADES)})", "grade Nutri-Score connu (a à e)"),
    *[(f"{column} IS NOT NULL", f"{column} renseigné") for column in config.CORE_NUTRIENTS],
    ("energy_kcal_100g > 0", "énergie strictement positive"),
    (
        f"sugars_100g <= carbohydrates_100g + {cleaning.SUGARS_TOLERANCE}",
        f"sucres <= glucides + {cleaning.SUGARS_TOLERANCE} (garde-fou, tolérance du nettoyage)",
    ),
    (
        f"saturated_fat_100g <= fat_100g + {cleaning.SATURATED_TOLERANCE}",
        f"saturés <= lipides + {cleaning.SATURATED_TOLERANCE} (garde-fou, tolérance du nettoyage)",
    ),
]

USAGE = {
    "prevu": "entraînement et évaluation d'un modèle prédisant nutriscore_grade (TP 14) ; découpage train / test au TP 13",
    "interdits": [
        "utiliser nutriscore_score comme feature : le grade en est déduit (fuite de la cible)",
        "utiliser code comme feature : identifiant, sans information nutritionnelle",
    ],
}


def export_paths(out_dir: Path, frozen_on: date) -> tuple[Path, Path]:
    """(Parquet, schéma) de l'export daté : features_nutriscore_<AAAAMMJJ>.parquet et .schema.json."""
    stem = f"{EXPORT_PREFIX}_{frozen_on.strftime('%Y%m%d')}"
    return out_dir / f"{stem}.parquet", out_dir / f"{stem}.schema.json"


def _check_source(source: Path) -> None:
    """Lève FileNotFoundError si le dossier partitionné est absent ou incomplet (sans _SUCCESS)."""
    if not (source / SUCCESS_MARKER).exists():
        raise FileNotFoundError(
            f"Parquet partitionné absent ou incomplet (pas de {SUCCESS_MARKER}) : {source} "
            "(lancer d'abord python -m src.storage.convert_parquet)"
        )


def _ratio_sql(numerator: str, denominator: str) -> str:
    """Ratio borné à [0, 1] : 0 si numérateur et dénominateur valent 0, NULL si seul le dénominateur vaut 0."""
    return (
        f"CASE WHEN {denominator} = 0 THEN (CASE WHEN {numerator} = 0 THEN 0.0 END) "
        f"ELSE least({numerator} / {denominator}, {RATIO_MAX}) END"
    )


def _select_list() -> str:
    """Expressions typées des colonnes de l'export, dans l'ordre de COLUMNS."""
    expressions = []
    for name, (sql_type, _, _, _) in COLUMNS.items():
        if name in RATIOS:
            numerator, denominator, _ = RATIOS[name]
            expression = _ratio_sql(numerator, denominator)
        else:
            expression = name
        expressions.append(f"CAST({expression} AS {sql_type}) AS {name}")
    return ",\n        ".join(expressions)


def _source_sql(source: Path) -> str:
    """Lecture du dossier partitionné, colonne aisle comprise (hive_partitioning)."""
    pattern = sql_literal((source / "**" / "*.parquet").as_posix())
    return f"read_parquet({pattern}, hive_partitioning = true)"


def _build_query(source: Path) -> str:
    """SELECT de l'export : produits utilisables (FILTERS), colonnes typées, triés par code (sortie reproductible)."""
    where = "\n      AND ".join(condition for condition, _ in FILTERS)
    return (
        f"SELECT\n        {_select_list()}\n"
        f"    FROM {_source_sql(source)}\n"
        f"    WHERE {where}\n"
        f"    ORDER BY {IDENTIFIER}"
    )


def _capped_counts(con: duckdb.DuckDBPyConnection, source: Path) -> dict[str, int]:
    """Nombre de produits retenus dont le ratio brut dépassait RATIO_MAX (ramené à RATIO_MAX)."""
    where = " AND ".join(condition for condition, _ in FILTERS)
    counts = ", ".join(
        f"count(*) FILTER ({numerator} / nullif({denominator}, 0) > {RATIO_MAX})"
        for numerator, denominator, _ in RATIOS.values()
    )
    row = con.execute(f"SELECT {counts} FROM {_source_sql(source)} WHERE {where}").fetchone()
    return dict(zip(RATIOS, row))


def _missing_policy(column: str) -> str:
    """Politique de manquants à appliquer au TP 14 : celle du nettoyage quand elle existe, sinon flag."""
    if column in NEVER_MISSING:
        return NEVER_MISSING_POLICY
    return cleaning.DEFAULT_MISSING_STRATEGY.get(column, DEFAULT_POLICY)


def _git(*args: str) -> str | None:
    """Sortie d'une commande git lancée à la racine du dépôt, ou None si git ou le dépôt est indisponible."""
    try:
        result = subprocess.run(["git", *args], cwd=config.ROOT, capture_output=True, text=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return None
    return result.stdout.strip()


def _sha256(path: Path) -> str:
    """Empreinte SHA-256 du fichier, lu par blocs."""
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _write_schema(con, path: Path, export: Path, source: Path, frozen_on: date, capped: dict[str, int]) -> dict:
    """Écrit le schéma de l'export (contrat du TP 14) et le renvoie."""
    table = sql_literal(export.as_posix())
    rows = con.execute(f"SELECT count(*) FROM read_parquet({table})").fetchone()[0]
    missing = con.execute(
        "SELECT " + ", ".join(f"count(*) - count({name})" for name in COLUMNS) + f" FROM read_parquet({table})"
    ).fetchone()
    distribution = dict(con.execute(
        f"SELECT {TARGET}, count(*) FROM read_parquet({table}) GROUP BY {TARGET} ORDER BY {TARGET}"
    ).fetchall())
    status = _git("status", "--porcelain")

    columns = []
    for (name, (sql_type, unit, description, role)), missing_count in zip(COLUMNS.items(), missing):
        columns.append({
            "name": name, "type": sql_type, "unit": unit, "description": description, "role": role,
            "missing_pct": round(100 * missing_count / rows, 2) if rows else 0.0,
            "missing_policy": _missing_policy(name),
        })
    schema = {
        "name": export.stem,
        "frozen_on": frozen_on.isoformat(),
        "source": display_path(source),
        "git_commit": _git("rev-parse", "HEAD"),
        "git_dirty": None if status is None else bool(status),
        "rows": rows,
        "sha256": _sha256(export),
        "target": TARGET,
        "identifier": IDENTIFIER,
        "filters": [description for _, description in FILTERS],
        "target_distribution": distribution,
        "ratios": {
            "bornes": f"0 à {RATIO_MAX} ; 0 si numérateur et dénominateur valent 0 ; NULL si seul le dénominateur vaut 0",
            "capped": capped,
        },
        "columns": columns,
        "usage": USAGE,
        "license": config.LICENSE,
    }
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return schema


def export(source: Path, out_dir: Path, frozen_on: date | None = None, force: bool = False) -> dict:
    """Écrit l'export features daté et son schéma ; renvoie le schéma.

    `frozen_on` : date de gel, aujourd'hui par défaut (elle nomme les fichiers, elle n'est pas dans les données).
    Lève FileNotFoundError si la source est incomplète, FileExistsError si l'export existe déjà sans `force`.
    Le Parquet est écrit dans un fichier temporaire puis renommé : un export interrompu ne laisse pas de fichier.
    """
    _check_source(source)
    frozen_on = frozen_on or datetime.now().astimezone().date()   # date locale
    parquet_path, schema_file = export_paths(out_dir, frozen_on)
    if parquet_path.exists() and not force:
        raise FileExistsError(f"Export déjà présent : {parquet_path} (--force pour le réécrire)")

    out_dir.mkdir(parents=True, exist_ok=True)
    temporary = parquet_path.with_suffix(".parquet.tmp")
    with duckdb.connect() as con:
        con.execute(
            f"COPY ({_build_query(source)}) TO {sql_literal(temporary.as_posix())} "
            f"(FORMAT PARQUET, {duckdb_parquet_options()})"
        )
        os.replace(temporary, parquet_path)
        return _write_schema(con, schema_file, parquet_path, source, frozen_on, _capped_counts(con, source))


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Exporte les features datées pour prédire le Nutri-Score.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="dossier Parquet partitionné")
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT_DIR, help="dossier des exports")
    parser.add_argument("--force", action="store_true", help="réécrire l'export du jour s'il existe")
    args = parser.parse_args(argv)

    schema = export(args.source, args.out_dir, force=args.force)
    parquet_path, schema_file = export_paths(args.out_dir, date.fromisoformat(schema["frozen_on"]))
    print(f"{format_int(schema['rows'])} produits écrits dans {display_path(parquet_path)} ; "
          f"schéma : {display_path(schema_file)} ; SHA-256 : {schema['sha256']}")


if __name__ == "__main__":
    main()