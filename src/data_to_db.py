import pandas as pd
# import nutriscore_sql
# import math
import sys

sys.path.append(".")

from cleaning import *
from conf import sql_conf_dict as conf
print("Import effectué")

conf = {
    "database": "nutriscope", 
    "user": "postgres", 
    "host": "localhost", 
    "port": 5432,
    "debug": False
}

# NSQL = nutriscore_sql.NutriscoreSQL(conf, "postgres")

# TODO : 
# Initialiser un fichier .parquet 
# L'aplatir (light ou regular)
# L'exporter
# Le manipuler

def print_df(df:pd.DataFrame, nbr_of_line:int, column:list = []) :
    if column != [] :
        if nbr_of_line != '':
            print(df[column].head(nbr_of_line))
        else :
            print(df[column])
    else :
        if nbr_of_line != '':
            print(df.head(nbr_of_line))
        else :
            print(df)

paquet_choice = True
food_parquet = ''

# Nettoyer la donnée et créer un fichier .parquet de ["code", "brands", "product_name", "nutriments"]
while paquet_choice :

    choose_paquet = input("Initialiser un paquet en cleaned - light(l) ou regular(r)\nOU next(n) pour passer à la suite : ")

    if choose_paquet == 'light' or choose_paquet == 'l' :
        food_parquet = "data/food_light.parquet"
    elif choose_paquet == 'regular' or choose_paquet == 'r' :
        food_parquet = "data/food.parquet"
    else :
        paquet_choice = False
        break

    print("Récupération du parquet")
    # Récupération et nettoyage des listes : 
    df_products = pd.read_parquet(food_parquet, columns=["code", "brands", "product_name", "nutriments", "categories_tags"])#.head(10_000) ==> light_food
    # df_products.to_parquet("data/food_light.parquet")
    print(f"Parquet récupéré : {food_parquet}")

    print('Création de ma colonne flat_nutriments')
    df_products['flat_nutriments'] = df_products['nutriments'].apply(lambda x : flatten_nutriments(x))
    print('Colonne flat_nutriments finie')

    print('Création de ma colonne flat_categories_tags')
    df_products['flat_categories_tags'] = df_products['categories_tags'].apply(lambda x : flatten_categories(x))
    print('Colonne flat_nutriments finie')


    print('Étaler flat_categories_tags et suppression de celle-ci et de nutriments')
    df_join_cat = flattening_categories_column_join_and_drop(df_products['flat_categories_tags'], df_products, ['categories_tags', 'flat_categories_tags'])
    print('Jointure et suppression finie')

    print('Étaler flat_nutriments et suppression de celle-ci et de nutriments')
    df_join = flattening_nutriments_column_join_and_drop(df_products['flat_nutriments'], df_join_cat, ['nutriments', 'flat_nutriments'])
    print('Jointure et suppression finie')

    input_export = input("Voulez-vous exporter le fichier ? y / n : ")
    if input_export.lower() == 'y' or input_export.lower() == 'yes' :
        print('Exportation en parquet')
        if food_parquet == "data/food_light.parquet" :
            df_join.to_parquet("data/cleaned_food_light.parquet")
        elif food_parquet == "data/food.parquet" :
            df_join.to_parquet("data/cleaned_food.parquet")
        print('Exportation finie')

    paquet_choice = False


# Manipulation de la donnée
data_choice = True
while data_choice:

    choose_paquet = input("Choisissez un parquet nettoyé : light(l) ou regular(r)\nOU quit(q) pour quitter : ")

    if choose_paquet == 'light' or choose_paquet == 'l' :
        food_parquet = "data/cleaned_food_light.parquet" 
    elif choose_paquet == 'regular' or choose_paquet == 'r' :
        food_parquet = "data/cleaned_food.parquet" 
    else :
        data_choice = False
        break

    # Charger le parquet 
    df = pd.read_parquet(food_parquet)
    print(f"Voici les colonnes du {food_parquet} :\n{df.columns}")

    while data_choice :

        columns_input = []
        columns_continue = True

        while columns_continue : 
            display_df = input("Quelles colonnes voulez-vous afficher ?\nq - Quitter (dernier tour) : ")
            if display_df.lower() in df.columns :
                columns_input.append(display_df.lower())
            elif display_df.lower() == 'q' or display_df.lower() == 'quitter':
                columns_continue = False
                data_choice = False
            else : 
                print("Vérifiez que la colonne existe...")
                continue

        nbr_of_line = -131197 
        while nbr_of_line < 0 :
            try :
                nbr_of_line = int(input(f'Combien de lignes afficher ? (0 - {len(df)})\nEntrez "0" si vous ne voulez rien mettre : '))
            except :
                continue    
            if nbr_of_line > 0 :
                print_df(df,nbr_of_line, columns_input)
            else : 
                data_choice = False