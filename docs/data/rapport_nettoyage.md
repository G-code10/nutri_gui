# Rapport de nettoyage

- Date : 2026-10-21
- Source : `data/raw/products_nutrition.parquet`
- Données : Open Food Facts, © Open Food Facts contributors, licence ODbL.
- Généré par `python -m src.report` : ne pas modifier à la main.

## 1. Volumétrie

|  | Avant | Après |
| --- | --- | --- |
| Lignes | 4 636 471 | 1 586 106 |
| Colonnes | 27 | 41 |
| Codes distincts | 4 636 411 | 1 586 106 |

## 2. Lignes touchées par règle

Une ligne touchée par plusieurs sous-règles compte une fois dans « lignes touchées » et une fois par sous-règle dans le détail.

| Règle | Lignes avant | Lignes après | Lignes touchées | Détail |
| --- | --- | --- | --- | --- |
| `type_columns` | 4 636 471 | 4 636 471 | 0 | columns_cast = 18, values_coerced = 0 |
| `normalize_texts` | 4 636 471 | 4 636 471 | 350 202 | nul_removed = 13, blank_to_na = 1, names_fixed = 70 382, brands_unified = 297 930, codes_stripped = 0 |
| `enforce_unique_code` | 4 636 471 | 4 636 410 | 61 | rows_without_code = 1, duplicates_removed = 60, codes_concerned = 60 |
| `normalize_grade` | 4 636 410 | 4 636 410 | 3 211 949 | not_applicable = 101 212, unknown = 3 110 737 |
| `drop_unclassifiable` | 4 636 410 | 1 864 421 | 2 771 989 | unclassifiable_dropped = 2 771 989 |
| `reconcile_salt_sodium` | 1 864 421 | 1 864 421 | 8 822 | sodium_recomputed = 8 821, salt_derived = 1, sodium_derived = 0 |
| `reconcile_kcal_kj` | 1 864 421 | 1 864 421 | 131 450 | ratio_inconsistent = 131 459, kcal_recomputed = 131 450 |
| `neutralize_range:fat_100g` | 1 864 421 | 1 864 421 | 5 883 | invalid_to_na = 5 883 |
| `neutralize_range:saturated_fat_100g` | 1 864 421 | 1 864 421 | 902 | invalid_to_na = 902 |
| `neutralize_range:carbohydrates_100g` | 1 864 421 | 1 864 421 | 13 434 | invalid_to_na = 13 434 |
| `neutralize_range:sugars_100g` | 1 864 421 | 1 864 421 | 6 231 | invalid_to_na = 6 231 |
| `neutralize_range:fiber_100g` | 1 864 421 | 1 864 421 | 411 | invalid_to_na = 411 |
| `neutralize_range:proteins_100g` | 1 864 421 | 1 864 421 | 1 446 | invalid_to_na = 1 446 |
| `neutralize_range:salt_100g` | 1 864 421 | 1 864 421 | 1 325 | invalid_to_na = 1 325 |
| `neutralize_range:sodium_100g` | 1 864 421 | 1 864 421 | 1 325 | invalid_to_na = 1 325 |
| `neutralize_range:fruits_vegetables_legumes_100g` | 1 864 421 | 1 864 421 | 2 631 | invalid_to_na = 2 631 |
| `neutralize_range:energy_kcal_100g` | 1 864 421 | 1 864 421 | 15 436 | invalid_to_na = 15 436 |
| `neutralize_range:energy_kj_100g` | 1 864 421 | 1 864 421 | 15 708 | invalid_to_na = 15 708 |
| `neutralize_subpart_above_total` | 1 864 421 | 1 864 421 | 2 749 | sugars_above_carbs = 1 696, saturated_above_fat = 1 136 |
| `handle_allergens_unknown` | 1 864 421 | 1 864 421 | 772 053 | flagged = 772 067, empty_to_na = 772 053, none_declared = 449 911 |
| `missing_strategy` | 1 864 421 | 1 864 421 | 0 | flags_set = 11, constants_filled = 0, deferred = 3, columns_dropped = 0 |
| `fill_saturated_zero_if_low_fat` | 1 864 421 | 1 864 421 | 45 085 | set_to_zero = 45 085 |
| `fix_inconsistent_energy` | 1 864 421 | 1 864 421 | 13 163 | zero_recomputed = 4 808, zero_invalidated = 101, deviation_recomputed = 8 195, deviation_invalidated = 59 |
| `drop_rows_without_key_nutrient` | 1 864 421 | 1 586 106 | 278 315 | rows_dropped = 278 315 |
| `derive_missing_energy` | 1 586 106 | 1 586 106 | 8 670 | kcal_from_kj = 6 501, kcal_from_macros = 2 169, flagged = 29 828 |

