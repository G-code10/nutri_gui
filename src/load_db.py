"""Chargement de la base PostgreSQL (étape `charger_base`) : ne reçoit que la sortie de cleaning.clean().

Les tables doivent déjà exister : le schéma est créé à part par create_db.create_schema().
Le remplissage se fait dans UNE seule transaction : si une étape échoue, rien n'est écrit.
Pour un rechargement complet, recréer le schéma avant (sinon les codes existants sont refusés).

La connexion part de la configuration CONF ci-dessous, complétée par le fichier db.env (à la racine du
dépôt, ignoré par Git) : POSTGRES_DB (nom de la base) et POSTGRES_PASSWORD (mot de passe) sont obligatoires
en pratique ; POSTGRES_USER, POSTGRES_HOST et POSTGRES_PORT remplacent les valeurs de CONF si on les décommente.
Modèle : db.env.example. Une variable d'environnement déjà définie l'emporte sur le fichier.
"""

import os

import pandas as pd
import psycopg
from dotenv import load_dotenv

from src import config, schema
from src.config import UNKNOWN_AISLE
from src.utils import aisle_code

ENV_PATH = config.ROOT / "db.env"

CONF = {
    "database": "nutriscope",
    "user": "postgres",
    "host": "localhost",
    "port": 5432,
    "debug": False,
}

# Variables de db.env et clé de connexion qu'elles remplacent (POSTGRES_PASSWORD ajoute une clé absente de CONF)
ENV_VARIABLES = {
    "POSTGRES_DB": "database",
    "POSTGRES_USER": "user",
    "POSTGRES_HOST": "host",
    "POSTGRES_PORT": "port",
    "POSTGRES_PASSWORD": "password",
}

TABLES = ["aisles", "brands", "categories", "products", "nutrients", "product_categories"]

PRODUCT_COLUMNS = [
    "code", "product_name", "brand_id", "aisle_code", "main_category", "ingredients_text", "allergens",
    "serving_size", "nova_group", "nutriscore_score", "nutriscore_grade", "grade_not_applicable",
    "completeness", "last_modified_t",
]
NUTRIENT_COLUMNS = [
    "code", "energy_kcal_100g", "energy_kj_100g", "fat_100g", "saturated_fat_100g", "carbohydrates_100g",
    "sugars_100g", "fiber_100g", "proteins_100g", "salt_100g", "sodium_100g",
    "fruits_vegetables_legumes_100g", "saturated_fat_100g_missing", "energy_kcal_100g_missing",
]
# Colonnes entières de la base : un décimal comme 12.0 serait refusé par COPY
INTEGER_COLUMNS = ["brand_id", "nova_group", "nutriscore_score", "last_modified_t"]

# Requêtes de contrôle rejouées après chaque chargement
CONTROLS = {
    "produits sans catégorie": """
        SELECT count(*) FROM products p
        WHERE NOT EXISTS (SELECT 1 FROM product_categories pc WHERE pc.code = p.code)""",
    "top marques": """
        SELECT b.name, count(*) FROM products p JOIN brands b USING (brand_id)
        GROUP BY b.name ORDER BY count(*) DESC, b.name LIMIT 10""",
    "complétude Nutri-Score par rayon (%)": """
        SELECT aisle_code, count(*), round(100.0 * count(nutriscore_grade) / count(*), 1)
        FROM products GROUP BY aisle_code ORDER BY count(*) DESC, aisle_code""",
    "codes en double": "SELECT count(*) - count(DISTINCT code) FROM products",
}


def settings() -> dict:
    """CONF complétée par db.env : chaque variable POSTGRES_* présente remplace (ou ajoute) sa clé de CONF."""
    load_dotenv(ENV_PATH)   # sans effet si le fichier n'existe pas ; ne remplace pas une variable déjà définie
    conf = dict(CONF)
    for variable, key in ENV_VARIABLES.items():
        value = os.environ.get(variable)
        if value:   # variable absente ou vide : on garde la valeur de CONF
            conf[key] = int(value) if key == "port" else value
    return conf


def connect(conf: dict | None = None) -> psycopg.Connection:
    """Ouvre la connexion (settings() par défaut). autocommit : la transaction est gérée par load()."""
    params = dict(settings() if conf is None else conf)
    params.pop("debug", None)                       # réglage de l'application, inconnu de psycopg
    params["dbname"] = params.pop("database")       # psycopg nomme cette clé « dbname »
    return psycopg.connect(**params, autocommit=True)


