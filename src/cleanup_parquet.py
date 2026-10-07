import os, sys
sys.path.append(".")

import nutriscope_ean

import time
import re

import pandas as pd
import numpy as np

import conf

def extract_nutriment(liste_nutriments, nom_nutriment):
    if not isinstance(liste_nutriments, (np.ndarray, list)):
        return None

    for nutriment in liste_nutriments:
        if isinstance(nutriment, dict) and nutriment.get('name') == nom_nutriment:

            value_100g = nutriment.get('100g')
            try:
                value_100g = float(value_100g)
            except (TypeError, ValueError):
                return None

            if nom_nutriment == "fruits-vegetables-legumes-estimate-from-ingredients":
                return value_100g

            unit = nutriment.get('unit')
            if unit == "&#181;g":
                unit = 'µg'
            elif unit == "% vol / *":
                unit = '% vol'
            elif unit == "kJ":
                unit = 'kj'
            elif unit == "":
                unit = None

            if unit == "g":
                return value_100g
            elif unit == "mg":
                return value_100g * 0.001
            elif unit == "µg":
                return value_100g * 0.000001
            elif unit == "kj":
                return value_100g

            return None

    return None

if not os.path.exists(conf.off_parquet_path_light):
    print(f"Le fichier parquet allégé n'est pas présent... Veuillez lancer generate_light_parquet.py pour le généré")
    exit()

start = time.time()
off_nutriments_tags_df = pd.read_parquet(conf.off_parquet_path_light)
print(f"Temps de chargement du fichier parquet allégé: {time.time() - start}")

start = time.time()
off_light_extended_df_fr = off_nutriments_tags_df.copy()

for name in conf.nutriments_list:
    print(f"\t Génération des données pour: {name}")
    off_light_extended_df_fr[name] = off_light_extended_df_fr['nutriments'].apply(lambda x: extract_nutriment(x, name))
print(f"Temps de génération des données: {time.time() - start}")

start = time.time()
off_light_extended_df_fr["short_name"] = off_light_extended_df_fr["product_name"].apply(lambda x: x[0]["text"] if isinstance(x, (list, np.ndarray)) and len(x) > 0 else None)
print(f"Temps de génération du nom court: {time.time() - start}")




start = time.time()
off_categories_tags_df = pd.read_parquet(conf.off_parquet_path_cat)
print(f"Temps de chargement du fichier parquet des catégories: {time.time() - start}")

start = time.time()
off_categories_tags_df["code_safe"] = 0
off_categories_tags_df["code_safe"] = off_categories_tags_df["code"].apply(lambda x: nutriscope_ean.EAN(x).get_key())

off_categories_tags_df_bad_ean = off_categories_tags_df[off_categories_tags_df["code_safe"].isna()].copy()
off_categories_tags_df = off_categories_tags_df[~off_categories_tags_df["code_safe"].isna()].copy()

off_categories_tags_df.drop(columns=['code_safe'], inplace=True)

print(f"Netoyage divers (categories): {time.time() - start}")




start = time.time()
off_light_extended_df_fr["code_safe"] = 0
off_light_extended_df_fr["code_safe"] = off_light_extended_df_fr["code"].apply(lambda x: nutriscope_ean.EAN(x).get_key())

off_light_extended_df_fr_bad_ean = off_light_extended_df_fr[off_light_extended_df_fr["code_safe"].isna()].copy()
off_light_extended_df_fr = off_light_extended_df_fr[~off_light_extended_df_fr["code_safe"].isna()].copy()

off_light_extended_df_fr.drop(columns=['nutriments'], inplace=True)
off_light_extended_df_fr.drop(columns=['product_name'], inplace=True)
off_light_extended_df_fr.drop(columns=['code_safe'], inplace=True)

off_light_extended_df_fr["brands"] = (off_light_extended_df_fr["brands"].replace("", pd.NA).fillna("Inconnu"))
off_light_extended_df_fr["brands"] = off_light_extended_df_fr["brands"].astype(str).str.replace("\x00", "", regex=False)

off_light_extended_df_fr["short_name"] = (off_light_extended_df_fr["short_name"].replace("", pd.NA).fillna("Inconnu"))

off_light_extended_df_fr["code"] = pd.to_numeric(off_light_extended_df_fr["code"], errors="coerce").astype("Int64")
off_light_extended_df_fr = off_light_extended_df_fr[off_light_extended_df_fr["code"].notna() & (off_light_extended_df_fr["code"] != 0)]
off_light_extended_df_fr.drop_duplicates(subset=["code"], inplace=True)

for col in ["short_name", "brands"]:
    off_light_extended_df_fr[col] = (
        off_light_extended_df_fr[col]
        .astype("string")
        .str.replace("\x00", "", regex=False)
    )
print(f"Netoyage divers: {time.time() - start}")

start = time.time()
off_light_extended_df_fr.to_parquet(conf.off_parquet_path_formated, index=False)
print(f"Temps de sauvegarde du fichier parquet formaté: {time.time() - start}")


start = time.time()
off_categories_tags_df.to_parquet(conf.off_parquet_path_formated_cat, index=False)
print(f"Temps de sauvegarde du fichier parquet categories formaté: {time.time() - start}")
