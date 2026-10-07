import os, sys
sys.path.append(".")

import time

import pandas as pd

import conf

if not os.path.exists(conf.off_parquet_path):
    print(f"Le fichier parquet n'est pas présent... Veuillez lancer download_parquet.py pour le récupérer")
    exit()

if "--clear" in sys.argv:
    os.remove(conf.off_parquet_path_light)

if os.path.exists(conf.off_parquet_path_light):
    print(f"Le fichier parquet allégé est déjà présent... Relancer le script avec \"--clear\" pour le netoyer !")
    exit()

start = time.time()
off_nutriments_tags_df = pd.read_parquet(conf.off_parquet_path, columns=conf.sel_columns)
print(f"Temps de chargement du fichier parquet: {time.time() - start}")

start = time.time()
off_nutriments_tags_df.to_parquet(conf.off_parquet_path_light, index=False)
print(f"Temps de sauvegarde du fichier parquet allégé: {time.time() - start}")

start = time.time()
off_nutriments_tags_df = pd.read_parquet(conf.off_parquet_path, columns=["code", "categories_tags"])
print(f"Temps de chargement du fichier parquet pour les catégories: {time.time() - start}")

start = time.time()
off_nutriments_tags_df.to_parquet(conf.off_parquet_path_cat, index=False)
print(f"Temps de sauvegarde du fichier parquet pour les catégories {conf.off_parquet_path_cat}: {time.time() - start}")
