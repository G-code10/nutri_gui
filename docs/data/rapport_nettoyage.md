# Rapport de nettoyage

- Date : 2026-11-09
- Source : `data/raw/france_extract_20261109.parquet`
- Données : Open Food Facts, © Open Food Facts contributors, licence ODbL.
- Généré par `python -m src.report` : ne pas modifier à la main.

## 1. Volumétrie

|  | Avant | Après |
| --- | --- | --- |
| Lignes | 1 247 336 | 521 240 |
| Colonnes | 27 | 41 |
| Codes distincts | 1 247 309 | 521 240 |

## 2. Lignes touchées par règle

Une ligne touchée par plusieurs sous-règles compte une fois dans « lignes touchées » et une fois par sous-règle dans le détail.

| Règle | Lignes avant | Lignes après | Lignes touchées | Détail |
| --- | --- | --- | --- | --- |
| `type_columns` | 1 247 336 | 1 247 336 | 0 | columns_cast = 18, values_coerced = 0 |
| `normalize_texts` | 1 247 336 | 1 247 336 | 71 900 | nul_removed = 3, blank_to_na = 1, names_fixed = 15 231, brands_unified = 58 412, codes_stripped = 0 |
| `enforce_unique_code` | 1 247 336 | 1 247 309 | 27 | rows_without_code = 0, duplicates_removed = 27, codes_concerned = 27 |
| `normalize_grade` | 1 247 309 | 1 247 309 | 758 534 | not_applicable = 40 941, unknown = 717 593 |
| `drop_unclassifiable` | 1 247 309 | 617 241 | 630 068 | unclassifiable_dropped = 630 068 |
| `reconcile_salt_sodium` | 617 241 | 617 241 | 1 937 | sodium_recomputed = 1 937, salt_derived = 0, sodium_derived = 0 |
| `reconcile_kcal_kj` | 617 241 | 617 241 | 51 007 | ratio_inconsistent = 51 010, kcal_recomputed = 51 007 |
| `neutralize_range:fat_100g` | 617 241 | 617 241 | 36 | invalid_to_na = 36 |
| `neutralize_range:saturated_fat_100g` | 617 241 | 617 241 | 16 | invalid_to_na = 16 |
| `neutralize_range:carbohydrates_100g` | 617 241 | 617 241 | 60 | invalid_to_na = 60 |
| `neutralize_range:sugars_100g` | 617 241 | 617 241 | 42 | invalid_to_na = 42 |
| `neutralize_range:fiber_100g` | 617 241 | 617 241 | 73 | invalid_to_na = 73 |
| `neutralize_range:proteins_100g` | 617 241 | 617 241 | 27 | invalid_to_na = 27 |
| `neutralize_range:salt_100g` | 617 241 | 617 241 | 34 | invalid_to_na = 34 |
| `neutralize_range:sodium_100g` | 617 241 | 617 241 | 34 | invalid_to_na = 34 |
| `neutralize_range:fruits_vegetables_legumes_100g` | 617 241 | 617 241 | 1 401 | invalid_to_na = 1 401 |
| `neutralize_range:energy_kcal_100g` | 617 241 | 617 241 | 140 | invalid_to_na = 140 |
| `neutralize_range:energy_kj_100g` | 617 241 | 617 241 | 149 | invalid_to_na = 149 |
| `neutralize_subpart_above_total` | 617 241 | 617 241 | 506 | sugars_above_carbs = 338, saturated_above_fat = 178 |
| `handle_allergens_unknown` | 617 241 | 617 241 | 299 182 | flagged = 299 184, empty_to_na = 299 182, none_declared = 121 896 |
| `missing_strategy` | 617 241 | 617 241 | 0 | flags_set = 11, constants_filled = 0, deferred = 3, columns_dropped = 0 |
| `fill_saturated_zero_if_low_fat` | 617 241 | 617 241 | 1 948 | set_to_zero = 1 948 |
| `fix_inconsistent_energy` | 617 241 | 617 241 | 3 012 | zero_recomputed = 1 432, zero_invalidated = 18, deviation_recomputed = 1 553, deviation_invalidated = 9 |
| `drop_rows_without_key_nutrient` | 617 241 | 521 240 | 96 001 | rows_dropped = 96 001 |
| `derive_missing_energy` | 521 240 | 521 240 | 399 | kcal_from_kj = 369, kcal_from_macros = 30, flagged = 5 675 |

