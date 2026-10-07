import pandas as pd
import matplotlib as plt
import numpy as np
import json

###########################################
#### Profiling & périmètre · lun 25/08 #### 
###########################################

# TODO : 
# Profiling systématique des données récupérées au TP 1 : distributions, cardinalités, doublons de codes-barres,
# incohérences d'unités, valeurs impossibles (sucres > 100 g/100 g, énergies nulles…).;

#  Inventaire des colonnes : lesquelles servent le produit (score, substitution, images, assistant), lesquelles sont du
# bruit. S'appuyer sur data-fields.txt d'Open Food Facts. 

# Décision de périmètre en équipe : rayons couverts au lancement (5 à 8 catégories), colonnes conservées, seuil de
# complétude minimal par produit.

# Rédaction de docs/perimetre.md : périmètre retenu, critères, et surtout ce qu'on écarte et pourquoi.

#  Tour des équipes en fin de journée : chaque périmètre est challengé par une autre équipe.

########## ATTENTION ##########
# À committer : notebook de profiling + docs/perimetre.md argumenté.
# Un périmètre trop large en août se paie en janvier. Le formateur joue le client : il pousse à couper.
###############################

food_paquet = "data/food.parquet"

# open_food_facts_df = pd.read_parquet(food_paquet, columns=("countries_tags"))
open_food_facts_df = pd.read_parquet(food_paquet, columns=["countries_tags", "nutriments"])