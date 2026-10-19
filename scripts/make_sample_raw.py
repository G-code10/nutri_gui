"""Extrait de la table brute un petit échantillon parquet pour les tests d'idempotence.

La table brute products_nutrition est reconstruite à partir de data/food.parquet avec la
requête de la cartographie (3.2.2), dans une base temporaire supprimée à la fin.
L'échantillon reste BRUT (aucun nettoyage) : le test applique clean() lui-même.
Il est reproductible : même parquet + même graine = mêmes lignes, sur toutes les machines.

Usage (depuis la racine du dépôt) :
    python scripts/make_sample_raw.py
    python scripts/make_sample_raw.py --parquet chemin/vers/food.parquet --rows 2000
"""

import argparse
import tempfile
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_PARQUET = ROOT / "data" / "food.parquet"
DEFAULT_OUT = ROOT / "data" / "sample_raw.parquet"
DEFAULT_TABLE = "products_nutrition"
DEFAULT_ROWS = 5000
ANOMALY_ROWS = 100  # lignes ajoutées par type d'anomalie, pour que le test ait de quoi nettoyer

# Requête de création de la cartographie (3.2.2), recopiée telle quelle sauf le chemin du parquet
CREATE_TABLE_SQL = """
    CREATE TABLE {table} AS
    SELECT
        t.code,
        t.product_name[1].text AS product_name,
        NULLIF(t.brands, '') AS brands,
        t.categories_tags,
        t.compared_to_category AS main_category,
        t.food_groups_tags[1] AS food_groups_tag_1,
        array_to_string(t.allergens_tags, ',') AS allergens,
        t.ingredients_text[1].text AS ingredients_text,
        t.nova_group,
        t.nutriscore_score,
        t.nutriscore_grade,
        t.serving_size,
        t.completeness,
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
    FROM '{parquet}' AS t
"""

# Colonnes lues par clean() ; last_modified_t est facultative (départage des doublons)
REQUIRED_COLUMNS = [
    "code", "product_name", "brands", "ingredients_text", "allergens", "serving_size",
    "energy_kcal_100g", "energy_kj_100g", "fat_100g", "saturated_fat_100g",
    "carbohydrates_100g", "sugars_100g", "fiber_100g", "proteins_100g",
    "salt_100g", "sodium_100g", "fruits_vegetables_legumes_100g", "completeness",
    "nutriscore_score", "nutriscore_grade", "nova_group",
    "food_groups_tag_1", "categories_tags",
]
OPTIONAL_COLUMNS = ["last_modified_t"]

# Une condition SQL par type d'anomalie à représenter dans l'échantillon
ANOMALY_FILTERS = {
    "énergie > 900 kcal": "energy_kcal_100g > 900",
    "sucres > 100 g": "sugars_100g > 100",
    "sel > 100 g": "salt_100g > 100",
    "sucres > glucides": "sugars_100g > carbohydrates_100g + 0.5",
    "saturées > lipides": "saturated_fat_100g > fat_100g + 0.5",
    "énergie nulle avec lipides": "energy_kcal_100g = 0 AND fat_100g > 0",
    "sans catégorie": "categories_tags IS NULL OR len(categories_tags) = 0",
    "code avec espaces": "code <> trim(code)",
    "nom en majuscules": "product_name = upper(product_name) AND product_name <> lower(product_name)",
}


def create_raw_table(con: duckdb.DuckDBPyConnection, parquet: Path, table: str) -> None:
    """Construit la table brute à partir du parquet OpenFoodFacts."""
    con.execute(CREATE_TABLE_SQL.format(table=table, parquet=parquet.as_posix()))


def select_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Vérifie que les colonnes nécessaires existent et renvoie celles à extraire."""
    available = {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}
    missing = [column for column in REQUIRED_COLUMNS if column not in available]
    if missing:
        raise SystemExit(f"Colonnes absentes de {table} : {', '.join(missing)}")
    return REQUIRED_COLUMNS + [column for column in OPTIONAL_COLUMNS if column in available]


def build_query(table: str, columns: list[str], rows: int) -> str:
    """Échantillon déterministe : lignes triées par empreinte du code, plus des lignes anormales."""
    column_list = ", ".join(columns)
    # hash(code) puis code : ordre total et stable, les doublons d'un même code restent voisins
    random_part = f"""
        SELECT {column_list} FROM {table}
        WHERE code IN (
            SELECT DISTINCT code FROM {table}
            WHERE code IS NOT NULL
            ORDER BY hash(code), code
            LIMIT {rows}
        )"""
    anomaly_parts = [
        f"""
        SELECT {column_list} FROM {table}
        WHERE code IN (
            SELECT code FROM {table}
            WHERE code IS NOT NULL AND ({condition})
            ORDER BY hash(code), code
            LIMIT {ANOMALY_ROWS}
        )"""
        for condition in ANOMALY_FILTERS.values()
    ]
    duplicate_part = f"""
        SELECT {column_list} FROM {table}
        WHERE code IN (
            SELECT code FROM {table}
            WHERE code IS NOT NULL
            GROUP BY code HAVING count(*) > 1
            ORDER BY hash(code), code
            LIMIT {ANOMALY_ROWS}
        )"""
    # UNION (sans ALL) retire les lignes identiques présentes dans plusieurs parties
    return "\nUNION\n".join([random_part, duplicate_part, *anomaly_parts])


def main() -> None:
    parser = argparse.ArgumentParser(description="Extrait un échantillon brut de la table produits.")
    parser.add_argument("--parquet", type=Path, default=DEFAULT_PARQUET, help="parquet OpenFoodFacts")
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="codes tirés au hasard")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    if not args.parquet.exists():
        raise SystemExit(f"Parquet introuvable : {args.parquet}")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # Base temporaire sur disque (et non en mémoire) : le dépliage de nutriments est gourmand
    with tempfile.TemporaryDirectory(ignore_cleanup_errors=True) as tmp:
        con = duckdb.connect(str(Path(tmp) / "raw.duckdb"))
        create_raw_table(con, args.parquet, args.table)
        columns = select_columns(con, args.table)
        query = build_query(args.table, columns, args.rows)
        # ORDER BY ALL : tri sur toutes les colonnes, donc ordre total et fichier identique d'un lancement à l'autre
        con.execute(
            f"COPY (SELECT * FROM ({query}) ORDER BY ALL) "
            f"TO '{args.out.as_posix()}' (FORMAT parquet)"
        )
        con.close()

    count = duckdb.sql(f"SELECT count(*) FROM read_parquet('{args.out.as_posix()}')").fetchone()[0]
    print(f"{count} lignes écrites dans {args.out}")


if __name__ == "__main__":
    main()