"""Extraction de la table brute products_nutrition depuis le Parquet Open Food Facts (aucun nettoyage).

Une seule requête d'extraction pour tout le dépôt : make_sample_raw.py, le pipeline et le TP 12 la partagent.
Elle déplie les champs imbriqués (product_name, nutriments...) en colonnes plates, celles que lit cleaning.clean().

Deux formes de source sont acceptées (étape load du pipeline, TP 13) :
- imbriquée (data/food.parquet) : extraction par la requête ci-dessous, avec filtre pays éventuel ;
- déjà aplatie (l'échantillon data/raw/sample_raw.parquet) : recopiée telle quelle, colonnes dans l'ordre de
  COLUMNS ; le filtre pays y est impossible (countries_tags n'est pas extrait) et refusé.
La forme est reconnue aux noms de colonnes de la source.

Deux usages :
    python -m src.extract                          # fichier complet  -> data/raw/products_nutrition_<AAAAMMJJ>.parquet
    python -m src.extract --country en:france      # extrait France   -> data/raw/france_extract_<AAAAMMJJ>.parquet

À côté du brut, un manifeste <nom>.manifest.json : source, empreinte SHA-256 de la source et du brut, lignes,
horodatage. Le brut lui-même ne contient aucune date : relancé sur la même source, il est réécrit à l'identique
(l'ordre des lignes est celui de la source, conservé par DuckDB). Il reste BRUT : le nettoyage vient après.

Données : © Open Food Facts contributors — ODbL (rappel écrit dans les métadonnées du Parquet produit).
"""

import argparse
import datetime
import json
import os
from pathlib import Path

import duckdb

from src import config
from src.utils import (
    dated_path,
    display_path,
    duckdb_parquet_options,
    file_sha256,
    sql_literal,
    today,
)

DEFAULT_SOURCE = config.FOOD_PARQUET
FRANCE_TAG = "en:france"
NESTED_MARKER = "nutriments"   # colonne propre à la source imbriquée
NESTED = "imbriquée"
FLAT = "aplatie"

# Liste du SELECT : requête de la cartographie (3.2.2), complétée de additives_n et created_t (TP 12)
SELECT_SQL = """
    SELECT
        t.code,
        t.product_name[1].text AS product_name,
        NULLIF(t.brands, '') AS brands,
        t.categories_tags,
        t.compared_to_category AS main_category,
        t.food_groups_tags[1] AS food_groups_tag_1,
        array_to_string(t.allergens_tags, ',') AS allergens,
        t.ingredients_text[1].text AS ingredients_text,
        t.additives_n,
        t.nova_group,
        t.nutriscore_score,
        t.nutriscore_grade,
        t.serving_size,
        t.completeness,
        t.created_t,
        t.last_modified_t,
        list_filter(t.nutriments, x -> x.name = 'energy-kcal')[1]."100g" AS energy_kcal_100g,
        COALESCE(
            list_filter(t.nutriments, x -> x.name = 'energy-kj')[1]."100g",
            list_filter(t.nutriments, x -> x.name = 'energy')[1]."100g"
        ) AS energy_kj_100g,
        list_filter(t.nutriments, x -> x.name = 'fat')[1]."100g" AS fat_100g,
        list_filter(t.nutriments, x -> x.name = 'saturated-fat')[1]."100g" AS saturated_fat_100g,
        list_filter(t.nutriments, x -> x.name = 'carbohydrates')[1]."100g" AS carbohydrates_100g,
        list_filter(t.nutriments, x -> x.name = 'sugars')[1]."100g" AS sugars_100g,
        list_filter(t.nutriments, x -> x.name = 'fiber')[1]."100g" AS fiber_100g,
        list_filter(t.nutriments, x -> x.name = 'proteins')[1]."100g" AS proteins_100g,
        list_filter(t.nutriments, x -> x.name = 'salt')[1]."100g" AS salt_100g,
        list_filter(t.nutriments, x -> x.name = 'sodium')[1]."100g" AS sodium_100g,
        list_filter(t.nutriments, x -> x.name = 'fruits-vegetables-legumes')[1]."100g"
            AS fruits_vegetables_legumes_100g
    FROM read_parquet({source}) AS t
"""

# Colonnes produites, dans l'ordre du SELECT (référence pour les tests et les scripts en aval)
COLUMNS = [
    "code", "product_name", "brands", "categories_tags", "main_category", "food_groups_tag_1",
    "allergens", "ingredients_text", "additives_n", "nova_group", "nutriscore_score",
    "nutriscore_grade", "serving_size", "completeness", "created_t", "last_modified_t",
    "energy_kcal_100g", "energy_kj_100g", "fat_100g", "saturated_fat_100g", "carbohydrates_100g",
    "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g", "sodium_100g",
    "fruits_vegetables_legumes_100g",
]


