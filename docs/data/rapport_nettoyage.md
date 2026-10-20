# Rapport de nettoyage

- Date : 2026-10-20
- Source : `data/sample_raw.parquet`
- Données : Open Food Facts, © Open Food Facts contributors, licence ODbL.
- Généré par `python -m src.report` : ne pas modifier à la main.

## 1. Volumétrie

|  | Avant | Après |
| --- | --- | --- |
| Lignes | 5 656 | 2 072 |
| Colonnes | 24 | 38 |
| Codes distincts | 5 596 | 2 072 |

## 2. Lignes touchées par règle

Une ligne touchée par plusieurs sous-règles compte une fois dans « lignes touchées » et une fois par sous-règle dans le détail.

| Règle | Lignes avant | Lignes après | Lignes touchées | Détail |
| --- | --- | --- | --- | --- |
| `type_columns` | 5 656 | 5 656 | 0 | columns_cast = 18, values_coerced = 0 |
| `normalize_texts` | 5 656 | 5 656 | 183 | blank_to_na = 0, names_fixed = 103, brands_unified = 82, codes_stripped = 0 |
| `enforce_unique_code` | 5 656 | 5 596 | 60 | rows_without_code = 0, duplicates_removed = 60, codes_concerned = 60 |
| `normalize_grade` | 5 596 | 5 596 | 3 764 | not_applicable = 132, unknown = 3 632 |
| `drop_unclassifiable` | 5 596 | 2 393 | 3 203 | unclassifiable_dropped = 3 203 |
| `reconcile_salt_sodium` | 2 393 | 2 393 | 17 | sodium_recomputed = 17, salt_derived = 0, sodium_derived = 0 |
| `reconcile_kcal_kj` | 2 393 | 2 393 | 181 | ratio_inconsistent = 181, kcal_recomputed = 181 |
| `neutralize_range:fat_100g` | 2 393 | 2 393 | 30 | invalid_to_na = 30 |
| `neutralize_range:saturated_fat_100g` | 2 393 | 2 393 | 10 | invalid_to_na = 10 |
| `neutralize_range:carbohydrates_100g` | 2 393 | 2 393 | 119 | invalid_to_na = 119 |
| `neutralize_range:sugars_100g` | 2 393 | 2 393 | 97 | invalid_to_na = 97 |
| `neutralize_range:fiber_100g` | 2 393 | 2 393 | 6 | invalid_to_na = 6 |
| `neutralize_range:proteins_100g` | 2 393 | 2 393 | 5 | invalid_to_na = 5 |
| `neutralize_range:salt_100g` | 2 393 | 2 393 | 58 | invalid_to_na = 58 |
| `neutralize_range:sodium_100g` | 2 393 | 2 393 | 58 | invalid_to_na = 58 |
| `neutralize_range:fruits_vegetables_legumes_100g` | 2 393 | 2 393 | 6 | invalid_to_na = 6 |
| `neutralize_range:energy_kcal_100g` | 2 393 | 2 393 | 126 | invalid_to_na = 126 |
| `neutralize_range:energy_kj_100g` | 2 393 | 2 393 | 126 | invalid_to_na = 126 |
| `neutralize_subpart_above_total` | 2 393 | 2 393 | 134 | sugars_above_carbs = 69, saturated_above_fat = 70 |
| `handle_allergens_unknown` | 2 393 | 2 393 | 892 | flagged = 892, empty_to_na = 892, none_declared = 628 |
| `missing_strategy` | 2 393 | 2 393 | 0 | flags_set = 11, constants_filled = 0, deferred = 3, columns_dropped = 0 |
| `fill_saturated_zero_if_low_fat` | 2 393 | 2 393 | 68 | set_to_zero = 68 |
| `fix_inconsistent_energy` | 2 393 | 2 393 | 81 | zero_recomputed = 48, zero_invalidated = 1, deviation_recomputed = 32, deviation_invalidated = 0 |
| `drop_rows_without_key_nutrient` | 2 393 | 2 072 | 321 | rows_dropped = 321 |
| `derive_missing_energy` | 2 072 | 2 072 | 17 | kcal_from_kj = 14, kcal_from_macros = 3, flagged = 137 |

