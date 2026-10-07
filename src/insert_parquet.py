import os, sys
sys.path.append(".")

import io
import time

import csv

import pandas as pd
import numpy as np

import nutriscope_sql
import conf

if not os.path.exists(conf.off_parquet_path_formated):
    print(f"Le fichier parquet formaté n'est pas présent... Veuillez lancer cleanup_parquet.py pour le généré")
    exit()

start = time.time()
off_nutriments_tags_df = pd.read_parquet(conf.off_parquet_path_formated)
print(f"Temps de chargement du fichier parquet formaté: {time.time() - start}")

NSQL = nutriscope_sql.NutriscopeSQL(conf.sql_conf_dict, "simirblaiti")

sql_db_struct = "../sql/postgre_creation.sql"
NSQL.send_file(sql_db_struct)

brands = off_nutriments_tags_df["brands"].dropna().unique()
values = [(str.capitalize(brand),) for brand in brands]

off_nutriments_tags_df["brand"] = off_nutriments_tags_df["brands"] # pour traitement avant finalisation
off_nutriments_tags_df["brands"] = -1 # brand_id à 1 pour le moment
off_nutriments_tags_df["lang"] = "fr"

start = time.time()
NSQL.add_values(conf.add_brand_query_ex, values, )
print(f"Insertion des \"brands\": {time.time() - start}")



start = time.time()
off_categories_tags_df = pd.read_parquet(conf.off_parquet_path_formated_cat)
print(f"Temps de chargement du fichier parquet des catégories: {time.time() - start}")

exp = off_categories_tags_df[off_categories_tags_df["categories_tags"].apply(lambda x: isinstance(x, (list, np.ndarray)) and len(x) > 0)][["code", "categories_tags"]].explode("categories_tags")

datas = exp["categories_tags"].unique()
datas_en = []
for e in datas:
    if e.startswith("en:"):
        e = e[3:]
        datas_en.append((e, ))

start = time.time()
NSQL.add_values(conf.add_categories_query_ex, datas_en, )
print(f"Insertion des \"categories\": {time.time() - start}")

NSQL.send_query("SELECT id, name FROM categories;")
categories = NSQL.fetch()

db_categories_df = pd.DataFrame(categories, columns=["id", "name"])

exp["categories_tags"] = exp["categories_tags"].str.removeprefix("en:")

db_categories_df = db_categories_df.merge(exp, left_on="name", right_on="categories_tags")


# df_copy = db_categories_df[["id", "code"]].copy()
# print(df_copy.head(10))

cat_code = list(db_categories_df[["id", "code"]].itertuples(index=False, name=None))

start = time.time()
NSQL.add_values(conf.add_categories_codes_query_ex, cat_code, )
print(f"Insertion des relations \"categories\"/\"codes\": {time.time() - start}")

buffer = io.StringIO()

df_copy = off_nutriments_tags_df[[
    "code",
    "brands",
    "brand",
    "short_name",
    "lang", 
    "nutriscore_score", 
    "fiber",
    "proteins",
    "energy",
    "saturated-fat",
    "sugars",
    "salt"
]].copy()

"""
df_copy = off_nutriments_tags_df[[
    "code",
    "brands",
    "brand",
    "short_name",
    "lang", 
    "nutriments"
]].copy()
"""

start = time.time()
df_copy.to_csv(buffer, sep="\t", header=False, index=False, na_rep="\\N")
print(f"Création du CSV en mémoire: {time.time() - start}")

buffer.seek(0)

start = time.time()
NSQL.copy_products(conf.copy_product, buffer)
print(f"Insertion des products: {time.time() - start}")

start = time.time()
NSQL.send_query(conf.update_brand_id_query)
print(f"Création des liaisons produit/marque: {time.time() - start}")

NSQL.send_query(conf.finalize_table)
