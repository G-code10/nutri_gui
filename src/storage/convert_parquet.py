"""Conversion du nettoyé en Parquet partitionné par rayon (TP 12, étape 1).

Entrée : le Parquet nettoyé (sortie de cleaning.clean(), écrite par le pipeline).
Sortie : data/parquet/produits/aisle=<slug>/…, types posés dans le SELECT, compression ZSTD,
         puis data/parquet/schema_produits.json à côté, puis le marqueur _SUCCESS en dernier.

Rejouable : le dossier cible est supprimé avant l'écriture (aucune partition orpheline), et les lignes
sont triées avant l'écriture (mêmes données en entrée = mêmes fichiers en sortie).
Les chemins sont des paramètres : les valeurs par défaut ne servent qu'en ligne de commande.

Usage (depuis la racine du dépôt) :
    python -m src.storage.convert_parquet
    python -m src.storage.convert_parquet --source data/clean/products_clean.parquet --out data/parquet/produits

Données : © Open Food Facts contributors — ODbL (rappel écrit dans les Parquet et dans le schéma).
"""

import argparse
import json
import shutil
from datetime import date
from pathlib import Path

import duckdb

from src import cleaning, config
from src.config import COMPRESSION, LICENSE, UNKNOWN_AISLE
from src.utils import display_path, duckdb_parquet_options, sql_literal

DEFAULT_SOURCE = config.CLEAN_PATH
DEFAULT_OUTPUT = config.PRODUCTS_PARQUET_DIR
SCHEMA_FILENAME = "schema_produits.json"
SUCCESS_MARKER = "_SUCCESS"

PARTITION_KEY = "aisle"

# Rayon = slug de food_groups_tag_1 (équivalent de pnns_groups_1) ; NULL ou vide -> unknown
AISLE_SQL = (
    "lower(regexp_replace(coalesce(nullif(trim(food_groups_tag_1), ''), "
    f"'{UNKNOWN_AISLE}'), '[^A-Za-z0-9]+', '-', 'g'))"
)

_NUTRIENT_REASON = "float64 comme cleaning.py et la base (DOUBLE PRECISION) : aucun arrondi, bornes comparées à l'identique"
_TEXT_REASON = "texte libre"

# Colonnes attendues du nettoyé : nom -> (expression SQL de typage, type, justification)
COLUMN_SPECS = {
    "code": ("CAST(code AS VARCHAR)", "VARCHAR", "code-barres en texte : un entier perdrait les zéros de tête"),
    "product_name": ("CAST(product_name AS VARCHAR)", "VARCHAR", _TEXT_REASON),
    "brands": ("CAST(brands AS VARCHAR)", "VARCHAR", _TEXT_REASON),
    "categories_tags": ("CAST(categories_tags AS VARCHAR[])", "VARCHAR[]", "liste de tags conservée telle quelle pour l'analyse"),
    "main_category": ("CAST(main_category AS VARCHAR)", "VARCHAR", "tag de catégorie"),
    "food_groups_tag_1": ("CAST(food_groups_tag_1 AS VARCHAR)", "VARCHAR", "tag d'origine du rayon, gardé à côté de son slug"),
    "allergens": ("CAST(allergens AS VARCHAR)", "VARCHAR", "NULL = inconnu, '' = aucun allergène déclaré"),
    "ingredients_text": ("CAST(ingredients_text AS VARCHAR)", "VARCHAR", _TEXT_REASON),
    "additives_n": ("CAST(additives_n AS SMALLINT)", "SMALLINT", "nombre d'additifs : entier petit, 2 octets suffisent"),
    "nova_group": ("CAST(nova_group AS TINYINT)", "TINYINT", "valeurs 1 à 4 : 1 octet suffit"),
    "nutriscore_score": ("CAST(nutriscore_score AS SMALLINT)", "SMALLINT", "score entier borné (-17 à 55 observés)"),
    "nutriscore_grade": ("CAST(nutriscore_grade AS VARCHAR)", "VARCHAR", "cible : a-e, ou NULL (unknown et not-applicable effacés au nettoyage)"),
    "serving_size": ("CAST(serving_size AS VARCHAR)", "VARCHAR", "texte libre (unités variables)"),
    "completeness": ("CAST(completeness AS DOUBLE)", "DOUBLE", "taux de complétude OFF, même type que la base"),
    "created_t": ("make_timestamp(CAST(created_t AS BIGINT) * 1000000)", "TIMESTAMP", "secondes Unix converties en date, sans fuseau (UTC)"),
    "last_modified_t": ("make_timestamp(CAST(last_modified_t AS BIGINT) * 1000000)", "TIMESTAMP", "secondes Unix converties en date, sans fuseau (UTC)"),
    # Les 11 nutriments bornés par le nettoyage (clés de cleaning.RANGES)
    **{column: (f"CAST({column} AS DOUBLE)", "DOUBLE", _NUTRIENT_REASON) for column in cleaning.RANGES},
    "grade_not_applicable": ("CAST(grade_not_applicable AS BOOLEAN)", "BOOLEAN", "drapeau du nettoyage : grade « not-applicable » avant effacement"),
}