## 3. Anomalies métier avant / après

| Anomalie | Avant | Après |
| --- | --- | --- |
| fat_100g hors de [0 ; 100] | 6 334 | 0 |
| saturated_fat_100g hors de [0 ; 100] | 1 075 | 0 |
| carbohydrates_100g hors de [0 ; 100] | 14 335 | 0 |
| sugars_100g hors de [0 ; 100] | 6 531 | 0 |
| fiber_100g hors de [0 ; 100] | 604 | 0 |
| proteins_100g hors de [0 ; 100] | 1 857 | 0 |
| salt_100g hors de [0 ; 100] | 2 543 | 0 |
| sodium_100g hors de [0 ; 40] | 2 637 | 0 |
| fruits_vegetables_legumes_100g hors de [0 ; 100] | 3 029 | 0 |
| energy_kcal_100g hors de [0 ; 900] | 19 947 | 0 |
| energy_kj_100g hors de [0 ; 3765,6] | 17 897 | 0 |
| sucres > glucides + 0,5 | 2 848 | 0 |
| saturés > lipides + 0,5 | 1 725 | 0 |
| sel ≠ sodium × 2,5 (écart > 0,1) | 13 801 | 0 |
| rapport kJ / kcal hors de [3,9 ; 4,5] | 322 768 | 612 |
| kcal nulles avec un macronutriment positif (hors alcool) | 11 310 | 69 |
| kcal à plus de 50 % du calcul 4/4/9 (hors alcool) | 63 829 | 0 |
| lignes sans code | 1 | 0 |
| codes en double (lignes en trop) | 60 | 0 |

## 4. Manquants sur les colonnes clés

| Colonne | Manquants avant | % | Manquants après | % |
| --- | --- | --- | --- | --- |
| energy_kcal_100g | 1 291 656 | 27,9 % | 29 828 | 1,9 % |
| energy_kj_100g | 1 283 648 | 27,7 % | 32 402 | 2,0 % |
| saturated_fat_100g | 1 564 311 | 33,7 % | 46 291 | 2,9 % |
| sugars_100g | 1 504 274 | 32,4 % | 68 874 | 4,3 % |
| proteins_100g | 1 316 249 | 28,4 % | 28 061 | 1,8 % |
| salt_100g | 1 736 095 | 37,4 % | 106 509 | 6,7 % |
| sodium_100g | 1 736 094 | 37,4 % | 106 509 | 6,7 % |
| fat_100g | 1 321 219 | 28,5 % | 32 072 | 2,0 % |
| carbohydrates_100g | 1 318 649 | 28,4 % | 41 527 | 2,6 % |
| fiber_100g | 2 860 659 | 61,7 % | 622 956 | 39,3 % |
| nutriscore_grade | 43 447 | 0,9 % | 216 944 | 13,7 % |
| brands | 1 703 767 | 36,7 % | 327 905 | 20,7 % |

## 5. Produits par rayon après nettoyage

| Rayon | Produits | Part |
| --- | --- | --- |
| `unknown` | 300 448 | 18,9 % |
| `en:sugary-snacks` | 261 253 | 16,5 % |
| `en:cereals-and-potatoes` | 174 698 | 11,0 % |
| `en:fish-meat-eggs` | 169 039 | 10,7 % |
| `en:milk-and-dairy-products` | 160 897 | 10,1 % |
| `en:beverages` | 138 280 | 8,7 % |
| `en:fats-and-sauces` | 115 149 | 7,3 % |
| `en:composite-foods` | 96 390 | 6,1 % |
| `en:fruits-and-vegetables` | 86 090 | 5,4 % |
| `en:salty-snacks` | 67 952 | 4,3 % |
| `en:alcoholic-beverages` | 11 598 | 0,7 % |
| `en:baby-foods-and-milks` | 4 312 | 0,3 % |

## 6. Colonnes ajoutées et retirées

- Ajoutées : `allergens_missing`, `brands_missing`, `carbohydrates_100g_missing`, `energy_kcal_100g_missing`, `fat_100g_missing`, `fiber_100g_missing`, `fruits_vegetables_legumes_100g_missing`, `grade_not_applicable`, `ingredients_text_missing`, `nova_group_missing`, `product_name_missing`, `proteins_100g_missing`, `saturated_fat_100g_missing`, `sugars_100g_missing`
- Retirées : aucune
