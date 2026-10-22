# Contrôles du stockage analytique

- Date : 2026-10-22
- Source : `data/parquet/produits` (521 240 produits)
- Données : Open Food Facts contributors - ODbL (https://opendatacommons.org/licenses/odbl/1-0/).
- Requêtes : `sql/controles.sql` ; paramètres tirés de `src/cleaning.py` : kcal_max = 900, sugars_tolerance = 0.5, saturated_tolerance = 0.5, salt_per_sodium = 2.5, salt_sodium_tolerance = 0.1, alcohol_group = en:alcoholic-beverages
- Généré par `python -m src.storage.run_queries` : ne pas modifier à la main.

## Vérifications

| Vérification | Résultat |
| --- | --- |
| la somme du comptage par rayon égale la volumétrie totale | ✓ |
| une ligne par rayon (aucun rayon en double) | ✓ |
| 0 code en double | ✓ |
| 0 valeur hors bornes | ✓ |
| les cinq grades a-e sont présents | ✓ |

## Parquet / base

Mêmes requêtes sur les deux moteurs ; résultats identiques.

| Contrôle | Identique |
| --- | --- |
| volumétrie | oui |
| 1. Comptage par rayon | oui |
| 2. Complétude par rayon (%) | oui |
| 3. Doublons | oui |
| 4. Bornes et cohérences | oui |
| 5. Distribution du Nutri-Score | oui |

## 1. Comptage par rayon

| rayon | produits | part_pct |
| --- | --- | --- |
| en-sugary-snacks | 100 663 | 19,3 |
| en-fish-meat-eggs | 81 245 | 15,6 |
| en-milk-and-dairy-products | 55 804 | 10,7 |
| en-cereals-and-potatoes | 51 651 | 9,9 |
| unknown | 51 100 | 9,8 |
| en-beverages | 41 177 | 7,9 |
| en-composite-foods | 36 949 | 7,1 |
| en-fats-and-sauces | 35 076 | 6,7 |
| en-fruits-and-vegetables | 32 295 | 6,2 |
| en-salty-snacks | 28 103 | 5,4 |
| en-alcoholic-beverages | 4 779 | 0,9 |
| en-baby-foods-and-milks | 2 398 | 0,5 |

## 2. Complétude par rayon (%)

| rayon | produits | nutriscore_pct | sept_nutriments_pct | categories_pct |
| --- | --- | --- | --- | --- |
| en-alcoholic-beverages | 4 779 | 1,1 | 45,8 | 100,0 |
| en-baby-foods-and-milks | 2 398 | 0,0 | 92,4 | 100,0 |
| en-beverages | 41 177 | 78,2 | 89,1 | 100,0 |
| en-cereals-and-potatoes | 51 651 | 90,9 | 94,3 | 100,0 |
| en-composite-foods | 36 949 | 96,0 | 97,7 | 100,0 |
| en-fats-and-sauces | 35 076 | 88,3 | 94,5 | 100,0 |
| en-fish-meat-eggs | 81 245 | 96,3 | 96,6 | 100,0 |
| en-fruits-and-vegetables | 32 295 | 89,7 | 91,5 | 100,0 |
| en-milk-and-dairy-products | 55 804 | 95,6 | 96,3 | 100,0 |
| en-salty-snacks | 28 103 | 95,6 | 96,1 | 100,0 |
| en-sugary-snacks | 100 663 | 91,3 | 93,7 | 100,0 |
| unknown | 51 100 | 70,1 | 90,7 | 100,0 |

Catégories : 100 % attendu partout, le nettoyage supprime les produits sans catégorie.

## 3. Doublons

| controle | groupes | lignes_en_trop |
| --- | --- | --- |
| codes en double | 0 | 0 |
| couples nom + marque répétés | 19 105 | 34 698 |

## 4. Bornes et cohérences

| ordre | nature | anomalie | produits |
| --- | --- | --- | --- |
| 1 | borne | nutriment hors [0, 100] g | 0 |
| 2 | borne | énergie hors [0, 900] kcal | 0 |
| 3 | cohérence | sucres > glucides + 0.5 g | 0 |
| 4 | cohérence | saturés > lipides + 0.5 g | 0 |
| 5 | cohérence | sel ≠ sodium × 2.5 (écart > 0.1 g) | 0 |
| 6 | cohérence | énergie nulle avec un macronutriment positif (hors alcool) | 33 |

Bornes : 0 attendu. Cohérences : mêmes tolérances que le nettoyage ; les lignes restantes sont listées ici, pas filtrées : une valeur à corriger revient au nettoyage sous forme de règle.

## 5. Distribution du Nutri-Score

| grade | produits | part_pct | score_moyen |
| --- | --- | --- | --- |
| a | 62 006 | 11,9 | -2,9 |
| b | 48 936 | 9,4 | 0,6 |
| c | 95 688 | 18,4 | 5,6 |
| d | 122 309 | 23,5 | 14,1 |
| e | 131 862 | 25,3 | 23,3 |
| not-applicable | 21 372 | 4,1 | — |
| null | 39 067 | 7,5 | — |

« unknown » et « not-applicable » sont effacés au nettoyage : not-applicable reste visible par le drapeau grade_not_applicable, unknown est compté dans null. La part d'« unknown » dans le brut figure dans docs/data/rapport_nettoyage.md (règle normalize_grade).