def _build_query(source: Path, country: str | None = None) -> str:
    """Requête d'extraction ; `country` (tag OFF, ex. « en:france ») ne garde que les produits vendus dans ce pays."""
    query = SELECT_SQL.format(source=sql_literal(source.as_posix()))
    if country:
        query += f"    WHERE list_contains(t.countries_tags, {sql_literal(country)})\n"
    return query


def _flat_query(source: Path) -> str:
    """Recopie d'une source déjà aplatie : les colonnes de COLUMNS, dans cet ordre (une colonne en trop est ignorée)."""
    return f"SELECT {', '.join(COLUMNS)} FROM read_parquet({sql_literal(source.as_posix())})"


def source_format(con: duckdb.DuckDBPyConnection, source: Path) -> str:
    """NESTED si la source a les champs imbriqués d'Open Food Facts, FLAT si elle a déjà toutes les colonnes de COLUMNS.

    Lève ValueError si elle n'est ni l'une ni l'autre (colonnes manquantes listées).
    """
    rows = con.execute(f"DESCRIBE SELECT * FROM read_parquet({sql_literal(source.as_posix())})").fetchall()
    columns = {row[0] for row in rows}
    if NESTED_MARKER in columns:
        return NESTED
    missing = [column for column in COLUMNS if column not in columns]
    if missing:
        raise ValueError(
            f"Source ni imbriquée (pas de colonne {NESTED_MARKER}) ni aplatie (colonnes absentes : {', '.join(missing)}) : "
            f"{display_path(source)}"
        )
    return FLAT


def create_raw_table(
    con: duckdb.DuckDBPyConnection, source: Path, table: str = config.RAW_TABLE, country: str | None = None
) -> None:
    """Crée la table brute `table` dans la connexion (utilisé par make_sample_raw.py, source imbriquée)."""
    con.execute(f"CREATE TABLE {table} AS {_build_query(source, country)}")


def manifest_path(output: Path) -> Path:
    """Manifeste du brut : à côté de lui, même nom suivi de .manifest.json."""
    return output.with_name(output.stem + ".manifest.json")


def _write_manifest(source: Path, output: Path, shape: str, country: str | None, rows: int) -> Path:
    """Écrit le manifeste : d'où vient le brut (source et son empreinte), ce qu'il contient, quand il a été écrit."""
    manifest = {
        "name": output.name,
        "written_at": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "source": display_path(source),
        "source_format": shape,
        "source_bytes": source.stat().st_size,
        "source_sha256": file_sha256(source),
        "country": country,
        "rows": rows,
        "sha256": file_sha256(output),
        "columns": COLUMNS,
        "license": config.LICENSE,
    }
    path = manifest_path(output)
    path.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return path


def extract(source: Path, output: Path, country: str | None = None) -> int:
    """Écrit la table brute en Parquet (ZSTD, licence en métadonnées) et son manifeste ; renvoie le nombre de lignes.

    Le brut est écrit dans un fichier temporaire renommé à la fin : une interruption ne laisse jamais un brut à
    moitié écrit sous le nom attendu, et relancer remplace la sortie précédente. Lève FileNotFoundError si la
    source n'existe pas, ValueError si un filtre pays est demandé sur une source déjà aplatie.
    """
    if not source.exists():
        raise FileNotFoundError(f"Parquet source introuvable : {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    temporary = output.with_name(output.name + ".tmp")

    with duckdb.connect() as con:
        shape = source_format(con, source)
        if shape == FLAT and country:
            raise ValueError(
                f"Source déjà aplatie ({display_path(source)}) : le filtre pays {country} est impossible "
                "(lancer sur l'échantillon avec --sample, ou sur une source aplatie avec --full)"
            )
        query = _flat_query(source) if shape == FLAT else _build_query(source, country)
        con.execute(f"COPY ({query}) TO {sql_literal(temporary.as_posix())} (FORMAT PARQUET, {duckdb_parquet_options()})")
        os.replace(temporary, output)
        rows = con.execute(f"SELECT count(*) FROM read_parquet({sql_literal(output.as_posix())})").fetchone()[0]

    _write_manifest(source, output, shape, country, rows)
    return rows


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extrait la table brute products_nutrition du Parquet OFF.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Parquet Open Food Facts")
    parser.add_argument("--country", help=f"tag pays à garder (ex. {FRANCE_TAG}) ; absent = tout le fichier")
    parser.add_argument("--out", type=Path, help="Parquet de sortie (défaut : daté du jour, selon --country)")
    args = parser.parse_args(argv)

    if args.out is None and args.country not in (None, FRANCE_TAG):
        parser.error(f"--out est obligatoire pour un autre pays que {FRANCE_TAG}")
    prefix = config.FRANCE_EXTRACT_PREFIX if args.country else config.FULL_RAW_PREFIX
    output = args.out or dated_path(config.RAW_DIR, prefix, today(), ".parquet")
    count = extract(args.source, output, args.country)
    print(f"{count} lignes écrites dans {display_path(output)} ; manifeste : {display_path(manifest_path(output))}")


if __name__ == "__main__":
    main()