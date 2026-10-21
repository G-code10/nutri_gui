"""Extrait de la table brute un petit échantillon parquet pour les tests d'idempotence.

La table brute products_nutrition est reconstruite à partir de data/food.parquet avec la
requête d'extraction partagée (src/extract.py), dans une base temporaire supprimée à la fin.
L'échantillon reste BRUT (aucun nettoyage) : le test applique clean() lui-même.
Il est reproductible : même parquet + même graine = mêmes lignes, sur toutes les machines.

Usage (depuis la racine du dépôt, avec -m pour que « src » soit importable) :
    python -m scripts.make_sample_raw
    python -m scripts.make_sample_raw --parquet chemin/vers/food.parquet --rows 2000
"""

import argparse
import tempfile
from pathlib import Path

import duckdb

from src import cleaning, config
from src.extract import COLUMNS, create_raw_table
from src.utils import duckdb_parquet_options, sql_literal

DEFAULT_PARQUET = config.FOOD_PARQUET
DEFAULT_OUT = config.SAMPLE_RAW_PATH
DEFAULT_TABLE = config.RAW_TABLE
DEFAULT_ROWS = 5000
ANOMALY_ROWS = 100  # lignes ajoutées par type d'anomalie, pour que le test ait de quoi nettoyer

# Colonnes de l'échantillon : toutes celles de l'extraction (lues par clean(), puis par la conversion Parquet)
REQUIRED_COLUMNS = COLUMNS

# Une condition SQL par type d'anomalie à représenter dans l'échantillon (seuils tirés de cleaning.py)
ANOMALY_FILTERS = {
    "énergie > 900 kcal": f"energy_kcal_100g > {cleaning.KCAL_MAX}",
    "sucres > 100 g": f"sugars_100g > {cleaning.RANGES['sugars_100g'][1]}",
    "sel > 100 g": f"salt_100g > {cleaning.RANGES['salt_100g'][1]}",
    "sucres > glucides": f"sugars_100g > carbohydrates_100g + {cleaning.SUGARS_TOLERANCE}",
    "saturées > lipides": f"saturated_fat_100g > fat_100g + {cleaning.SATURATED_TOLERANCE}",
    "énergie nulle avec lipides": "energy_kcal_100g = 0 AND fat_100g > 0",
    "sans catégorie": "categories_tags IS NULL OR len(categories_tags) = 0",
    "code avec espaces": "code <> trim(code)",
    "nom en majuscules": "product_name = upper(product_name) AND product_name <> lower(product_name)",
}


def _select_columns(con: duckdb.DuckDBPyConnection, table: str) -> list[str]:
    """Vérifie que les colonnes nécessaires existent et renvoie celles à extraire."""
    available = {row[0] for row in con.execute(f"DESCRIBE {table}").fetchall()}
    missing = [column for column in REQUIRED_COLUMNS if column not in available]
    if missing:
        raise SystemExit(f"Colonnes absentes de {table} : {', '.join(missing)}")
    return list(REQUIRED_COLUMNS)


def _build_query(table: str, columns: list[str], rows: int) -> str:
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
        columns = _select_columns(con, args.table)
        query = _build_query(args.table, columns, args.rows)
        # ORDER BY ALL : tri sur toutes les colonnes, donc ordre total et fichier identique d'un lancement à l'autre
        con.execute(
            f"COPY (SELECT * FROM ({query}) ORDER BY ALL) "
            f"TO {sql_literal(args.out.as_posix())} (FORMAT PARQUET, {duckdb_parquet_options()})"
        )
        con.close()

    count = duckdb.sql(f"SELECT count(*) FROM read_parquet({sql_literal(args.out.as_posix())})").fetchone()[0]
    print(f"{count} lignes écrites dans {args.out}")


if __name__ == "__main__":
    main()