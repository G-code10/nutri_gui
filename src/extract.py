"""Extraction de la table brute products_nutrition depuis le Parquet Open Food Facts (aucun nettoyage).

Une seule requête d'extraction pour tout le dépôt : make_sample_raw.py, le pipeline et le TP 12 la partagent.
Elle déplie les champs imbriqués (product_name, nutriments...) en colonnes plates, celles que lit cleaning.clean().

Deux usages :
    python -m src.extract                          # fichier complet  -> data/raw/products_nutrition.parquet
    python -m src.extract --country en:france      # extrait France   -> data/raw/extrait_france.parquet

La sortie est réécrite à chaque lancement (rejouable). Elle reste BRUTE : le nettoyage vient après.

Données : © Open Food Facts contributors — ODbL (rappel écrit dans les métadonnées du Parquet produit).
"""

import argparse
from pathlib import Path

import duckdb

from src import config
from src.utils import duckdb_parquet_options, sql_literal

DEFAULT_SOURCE = config.FOOD_PARQUET
DEFAULT_OUTPUT = config.RAW_PATH
DEFAULT_COUNTRY_OUTPUT = config.FRANCE_EXTRACT_PATH
FRANCE_TAG = "en:france"

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


def create_raw_table(
    con: duckdb.DuckDBPyConnection, source: Path, table: str = config.RAW_TABLE, country: str | None = None
) -> None:
    """Crée la table brute `table` dans la connexion (utilisé par make_sample_raw.py)."""
    con.execute(f"CREATE TABLE {table} AS {_build_query(source, country)}")


def extract(source: Path, output: Path, country: str | None = None) -> int:
    """Écrit la table brute en Parquet (ZSTD, licence en métadonnées) ; renvoie le nombre de lignes écrites.

    Le fichier de sortie est supprimé avant l'écriture : relancer donne le même résultat, sans reste d'un
    lancement précédent. Lève FileNotFoundError si la source n'existe pas.
    """
    if not source.exists():
        raise FileNotFoundError(f"Parquet source introuvable : {source}")
    output.parent.mkdir(parents=True, exist_ok=True)
    output.unlink(missing_ok=True)

    with duckdb.connect() as con:
        con.execute(
            f"COPY ({_build_query(source, country)}) TO {sql_literal(output.as_posix())} "
            f"(FORMAT PARQUET, {duckdb_parquet_options()})"
        )
        return con.execute(f"SELECT count(*) FROM read_parquet({sql_literal(output.as_posix())})").fetchone()[0]


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Extrait la table brute products_nutrition du Parquet OFF.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="Parquet Open Food Facts")
    parser.add_argument("--country", help=f"tag pays à garder (ex. {FRANCE_TAG}) ; absent = tout le fichier")
    parser.add_argument("--out", type=Path, help="Parquet de sortie (défaut selon --country)")
    args = parser.parse_args(argv)

    output = args.out or (DEFAULT_COUNTRY_OUTPUT if args.country else DEFAULT_OUTPUT)
    count = extract(args.source, output, args.country)
    print(f"{count} lignes écrites dans {output}")


if __name__ == "__main__":
    main()