## 3. Anomalies métier avant / après

| Anomalie | Avant | Après |
| --- | --- | --- |
| fat_100g hors de [0 ; 100] | 33 | 0 |
| saturated_fat_100g hors de [0 ; 100] | 12 | 0 |
| carbohydrates_100g hors de [0 ; 100] | 124 | 0 |
| sugars_100g hors de [0 ; 100] | 102 | 0 |
| fiber_100g hors de [0 ; 100] | 8 | 0 |
| proteins_100g hors de [0 ; 100] | 10 | 0 |
| salt_100g hors de [0 ; 100] | 101 | 0 |
| sodium_100g hors de [0 ; 40] | 101 | 0 |
| fruits_vegetables_legumes_100g hors de [0 ; 100] | 7 | 0 |
| energy_kcal_100g hors de [0 ; 900] | 156 | 0 |
| energy_kj_100g hors de [0 ; 3765,6] | 136 | 0 |
| sucres > glucides + 0,5 | 106 | 0 |
| saturés > lipides + 0,5 | 100 | 0 |
| sel ≠ sodium × 2,5 (écart > 0,1) | 30 | 0 |
| rapport kJ / kcal hors de [3,9 ; 4,5] | 410 | 0 |
| kcal nulles avec un macronutriment positif (hors alcool) | 111 | 0 |
| kcal à plus de 50 % du calcul 4/4/9 (hors alcool) | 106 | 0 |
| lignes sans code | 0 | 0 |
| codes en double (lignes en trop) | 60 | 0 |

## 4. Manquants sur les colonnes clés

| Colonne | Manquants avant | % | Manquants après | % |
| --- | --- | --- | --- | --- |
| energy_kcal_100g | 1 465 | 25,9 % | 137 | 6,6 % |
| energy_kj_100g | 1 448 | 25,6 % | 142 | 6,9 % |
| saturated_fat_100g | 1 779 | 31,5 % | 105 | 5,1 % |
| sugars_100g | 1 721 | 30,4 % | 246 | 11,9 % |
| proteins_100g | 1 495 | 26,4 % | 37 | 1,8 % |
| salt_100g | 1 983 | 35,1 % | 189 | 9,1 % |
| sodium_100g | 1 983 | 35,1 % | 189 | 9,1 % |
| fat_100g | 1 491 | 26,4 % | 52 | 2,5 % |
| carbohydrates_100g | 1 495 | 26,4 % | 157 | 7,6 % |
| fiber_100g | 3 296 | 58,3 % | 730 | 35,2 % |
| nutriscore_grade | 80 | 1,4 % | 309 | 14,9 % |
| brands | 1 995 | 35,3 % | 393 | 19,0 % |

## 5. Produits par rayon après nettoyage

| Rayon | Produits | Part |
| --- | --- | --- |
| `unknown` | 496 | 23,9 % |
| `en:sugary-snacks` | 320 | 15,4 % |
| `en:fish-meat-eggs` | 209 | 10,1 % |
| `en:milk-and-dairy-products` | 198 | 9,6 % |
| `en:beverages` | 186 | 9,0 % |
| `en:cereals-and-potatoes` | 186 | 9,0 % |
| `en:fats-and-sauces` | 161 | 7,8 % |
| `en:composite-foods` | 120 | 5,8 % |
| `en:fruits-and-vegetables` | 105 | 5,1 % |
| `en:salty-snacks` | 76 | 3,7 % |
| `en:alcoholic-beverages` | 8 | 0,4 % |
| `en:baby-foods-and-milks` | 7 | 0,3 % |

## 6. Colonnes ajoutées et retirées

- Ajoutées : `allergens_missing`, `brands_missing`, `carbohydrates_100g_missing`, `energy_kcal_100g_missing`, `fat_100g_missing`, `fiber_100g_missing`, `fruits_vegetables_legumes_100g_missing`, `grade_not_applicable`, `ingredients_text_missing`, `nova_group_missing`, `product_name_missing`, `proteins_100g_missing`, `saturated_fat_100g_missing`, `sugars_100g_missing`
- Retirées : aucune
