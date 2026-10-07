import numpy as np
import pandas as pd

def flatten_nutriments(nutriment_list):
    """Créer un dictionnaire plat des nutriments à partir d'une liste"""
    if not isinstance(nutriment_list, (np.ndarray, list)):
        return {}
    
    flat_dict = {}

    for nutriment in nutriment_list:
        name = nutriment['name'] + '_100g'
        flat_dict[name] = nutriment['100g']

    return flat_dict

def flatten_categories(category_list):
    """Créer un dictionnaire plat des nutriments à partir d'une liste"""
    if not isinstance(category_list, (np.ndarray, list)):
        return {}
    
    flat_dict = {}

    for category in category_list:
        name = category[3:] # Commencer la lecteur de la chaîne de caractère par le 3
        flat_dict[name] = 1 # Pas besoin d'ajouter +=1 à chaque fois car je souhaite mettre uniquement les unique.

    return flat_dict

def flattening_nutriments_column_join_and_drop(df_column, df, columns_drop:list=None) :
    """
    - Applatissement d'une colonne en un nouveau df_norm
    - df.join(df_norm)
    - Suppression des colonnes 'doublons' (optionnel)
    """
    # Applatir mon dict en nouvelles colonnes.
    df_norm = pd.json_normalize(df_column)

    # Joindre mon df et mes nouvelles colonnes en gardant.
    df_join = df.join(df_norm[['fiber_100g','proteins_100g','energy_100g','saturated-fat_100g','sugars_100g', 'salt_100g']]) # Attention pas de .fillna(0.0) car cela pourrait fausser la décision de la donnée manquante.

    # Retirer les colonnes si la donnée n'est pas vide.
    if columns_drop is not None :
        try: 
            df_join = df_join.drop(columns_drop, axis=1)
        except Exception as e:
            print(f"erreur : {e}")
        
    return df_join

def flattening_categories_column_join_and_drop(df_column, df, columns_drop:list=None) :
    """
    - Applatissement d'une colonne en un nouveau df_norm
    - df.join(df_norm)
    - Suppression des colonnes 'doublons' (optionnel)
    """
    # Applatir mon dict en nouvelles colonnes.
    df_norm = pd.json_normalize(df_column)

    # Joindre mon df et mes nouvelles colonnes en gardant.
    df_join = df.join(df_norm) # Attention pas de .fillna(0.0) car cela pourrait fausser la décision de la donnée manquante.

    # Retirer les colonnes si la donnée n'est pas vide.
    if columns_drop is not None :
        try: 
            df_join = df_join.drop(columns_drop, axis=1)
        except Exception as e:
            print(f"erreur : {e}")
        
    return df_join