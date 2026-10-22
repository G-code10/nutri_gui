"""Fonctions utilitaires partagées par plusieurs modules du dépôt.

Règle d'entrée : une fonction n'arrive ici que si au moins deux modules s'en servent ; sinon elle reste,
privée (_), dans le module qui l'utilise. Les fonctions d'ici sont publiques : elles sont faites pour être importées.
"""

from pathlib import Path

import pandas as pd

from src import config


def sql_literal(value: str) -> str:
    """Chaîne SQL entre apostrophes, apostrophes internes doublées : « d'O'Neil » devient 'd''O''Neil'.

    À utiliser pour tout texte (chemin, tag, licence) inséré dans une requête DuckDB.
    """
    return "'" + value.replace("'", "''") + "'"


def display_path(path: Path) -> str:
    """Chemin relatif à la racine du dépôt quand c'est possible, sinon le seul nom du fichier.

    Sert dans les rapports et les schémas écrits : ils ne contiennent jamais le chemin absolu d'un poste.
    """
    path = Path(path).resolve()
    return path.relative_to(config.ROOT).as_posix() if path.is_relative_to(config.ROOT) else path.name


def aisle_slug_sql(column: str) -> str:
    """Expression SQL du slug de rayon (DuckDB et PostgreSQL) : « en:fruits-and-vegetables » -> « en-fruits-and-vegetables ».

    NULL, vide ou espaces -> UNKNOWN_AISLE ; minuscules ; toute suite de caractères non alphanumériques -> « - ».
    C'est la clé de partition du Parquet (convert_parquet), recalculée côté base pour comparer (run_queries).
    """
    return (
        f"lower(regexp_replace(coalesce(nullif(trim({column}), ''), "
        f"'{config.UNKNOWN_AISLE}'), '[^A-Za-z0-9]+', '-', 'g'))"
    )


def aisle_code(food_groups_tag_1: pd.Series) -> pd.Series:
    """Rayon de chaque produit : son tag food_groups_tag_1, ou UNKNOWN_AISLE si le tag est NULL ou vide.

    Le tag est gardé tel quel (« en:fruits-and-vegetables ») : c'est le code de rayon de la base.
    Le slug des partitions Parquet (« en-fruits-and-vegetables ») est calculé à part, en SQL : aisle_slug_sql.
    """
    return food_groups_tag_1.astype("string").replace("", pd.NA).fillna(config.UNKNOWN_AISLE)


def duckdb_parquet_options() -> str:
    """Options communes d'un COPY ... TO ... (FORMAT PARQUET, ...) en DuckDB : compression, puis licence en métadonnées.

    Exemple : f"COPY ({query}) TO {sql_literal(path)} (FORMAT PARQUET, {duckdb_parquet_options()})"
    """
    return f"COMPRESSION {config.COMPRESSION.upper()}, KV_METADATA {{license: {sql_literal(config.LICENSE)}}}"


def format_int(number) -> str:
    """Entier avec une espace entre les milliers : 12345 devient « 12 345 »."""
    return f"{int(number):,}".replace(",", " ")


def markdown_table(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown : une ligne d'en-tête, une ligne de séparation, puis une ligne par élément de `rows`."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)