# Drapeaux <col>_missing posés par le nettoyage : typés BOOLEAN sans être listés un par un
FLAG_SUFFIX = "_missing"
FLAG_REASON = "drapeau de manquant posé par le nettoyage (missing_strategy)"


def _source_columns(con: duckdb.DuckDBPyConnection, source: Path) -> list[str]:
    """Colonnes du Parquet nettoyé, dans leur ordre."""
    rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet({sql_literal(source.as_posix())})").fetchall()
    return [row[0] for row in rows]


def _typed_columns(columns: list[str]) -> list[tuple[str, str, str, str]]:
    """(nom, expression SQL, type, justification) pour chaque colonne, dans l'ordre de la source.

    Lève ValueError si une colonne attendue manque, ou si une colonne inconnue (hors drapeaux) apparaît :
    toute nouvelle colonne doit recevoir un type justifié dans COLUMN_SPECS.
    """
    missing = [column for column in COLUMN_SPECS if column not in columns]
    if missing:
        raise ValueError(f"Colonnes absentes du nettoyé : {', '.join(missing)}")
    unknown = [c for c in columns if c not in COLUMN_SPECS and not c.endswith(FLAG_SUFFIX)]
    if unknown:
        raise ValueError(f"Colonnes sans type déclaré dans COLUMN_SPECS : {', '.join(unknown)}")

    typed = []
    for column in columns:
        if column in COLUMN_SPECS:
            expression, sql_type, reason = COLUMN_SPECS[column]
        else:
            expression, sql_type, reason = f"CAST({column} AS BOOLEAN)", "BOOLEAN", FLAG_REASON
        typed.append((column, expression, sql_type, reason))
    return typed


def _build_query(source: Path, typed: list[tuple[str, str, str, str]]) -> str:
    """SELECT typé + colonne aisle, trié par rayon puis code (ordre total, sortie reproductible)."""
    select_list = ",\n        ".join(f"{expression} AS {name}" for name, expression, _, _ in typed)
    return (
        f"SELECT\n        {select_list},\n        {AISLE_SQL} AS {PARTITION_KEY}\n"
        f"    FROM read_parquet({sql_literal(source.as_posix())})\n"
        f"    ORDER BY {PARTITION_KEY}, code"
    )


def schema_path(output: Path) -> Path:
    """Emplacement du schéma : à côté du dossier partitionné."""
    return output.parent / SCHEMA_FILENAME


def _write_schema(output: Path, source: Path, typed: list, row_count: int, aisles: list[str]) -> Path:
    """Écrit schema_produits.json : colonnes (type + justification), partition, compression, volumes, licence."""
    columns = [{"name": name, "type": sql_type, "justification": reason} for name, _, sql_type, reason in typed]
    columns.append({
        "name": PARTITION_KEY, "type": "VARCHAR",
        "justification": "slug de food_groups_tag_1 (unknown si vide) ; clé de partition, relue par hive_partitioning",
    })
    schema = {
        "name": output.name,
        "generated_on": date.today().isoformat(),
        "source": display_path(source),
        "partition_key": PARTITION_KEY,
        "partitions": aisles,
        "compression": COMPRESSION,
        "row_count": row_count,
        "columns": columns,
        "license": LICENSE,
    }
    path = schema_path(output)
    path.write_text(json.dumps(schema, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def convert(source: Path, output: Path) -> int:
    """Convertit le nettoyé en Parquet partitionné par aisle ; renvoie le nombre de lignes écrites.

    Ordre d'écriture : dossier supprimé, partitions, schéma, puis _SUCCESS en dernier (un dossier sans
    marqueur est incomplet). Lève FileNotFoundError si la source n'existe pas.
    """
    if not source.exists():
        raise FileNotFoundError(f"Nettoyé introuvable : {source} (lancer d'abord le pipeline de nettoyage)")

    with duckdb.connect() as con:
        typed = _typed_columns(_source_columns(con, source))

        if output.exists():
            shutil.rmtree(output)
        output.parent.mkdir(parents=True, exist_ok=True)

        con.execute(
            f"COPY ({_build_query(source, typed)}) TO {sql_literal(output.as_posix())} "
            f"(FORMAT PARQUET, PARTITION_BY ({PARTITION_KEY}), OVERWRITE_OR_IGNORE, {duckdb_parquet_options()})"
        )

        pattern = sql_literal((output / "**" / "*.parquet").as_posix())
        row_count, aisles = con.execute(
            f"SELECT count(*), list(DISTINCT {PARTITION_KEY} ORDER BY {PARTITION_KEY}) "
            f"FROM read_parquet({pattern}, hive_partitioning = true)"
        ).fetchone()

    _write_schema(output, source, typed, row_count, aisles)
    (output / SUCCESS_MARKER).write_text("", encoding="utf-8")
    return row_count


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Convertit le nettoyé en Parquet partitionné par rayon.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Parquet nettoyé")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="dossier partitionné de sortie")
    args = parser.parse_args(argv)

    count = convert(args.source, args.out)
    print(f"{count} lignes écrites dans {args.out} ; schéma : {schema_path(args.out)}")


if __name__ == "__main__":
    main()