def aisle_label(tag: str) -> str:
    """Libellé lisible d'un rayon : « en:fruits-and-vegetables » devient « Fruits and vegetables »."""
    text = tag.split(":", 1)[-1].replace("-", " ").strip()
    return text[:1].upper() + text[1:]


def check_input(df: pd.DataFrame) -> None:
    """Refuse un DataFrame dont `code` n'est pas unique (ValueError), puis le valide avec le schéma pandera."""
    duplicated = df.loc[df["code"].duplicated(), "code"]
    if not duplicated.empty:
        raise ValueError(
            f"{len(duplicated)} code(s) en double : dédupliquer avant le chargement "
            f"(exemples : {list(duplicated.head(5))})"
        )
    schema.validate(df)


def _rows(frame: pd.DataFrame):
    """Lignes du DataFrame en tuples Python, les valeurs manquantes devenant None (NULL en base)."""
    return frame.astype(object).where(frame.notna(), None).itertuples(index=False, name=None)


def _copy(conn: psycopg.Connection, table: str, columns: list[str], rows) -> None:
    """Insère des lignes avec COPY, bien plus rapide qu'un INSERT par ligne."""
    with conn.cursor() as cursor, cursor.copy(f"COPY {table} ({', '.join(columns)}) FROM STDIN") as copy:
        for row in rows:
            copy.write_row(row)


def _insert_and_get_ids(conn: psycopg.Connection, table: str, key: str, id_column: str, values) -> dict:
    """Insère les valeurs distinctes dans une table à identifiant généré, puis renvoie {valeur: identifiant}."""
    _copy(conn, table, [key], [(value,) for value in values])
    return dict(conn.execute(f"SELECT {key}, {id_column} FROM {table}").fetchall())


def count_rows(conn: psycopg.Connection) -> dict[str, int]:
    """Nombre de lignes de chaque table."""
    return {table: conn.execute(f"SELECT count(*) FROM {table}").fetchone()[0] for table in TABLES}


def controls(conn: psycopg.Connection) -> dict[str, list[tuple]]:
    """Rejoue les requêtes de contrôle : {nom du contrôle: lignes résultat}."""
    results = {"volumétrie par table": list(count_rows(conn).items())}
    for name, query in CONTROLS.items():
        results[name] = conn.execute(query).fetchall()
    return results


def load(df: pd.DataFrame, conn: psycopg.Connection) -> dict[str, int]:
    """Charge le DataFrame nettoyé dans les tables existantes. Renvoie le nombre de lignes par table."""
    check_input(df)

    aisle = aisle_code(df["food_groups_tag_1"])
    tags = df["categories_tags"].explode().dropna()

    with conn.transaction():
        # 1) Tables de référence ('unknown' existe déjà dans aisles)
        aisle_rows = [(tag, aisle_label(tag)) for tag in aisle.unique() if tag != UNKNOWN_AISLE]
        _copy(conn, "aisles", ["aisle_code", "label"], aisle_rows)
        brand_ids = _insert_and_get_ids(conn, "brands", "name", "brand_id", df["brands"].dropna().unique())
        category_ids = _insert_and_get_ids(conn, "categories", "tag", "category_id", tags.unique())

        # 2) Produits
        products = df.reindex(columns=PRODUCT_COLUMNS)   # une colonne descriptive absente devient NULL
        products["brand_id"] = df["brands"].map(brand_ids)
        products["aisle_code"] = aisle
        products[INTEGER_COLUMNS] = products[INTEGER_COLUMNS].astype("Int64")
        _copy(conn, "products", PRODUCT_COLUMNS, _rows(products))

        # 3) Nutriments et liens produit - catégorie
        _copy(conn, "nutrients", NUTRIENT_COLUMNS, _rows(df[NUTRIENT_COLUMNS]))
        links = df[["code", "categories_tags"]].explode("categories_tags").dropna(subset=["categories_tags"])
        links["position"] = links.groupby("code").cumcount() + 1   # rang du tag dans la liste d'origine
        links["category_id"] = links["categories_tags"].map(category_ids)
        links = links.drop_duplicates(["code", "category_id"])
        _copy(conn, "product_categories", ["code", "category_id", "position"],
              _rows(links[["code", "category_id", "position"]]))

    return count_rows(conn)