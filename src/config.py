"""Configuration partagée du dépôt : chemins et constantes utilisés par plusieurs modules.

Une seule source pour chaque valeur : les modules l'importent (from src import config) au lieu de la recopier.
Les chemins sont résolus par rapport à ce fichier, pas au dossier courant : ils valent quel que soit l'endroit
d'où l'on lance Python.

Sorties datées (TP 13) : chaque sortie du pipeline s'appelle <préfixe>_<AAAAMMJJ>, dans son dossier.
Les préfixes et les dossiers sont ici ; la construction des noms et la recherche de la version la plus
récente sont dans utils.py (dated_path, find_input, prune_versions).

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
FOOD_PARQUET = DATA_DIR / "food.parquet"                          # source Open Food Facts, imbriquée (téléchargée à la main)
RAW_DIR = DATA_DIR / "raw"                                        # brut aplati (extract.py)
SAMPLE_RAW_PATH = RAW_DIR / "sample_raw.parquet"                  # échantillon brut des tests (make_sample_raw.py), non daté
CLEAN_DIR = DATA_DIR / "clean"                                    # nettoyé (clean_pipeline.py)
PARQUET_DIR = DATA_DIR / "parquet"                                # partitionné par rayon (convert_parquet.py)
EXPORTS_DIR = DATA_DIR / "exports"                                # exports d'entraînement (export_features.py)
REPORTS_DIR = DATA_DIR / "reports"                                # rapports du pipeline, hors Git (sans --docs)
DURATIONS_LOG_PATH = DATA_DIR / "durations.jsonl"                 # journal des durées (pipeline, modules)

# Dossiers de données des lancements sur l'échantillon et sur le fichier complet : mêmes sous-dossiers que DATA_DIR,
# pour que leurs sorties ne se mélangent jamais à celles de l'extrait France
SAMPLE_DATA_DIR = DATA_DIR / "sample"
FULL_DATA_DIR = DATA_DIR / "full"

# Préfixes des sorties datées : <préfixe>_<AAAAMMJJ>.parquet (ou dossier pour le Parquet partitionné)
FRANCE_EXTRACT_PREFIX = "france_extract"       # brut, extrait France
FULL_RAW_PREFIX = "products_nutrition"         # brut, fichier complet
SAMPLE_RAW_PREFIX = "sample_raw"               # brut, copie de l'échantillon
CLEAN_PREFIX = "products_clean"                # nettoyé
PRODUCTS_PREFIX = "products"                   # dossier partitionné products_<AAAAMMJJ>/ et son schéma
CLEANING_REPORT_PREFIX = "cleaning_report"     # rapport de nettoyage dans REPORTS_DIR
CONTROLS_REPORT_PREFIX = "controls_report"     # rapport des contrôles dans REPORTS_DIR
KEEP_VERSIONS = 3                              # versions datées gardées par type de sortie (jamais appliqué aux exports)

# --- Documentation générée et versionnée (écrite seulement avec --docs) ---
CLEANING_REPORT_PATH = ROOT / "docs" / "data" / "rapport_nettoyage.md"   # rapport avant / après (report.py)
CONTROLS_REPORT_PATH = ROOT / "docs" / "data" / "controle.md"            # contrôles Parquet / base (run_queries.py)

# --- Constantes partagées ---
RAW_TABLE = "products_nutrition"   # nom de la table brute (extraction, échantillon)
UNKNOWN_AISLE = "unknown"          # rayon des produits sans groupe alimentaire
COMPRESSION = "zstd"               # compression de tous les Parquet produits
SUCCESS_MARKER = "_SUCCESS"        # écrit en dernier dans un dossier partitionné : sans lui, le dossier est incomplet
SOURCE_ENV = "NUTRISCOPE_SOURCE"   # variable d'environnement qui remplace FOOD_PARQUET (terminal ou db.env)

# Les sept nutriments clés (complétude du benchmark, filtre de l'export features) ; à ne pas confondre
# avec cleaning.KEY_NUTRIENTS, liste propre aux règles de nettoyage (kJ et sodium compris)
CORE_NUTRIENTS = [
    "energy_kcal_100g", "fat_100g", "saturated_fat_100g", "carbohydrates_100g",
    "sugars_100g", "proteins_100g", "salt_100g",
]

# Sous-étapes inscrites au journal des durées (écrites par les modules, relues par le benchmark)
STEP_READ = "read"
STEP_CLEAN = "clean_rules"
STEP_WRITE_CLEAN = "write_clean"
STEP_REPORT = "report"
STEP_DB_SCHEMA = "db_schema"
STEP_DB_LOAD = "db_load"
STEP_CONVERT = "convert_parquet"

# Licence des données, rappelée dans chaque fichier produit
LICENSE = "Open Food Facts contributors - ODbL (https://opendatacommons.org/licenses/odbl/1-0/)"