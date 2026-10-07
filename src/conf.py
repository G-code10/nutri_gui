import os

## @var nutriscope_root_dir
# @brief La racine du l'application installé
nutriscope_root_dir = os.environ["LOCALAPPDATA"] + "\\Nutriscope"

## @var cache_dir
# @brief Le répertorie de cache
cache_dir = nutriscope_root_dir + "/cache"

## @var off_parquet_url
# @brief L'URL du parquet
# details L'URL ou peut être télécharger le ficheir food.parquet d'OenFoodFact
off_parquet_url = "https://huggingface.co/datasets/openfoodfacts/product-database/resolve/main/food.parquet?download=true"

## @var off_parquet_path
# @brief Le nom du fichier parquet
# @details Le nom du fichier parquet pour le stockage local
off_parquet_path = cache_dir + "/food.parquet"

off_csv_path = cache_dir + "/food.csv"

## @var off_parquet_path_light
# @brief Le nom du fichier parquet allégé
# @details Le nom du fichier parquet pour le stockage local ne contenant QUE les colonnes nécessaire à l'application
off_parquet_path_light = cache_dir + "/food_light.parquet"

off_parquet_path_cat = cache_dir + "/food_categories.parquet"

## @var off_parquet_path_formated
# @brief Le nom du fichier parquet formaté
# @details Le nom du fichier parquet pour le stockage local contenant les données splité et nettoyé des colonnes précédentes désormais inutile
off_parquet_path_formated = cache_dir + "/food_formated.parquet"

off_parquet_path_formated_cat = cache_dir + "/food_formated_cat.parquet"

## @var off_parquet_path
# @brief Le nom du fichier parquet
# @details Le nom du fichier parquet pour le stockage local
sql_conf_dict = {
    "database": "nutriscope", 
    "user": "nutriscope_app", 
    "host": "localhost", 
    "port": 5432,
    "debug": False
}

# La liste des nutriments utilisés dans le calcule du nutriscore
nutriments_list = ["fiber", "proteins", "energy", "saturated-fat", "sugars", "salt"]

# Les colonnes chargées et traitées avant insertino en TABLEs
sel_columns = ["nutriments", "code", "product_name", "brands", "nutriscore_score"]

add_brand_query_ex = "INSERT INTO brands (name) VALUES %s ON CONFLICT (name) DO NOTHING;"

add_categories_query_ex = "INSERT INTO categories (name) VALUES %s ON CONFLICT (name) DO NOTHING;"

add_categories_codes_query_ex = "INSERT INTO products_categories (category_id, product_id) VALUES %s;"


copy_product = """
COPY products (
    code, brand_id, brand, name, lang, nutriscore, 
    fiber, proteins, energy,
    saturated_fat, sugars, salt
)
FROM STDIN
WITH (
    FORMAT CSV,
    DELIMITER E'\\t',
    NULL '\\N'
)
"""

# copy_product = """
# COPY products (
#     code, brand_id, brand, name, lang,
#     nutriments
# )
# FROM STDIN
# WITH (
#     FORMAT CSV,
#     DELIMITER E'\\t',
#     NULL '\\N'
# )
# """

# requête pour construire après insertion initiale le champ "marque_id" par rapport à la colonne (temporaire) brand
update_brand_id_query = "UPDATE products p SET brand_id = m.id FROM brands m WHERE p.brand = m.name;"

# après "update_brand_id_query", la colonne temporaire "brand" peu être supprimée
finalize_table = "ALTER TABLE products DROP COLUMN brand;"