## 3. Anomalies métier avant / après

| Anomalie | Avant | Après |
| --- | --- | --- |
| fat_100g hors de [0 ; 100] | 45 | 0 |
| saturated_fat_100g hors de [0 ; 100] | 18 | 0 |
| carbohydrates_100g hors de [0 ; 100] | 77 | 0 |
| sugars_100g hors de [0 ; 100] | 47 | 0 |
| fiber_100g hors de [0 ; 100] | 78 | 0 |
| proteins_100g hors de [0 ; 100] | 32 | 0 |
| salt_100g hors de [0 ; 100] | 54 | 0 |
| sodium_100g hors de [0 ; 40] | 68 | 0 |
| fruits_vegetables_legumes_100g hors de [0 ; 100] | 1 573 | 0 |
| energy_kcal_100g hors de [0 ; 900] | 1 117 | 0 |
| energy_kj_100g hors de [0 ; 3765,6] | 200 | 0 |
| sucres > glucides + 0,5 | 427 | 0 |
| saturés > lipides + 0,5 | 217 | 0 |
| sel ≠ sodium × 2,5 (écart > 0,1) | 2 291 | 0 |
| rapport kJ / kcal hors de [3,9 ; 4,5] | 110 311 | 157 |
| kcal nulles avec un macronutriment positif (hors alcool) | 3 306 | 33 |
| kcal à plus de 50 % du calcul 4/4/9 (hors alcool) | 18 145 | 0 |
| lignes sans code | 0 | 0 |
| codes en double (lignes en trop) | 27 | 0 |

## 4. Manquants sur les colonnes clés

| Colonne | Manquants avant | % | Manquants après | % |
| --- | --- | --- | --- | --- |
| energy_kcal_100g | 359 477 | 28,8 % | 5 675 | 1,1 % |
| energy_kj_100g | 359 123 | 28,8 % | 5 772 | 1,1 % |
| saturated_fat_100g | 367 656 | 29,5 % | 9 137 | 1,8 % |
| sugars_100g | 366 554 | 29,4 % | 10 273 | 2,0 % |
| proteins_100g | 364 825 | 29,2 % | 8 321 | 1,6 % |
| salt_100g | 420 869 | 33,7 % | 23 855 | 4,6 % |
| sodium_100g | 420 869 | 33,7 % | 23 855 | 4,6 % |
| fat_100g | 366 472 | 29,4 % | 8 979 | 1,7 % |
| carbohydrates_100g | 366 211 | 29,4 % | 9 015 | 1,7 % |
| fiber_100g | 867 348 | 69,5 % | 249 269 | 47,8 % |
| nutriscore_grade | 25 040 | 2,0 % | 60 439 | 11,6 % |
| brands | 597 607 | 47,9 % | 113 524 | 21,8 % |

## 5. Produits par rayon après nettoyage

| Rayon | Produits | Part |
| --- | --- | --- |
| `en:sugary-snacks` | 100 663 | 19,3 % |
| `en:fish-meat-eggs` | 81 245 | 15,6 % |
| `en:milk-and-dairy-products` | 55 804 | 10,7 % |
| `en:cereals-and-potatoes` | 51 651 | 9,9 % |
| `unknown` | 51 100 | 9,8 % |
| `en:beverages` | 41 177 | 7,9 % |
| `en:composite-foods` | 36 949 | 7,1 % |
| `en:fats-and-sauces` | 35 076 | 6,7 % |
| `en:fruits-and-vegetables` | 32 295 | 6,2 % |
| `en:salty-snacks` | 28 103 | 5,4 % |
| `en:alcoholic-beverages` | 4 779 | 0,9 % |
| `en:baby-foods-and-milks` | 2 398 | 0,5 % |

## 6. Colonnes ajoutées et retirées

- Ajoutées : `allergens_missing`, `brands_missing`, `carbohydrates_100g_missing`, `energy_kcal_100g_missing`, `fat_100g_missing`, `fiber_100g_missing`, `fruits_vegetables_legumes_100g_missing`, `grade_not_applicable`, `ingredients_text_missing`, `nova_group_missing`, `product_name_missing`, `proteins_100g_missing`, `saturated_fat_100g_missing`, `sugars_100g_missing`
- Retirées : aucune
