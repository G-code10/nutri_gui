# import pandas as pd
# import numpy as np
# import pyarrow as pa
import pyarrow.parquet as pq
import re
import json

#TODO nutriments

food_paquet = "data/food.parquet"

def check_col_string(col: str):
    ar_col = pq.read_table(food_paquet, columns=[col])
    val_list = ar_col.to_pylist()
    null_compt = 0
    for valeur in val_list:
        # print(type(valeur[col]))
        if valeur[col] is None:
            null_compt += 1
        # if not isinstance(valeur[col], str):
        #     print(valeur[col])
        #     type_compt += 1
    nb_ligne = len(val_list)
    percent_null = round((null_compt / nb_ligne) * 100, 2)
    return null_compt, percent_null

def check_col_liststr(col: str):
    ar_col = pq.read_table(food_paquet, columns=[col])
    val_list = ar_col.to_pylist()
    null_compt = 0
    typerr_compt = 0
    for valeur in val_list:
        if valeur[col] is None:
            null_compt += 1
        else:
            for item in valeur[col]:
                # print(type(item))
                if not isinstance(item, str):
                    typerr_compt += 1
    nb_ligne = len(val_list)
    percent_null = round((null_compt / nb_ligne) * 100, 4)
    percent_type = round((typerr_compt / nb_ligne) * 100, 2)
    return null_compt, typerr_compt, percent_null, percent_type

def check_col_int(col: str):
    ar_col = pq.read_table(food_paquet, columns=[col])
    val_list = ar_col.to_pylist()
    null_compt = 0
    type_compt = 0
    for valeur in val_list:
        # print(type(valeur[col]))
        if valeur[col] is None:
            null_compt += 1
        elif not isinstance(valeur[col], int):
        #     print(valeur[col])
            type_compt += 1
    nb_ligne = len(val_list)
    percent_null = round((null_compt / nb_ligne) * 100, 4)
    percent_type = round((typerr_compt / nb_ligne) * 100, 2)
    return null_compt, type_compt, percent_null, percent_type

def check_col_codeb(col: str):
    ar_col = pq.read_table(food_paquet, columns=[col])
    val_list = ar_col.to_pylist()
    null_compt = 0
    false_compt = 0
    for valeur in val_list:
        if valeur[col] is None:
            null_compt += 1
        if len(valeur[col]) > 13 or len(valeur[col]) < 13:
            false_compt += 1
        # if not isinstance(valeur[col], str):
        #     print(valeur[col])
    nb_ligne = len(val_list)
    percent_null = round((null_compt / nb_ligne) * 100, 2)
    percent_false = round((false_compt / nb_ligne) * 100, 2)
    return null_compt, false_compt, percent_null, percent_false

def check_col_completness(col: str):
    ar_col = pq.read_table(food_paquet, columns=[col])
    val_list = ar_col.to_pylist()
    null_compt = 0
    false_compt = 0
    for valeur in val_list:
        # print(type(valeur[col]))
        if valeur[col] is None:
            null_compt += 1
        if valeur[col] is not None and (valeur[col] > 1.1 or valeur[col] == 0):
            false_compt += 1
    nb_ligne = len(val_list)
    percent_null = round((null_compt / nb_ligne) * 100, 4)
    percent_false = round((false_compt / nb_ligne) * 100, 2)
    return null_compt, false_compt, percent_null, percent_false

def is_date_valide(date_str):
    # passage au regex division par 4 du temps d'éxécution
    return bool(re.match(r"^\d{4}(-\d{2}(-\d{2})?)?$", date_str))
    # formats = ["%Y-%m-%d", "%Y-%m", "%Y"]
    # for fmt in formats:
    #     try:
    #         datetime.strptime(date_str, fmt)
    #         return True
    #     except ValueError:
    #         continue
    # return False

def check_col_entry_dates(col: str):
    ar_col = pq.read_table(food_paquet, columns=[col])
    val_list = ar_col.to_pylist()
    null_compt = 0
    typerr_compt = 0
    daterr_compt = 0
    for valeur in val_list:
        if valeur[col] is None:
            null_compt += 1
        else:
            for item in valeur[col]:
                if not isinstance(item, str):
                    typerr_compt += 1
                if not is_date_valide(item):
                    daterr_compt += 1
    nb_ligne = len(val_list)
    percent_null = round((null_compt / nb_ligne) * 100, 4)
    percent_type = round((typerr_compt / nb_ligne) * 100, 2)
    percent_date = round((daterr_compt / nb_ligne) * 100, 4)
    return null_compt, typerr_compt, daterr_compt, percent_null, percent_type, percent_date

null_compt, percent_null = check_col_string("brands")
print(f"Colonne brands : nombre de valeur nulle : {null_compt} soit {percent_null}%")

null_compt, percent_null = check_col_string("lang")
print(f"Colonne lang : nombre de valeur nulle : {null_compt} soit {percent_null}%")

null_compt, percent_null = check_col_string("nutriscore_grade")
print(f"Colonne nutriscore_grade : nombre de valeur nulle : {null_compt} soit {percent_null}%")

null_compt, percent_null = check_col_string("ingredients")
print(f"Colonne ingredients : nombre de valeur nulle : {null_compt} soit {percent_null}%")

null_compt, false_compt, percent_null, percent_false = check_col_codeb("code")
print(f"Colonne code : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur fausse : {false_compt} soit {percent_false}%")

null_compt, false_compt, percent_null, percent_false = check_col_completness("completeness")
print(f"Colonne completness : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur fausse : {false_compt} soit {percent_false}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("countries_tags")
print(f"Colonne countries_tag : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("ingredients_text")
print(f"Colonne ingredients_text : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("data_quality_errors_tags")
print(f"Colonne data_quality_errors_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("food_groups_tags")
print(f"Colonne food_group_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("ingredients_analysis_tags")
print(f"Colonne ingredients_analysis_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("ingredients_original_tags")
print(f"Colonne ingredients_original_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("ingredients_tags")
print(f"Colonne ingredients_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("nova_groups_tags")
print(f"Colonne nova_groups_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("states_tags")
print(f"Colonne states_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("packaging_recycling_tags")
print(f"Colonne packaging_recycling_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("packaging_shapes_tags")
print(f"Colonne packaging_shapes_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("popularity_tags")
print(f"Colonne popularity_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_liststr("vitamins_tags")
print(f"Colonne vitamins_tag : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")

null_compt, typerr_compt, daterr_compt, percent_null, percent_type, percent_date = check_col_entry_dates("entry_dates_tags")
print(f"Colonne entry_dates_tags : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")
print(f"nombre de date au mauvais format : {daterr_compt} soit {percent_date}%")

null_compt, typerr_compt, percent_null, percent_type = check_col_int("nutriscore_score")
print(f"Colonne nutriscore_score : nombre de valeur nulle : {null_compt} soit {percent_null}%") 
print(f"nombre de valeur au mauvais type : {typerr_compt} soit {percent_type}%")
