"""Extrait de la table brute un petit échantillon parquet pour les tests d'idempotence.

L'échantillon reste BRUT (aucun nettoyage) : le test applique clean() lui-même.
Il est reproductible : même table + même graine = mêmes lignes, sur toutes les machines.

Usage (depuis la racine du dépôt) :
    python scripts/make_sample_raw.py --db chemin/vers/base.duckdb
"""

import argparse
from pathlib import Path

import duckdb

ROOT = Path(__file__).resolve().parent.parent
DEFAULT_OUT = ROOT / "data" / "sample_raw.parquet"
DEFAULT_TABLE = "products_nutrition"
DEFAULT_ROWS = 5000
DEFAULT_SEED = 42
ANOMALY_ROWS = 100  # lignes ajoutées par type d'anomalie, pour que le test ait de quoi nettoyer

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
    parser.add_argument("--db", required=True, help="fichier DuckDB contenant la table brute")
    parser.add_argument("--table", default=DEFAULT_TABLE)
    parser.add_argument("--rows", type=int, default=DEFAULT_ROWS, help="codes tirés au hasard")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    args = parser.parse_args()

    con = duckdb.connect(args.db, read_only=True)
    columns = select_columns(con, args.table)
    query = build_query(args.table, columns, args.rows)

    args.out.parent.mkdir(parents=True, exist_ok=True)
    # ORDER BY final : fichier identique d'une exécution à l'autre
    con.execute(
        f"COPY (SELECT * FROM ({query}) ORDER BY hash(code), code, completeness) "
        f"TO '{args.out.as_posix()}' (FORMAT parquet)"
    )
    count = con.execute(f"SELECT count(*) FROM read_parquet('{args.out.as_posix()}')").fetchone()[0]
    print(f"{count} lignes écrites dans {args.out}")


if __name__ == "__main__":
    main()