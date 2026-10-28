"""Configuration partagée du dépôt : chemins et constantes utilisés par plusieurs modules.

Une seule source pour chaque valeur : les modules l'importent (from src import config) au lieu de la recopier.
Les chemins sont résolus par rapport à ce fichier, pas au dossier courant : ils valent quel que soit l'endroit
d'où l'on lance Python.

Ce qui n'est PAS ici :
- les constantes métier du nettoyage (KCAL_MAX, RANGES, tolérances...) : paramètres des règles, dans cleaning.py ;
- la connexion à la base (CONF, db.env) : dans load_db.py ;
- ce qui ne sert qu'à un seul module.

Aucun fichier n'est lu ni créé à l'import : ce ne sont que des chemins et des valeurs.
"""

from pathlib import Path

# --- Racine du dépôt (src/config.py -> dossier parent de src/) ---
ROOT = Path(__file__).resolve().parent.parent

# --- Données (dossier data/, hors Git) ---
DATA_DIR = ROOT / "data"
FOOD_PARQUET = DATA_DIR / "food.parquet"                          # source Open Food Facts, imbriquée
RAW_DIR = DATA_DIR / "raw"
RAW_PATH = RAW_DIR / "products_nutrition.parquet"                 # brut aplati, fichier complet (extract.py)
FRANCE_EXTRACT_PATH = RAW_DIR / "extrait_france.parquet"          # brut aplati, extrait France (extract.py)
SAMPLE_RAW_PATH = RAW_DIR / "sample_raw.parquet"                  # échantillon brut des tests (make_sample_raw.py)
CLEAN_PATH = DATA_DIR / "clean" / "products_clean.parquet"        # nettoyé (clean_pipeline.py)
PARQUET_DIR = DATA_DIR / "parquet"
PRODUCTS_PARQUET_DIR = PARQUET_DIR / "produits"                   # partitionné par rayon (convert_parquet.py)
EXPORTS_DIR = DATA_DIR / "exports"                                # exports d'entraînement (TP 12, étape 5)
DURATIONS_LOG_PATH = DATA_DIR / "durees.jsonl"                    # journal des durées (pipeline, conversion)

# --- Documentation générée ---
CLEANING_REPORT_PATH = ROOT / "docs" / "data" / "rapport_nettoyage.md"   # rapport avant / après (report.py)

# --- Constantes partagées ---
RAW_TABLE = "products_nutrition"   # nom de la table brute (extraction, échantillon)
UNKNOWN_AISLE = "unknown"          # rayon des produits sans groupe alimentaire
COMPRESSION = "zstd"               # compression de tous les Parquet produits

# Les sept nutriments clés (complétude du benchmark, filtre de l'export features) ; à ne pas confondre
# avec cleaning.KEY_NUTRIENTS, liste propre aux règles de nettoyage (kJ et sodium compris)
CORE_NUTRIENTS = [
    "energy_kcal_100g", "fat_100g", "saturated_fat_100g", "carbohydrates_100g",
    "sugars_100g", "proteins_100g", "salt_100g",
]

# Étapes inscrites au journal des durées (écrites par pipeline et convert_parquet, relues par benchmark)
STEP_READ = "lecture"
STEP_CLEAN = "nettoyage"
STEP_WRITE_CLEAN = "ecriture_nettoye"
STEP_REPORT = "rapport"
STEP_DB_SCHEMA = "schema_base"
STEP_DB_LOAD = "chargement_base"
STEP_CONVERT = "conversion_parquet"

# Licence des données, rappelée dans chaque fichier produit
LICENSE = "Open Food Facts contributors - ODbL (https://opendatacommons.org/licenses/odbl/1-0/)"