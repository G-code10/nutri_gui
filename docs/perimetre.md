# TP2 - Profiling & périmètre
<hr>

## Périmètre retenu (avant meeting)
<pre>

[Colonnes retenues]
[Exemple de donnée] 
[Raison du choix / Critère]
[Nombre / Pourcentage de valeurs null]

<span style="color:green"><strong>allergens_tags</strong></span>
[
  "en:nuts"
]
Afin de pouvoir signaler les différents allergènes présent dans le produit

<span style="color:green"><strong>brands</strong></span>
Bovetti
Donnée brut, simple texte, importance de connaître la marque. Pour une tracabilité et rassurer la clientèle.
nombre de valeur nulle : 1595058 soit 34.4%

<span style="color:green"><strong>categories</strong></span>
Plant-based foods and beverages, Beverages, Hot beverages, Plant-based beverages, Teas, Tea bags
Donnée <strong>très importante</strong>, à compléter pour le calcule du nutriscore

<span style="color:green"><strong>code</strong></span>
0000101209159
Donnée brut, simple texte, important pour retrouver la donnée grâce au code-barre
Colonne code : nombre de valeur nulle : 0 soit 0.0%
nombre de valeur fausse : 323624 soit 6.98% (code ne respectant pas les 13caractères EAN13)

<span style="color:green"><strong>completeness</strong></span>
0.7875
Savoir si les informations sont complètes.
Colonne completness : nombre de valeur nulle : 18 soit 0.0004%
nombre de valeur fausse : 4309 soit 0.09% (completeness a 0 ou au dessus de 1.1)

<span style="color:green"><strong>countries_tags</strong></span>
[
    "en:france"
]
Dans quel pays trouver le produit, pour filtrer c'est important.
<span style="color: red;">
Colonne écartée
Colonne countries_tag : nombre de valeur nulle : 9741 soit 0.2101%

<strong>data_quality_errors_tags</strong>
[
    "en:nutrition-value-total-over-105","en:energy-value-in-kcal-does-not-match-value-computed-from-other-nutrients"
]
Récupérer les erreurs pour mettre en avant une erreur de complétion</span>

<span style="color:green"><strong>entry_dates_tags</strong></span>
[
  "2017-03-09",
  "2017-03",
  "2017"
]
Fonctionne bien avec l'obsolescence des informations, plus pour le côté gestion des données, sans forcément afficher cette info
Colonne data_quality_errors_tags : nombre de valeur nulle : 4 soit 0.0001%
nombre de valeur au mauvais type : 0 soit 0.0%
nombre de date au mauvais format : 2717 soit 0.0586%

<span style="color:green"><strong>food_groups_tags</strong></span>
[
  "en:beverages",
  "en:unsweetened-beverages"
]
Colonne food_group_tags : nombre de valeur nulle : 43426 soit 0.9366%

<span style="color:green"><strong>images</strong></span>
[
    {
        "key":"1"
        ... (très long)
    }
]
Permet d'afficher une petite image du produit

<span style="color:green"><strong>ingredients_analysis_tags</strong></span>
[
  "en:palm-oil-free",
  "en:maybe-vegan",
  "en:vegetarian"
]
Des informations importantes à récupérer pour l'alimentation de chacun
Colonne ingredients_analysis_tags : nombre de valeur nulle : 3262715 soit 70.3707%

<strong>ingredients_original_tags</strong> <span style="color:lightblue">Vérifier avec la prochaine colonne</span>
[
  "en:hazelnut",
  "en:cocoa dark chocolate",
  "en:sugar",
  "en:cocoa-paste",
  "en:sugar",
  "en:cocoa-butter",
  "en:vanilla-extract"
]
Colonne ingredients_original_tags : nombre de valeur nulle : 3340219 soit 72.0423%

<span style="color:green"><strong>ingredients_tags</strong></span>
[
  "en:hazelnut",
  "en:nut",
  "en:tree-nut",
  "en:cocoa dark chocolate",
  "en:sugar",
  "en:added-sugar",
  "en:disaccharide",
  "en:cocoa-paste",
  "en:plant",
  "en:cocoa",
  "en:cocoa-butter",
  "en:oil-and-fat",
  "en:vegetable-oil-and-fat",
  "en:vegetable-fat",
  "en:vanilla-extract",
  "en:extract",
  "en:vanilla",
  "en:vegetable-extract"
]
Permet d'établir une liste en cas d'alergène
Colonne ingredients_tags : nombre de valeur nulle : 3340216 soit 72.0422%

<span style="color:green"><strong>ingredients_text</strong></span>
[
  {
    "lang": "main",
    "text": "HAZELNUTS, 73% cocoa dark chocolate (cocoa mass, sugar, cocoa butter, vanilla extract), sugar, rapeseed oil\r\n\r\nMay contain traces of other nuts, milk, and soy."
  },
  {
    "lang": "en",
    "text": "HAZELNUTS, 73% cocoa dark chocolate (cocoa mass, sugar, cocoa butter, vanilla extract), sugar, rapeseed oil\r\n\r\nMay contain traces of other nuts, milk, and soy."
  },
  {
    "lang": "en",
    "text": "<span class=\"allergen\">HAZELNUTS</span>, 73% cocoa dark chocolate (cocoa mass, sugar, cocoa butter, vanilla extract), sugar, rapeseed oil\r\n\r\nMay contain traces of other <span class=\"allergen\">nuts</span>, <span class=\"allergen\">milk</span>, and <span class=\"allergen\">soy</span>."
  }
]
Permet d'établir une liste en cas d'alergène en récupérant le span .allergen
Colonne ingredients_text : nombre de valeur nulle : 0 soit 0.0%

<span style="color:green"><strong>ingredients</strong></span>
Donnée trop longue...
À récupérer à la place des trois précédentes, mais possède énormément de keys et values.
Colonne ingredients : nombre de valeur nulle : 3340217 soit 72.04%

<span style="color:green"><strong>lang</strong></span>
fr
Permet de filtrer par langue
Colonne lang : nombre de valeur nulle : 4 soit 0.0%

<span style="color:green"><strong>nova_groups_tags</strong></span>
[
  "en:3-processed-foods" (ultra, unprocessed, processed-minimaly etc...)
]
Savoir si l'aliment est transformé ou non, 
<span style="color: red;">
Colonne écartée
Colonne nova_groups_tags : nombre de valeur nulle : 43420 soit 0.9365%

<strong>nutrient_levels_tags</strong>
[
  "en:fat-in-high-quantity",
  "en:saturated-fat-in-high-quantity",
  "en:sugars-in-high-quantity",
  "en:salt-in-low-quantity"
]
</span>
<span style="color:green"><strong>nutriments</strong></span>
[
  {
    "name": "saturated-fat",
    "value": null,
    "100g": 10, <span style="color:lightblue">À vérifier</span>
    "serving": null,
    "unit": "g", <span style="color:lightblue">À vérifier</span>
    "prepared_value": null,
    "prepared_100g": null,
    "prepared_serving": null,
    "prepared_unit": null
  }, 
  ...
]

<span style ="color:green"><strong>nutriscore_grade</strong></span>
e
Grade du nutriscore, pas besoin d'argumenté
Colonne nutriscore_grade : nombre de valeur nulle : 43447 soit 0.94%

<span style ="color:green"><strong>nutriscore_score</strong></span>
25
Nutriscore, pas besoin d'argumenté
Colonne nutriscore_score : nombre de valeur nulle : 3255402 soit 70.2129%

<span style ="color:green"><strong>obsolete</strong></span>
false / true
Nous permet de filtrer directement les produits obsolètes.
Pas de valeur nulle, un bool ne peut être qu'a True ou False

<strong>origins_tags</strong> <span style="color:lightblue">Vérifier l'info</span>
...

<span style="color:green"><strong>packaging_recycling_tags</strong></span> <span style="color:yellow">Selon la décfision du client</span>
[
  "en:recycle-in-sorting-bin"
]
eco responsable
Colonne packaging_recycling_tags : nombre de valeur nulle : 43154 soit 0.9308%

<span style="color:green"><strong>packaging_shapes_tags</strong></span> <span style="color:yellow">Selon la décision du client</span>
[
  "en:jar",
  "en:lid"
]
Rappel de comment trier le packaging
Colonne packaging_shapes_tags : nombre de valeur nulle : 43154 soit 0.9308%



<span style="color:green"><strong>popularity_tags</strong></span> <span style="color: yellow;">Selon la décision du client</span>
[
  "top-75-percent-scans-2024",
  "top-80-percent-scans-2024",
  "top-85-percent-scans-2024",
  "top-90-percent-scans-2024",
  "top-1000-sg-scans-2024",
  "top-5000-sg-scans-2024",
  "top-10000-sg-scans-2024",
  "top-50000-sg-scans-2024",
  "top-100000-sg-scans-2024",
  "top-country-sg-scans-2024",
  "top-75-percent-scans-2025",
  "top-80-percent-scans-2025",
  "top-85-percent-scans-2025",
  "top-90-percent-scans-2025",
  "top-50000-gb-scans-2025",
  "top-100000-gb-scans-2025",
  "top-country-gb-scans-2025"
]
Colonne popularity_tags : nombre de valeur nulle : 3085050 soit 66.5388%

<span style="color:green"><strong>product_name</strong></span>
[
  {
    "lang": "main",
    "text": "Véritable pâte à tartiner noisettes chocolat noir"
  },
  {
    "lang": "fr",
    "text": "Véritable pâte à tartiner noisettes chocolat noir"
  }
]
Le nom de notre produit c'est important.
Colonne product_name : nombre de valeur nulle : 0 soit 0.00%

<span style="color:green"><strong>product_quantity</strong></span>
350

<span style="color:green"><strong>product_quantity_unit</strong></span>
g
<span style="color: red;">
Colonne écartée

<strong>quantity</strong>
350 g
Hésitation avec la quantité et la quantité du produit, celle-ci a le "g" et l'autre non.
Les deux peuvent être complémentaire.</span>

<span style="color:green"><strong>states_tags</strong></span>
[
  "en:to-be-completed",
  "en:nutrition-facts-completed",
  "en:ingredients-completed",
  "en:expiration-date-completed",
  "en:packaging-code-to-be-completed",
  "en:characteristics-to-be-completed",
  "en:origins-to-be-completed",
  "en:categories-completed",
  "en:brands-completed",
  "en:packaging-to-be-completed",
  "en:quantity-completed",
  "en:product-name-completed",
  "en:photos-to-be-validated",
  "en:packaging-photo-to-be-selected",
  "en:nutrition-photo-selected",
  "en:ingredients-photo-selected",
  "en:front-photo-selected",
  "en:photos-uploaded"
]
Permet d'identifier les cases manquantes d'un produits assez rapidement.
Colonne states_tags : nombre de valeur nulle : 3 soit 0.0001%

<strong>vitamins_tags</strong> <span style="color:lightblue">Vérifier si l'info n'est pas ailleurs <span style="color:lightgreen">UPDATE : info dans ingredients_tags, MAIS pas les même vitamines, problème de cohérence des informations</span></span>
[
  "en:vitamin-e",
  "en:dl-alpha-tocopheryl-acetate",
  "en:retinyl-palmitate",
  "en:cholecalciferol"
]
Un plus
</pre>
Colonne vitamins_tag : nombre de valeur nulle : 2622167 soit 56.5552%

## <span style="color:red">Ce qu'on écarte et pourquoi</span>

<pre>

[Colonnes écartées]
[Pourquoi]

<strong>Filtre après meeting :</strong>
['data-quality-errors-tags','nutrient_levels_tags', quantity]
Écartées après un premier meeting pour cause que les données présentées peuvent être calculées par nos soins au lieu de faire confiance à l'entrée ou la récupération de ces données.
Colonne data_quality_errors_tags : nombre de valeur nulle : 43069 soit 0.9289%

<strong>Information non pertinente :</strong>
[exemple : 'created_t', 'creator', 'last_editor', ...]
Pas nécessaire de garder ces colonnes pour connaître qui a ajouté ce produit ou l'a édité.

<strong>Doublons :</strong>
['countries', 'countries_tags']
Ce genre d'exemple, nous avons préféré prendre seulement une sur les deux, car cela faisait énormément de redondances dans les données
</pre>

## Décision de périmètre

### Rayons couverts au lancement classé du plus grand nombre au plus petits

- Snacking sucré (en:sugary-snacks)

- Poisson/Viande/Oeufs ou produits a base de (en:fish-meat-eggs)

- Céréales/Patates ou produits a base de (en:cereals-and-potatoes)

- Lait et produit laitiers (en:milk-and-dairy-products)

- Boissons (en:beverages)

- Sauces/graisse/huiles (en:fats-and-sauces)

- Fruit et légumes ou produits a base de (en:fruits-and-vegetables)

- Plats préparés (en:composite-foods)

- Snacking salé (en-salty-snacks)

### Rayons exclus

- unknown (nan)

- Boissons alcolisés (en:alcoholic-beverages)

- Nourriture et lait pour bébé, nutriscore totalement absent (en:baby-foods-and-milks)

### colonnes concervées

- "code" (code unique)
- "brands"
- "categories_tags"
- "product_name" ('fr' par défaut, si pas trouvé pour le champ 'lang' mettre 'main')
- "ingredients_text", 
- "nova_group"
- "nutriscore_score"
- "nutriments"(au moins energy-kcal_100g, sugars_100g, salt_100g, fiber_100g, fruit-vegetables-legumes_100g, a réanalyser pour vois si les autres nutriment serait utile) 
- "serving_size"

### Seuil de complétude minimal par produit

Le produit est conservé SI ET SEULEMENT SI les colonnes code, product_name, et l'énergie dans nutriments sont présentes à 100%"

### Stratégie de valeurs manquantes par colonne et par usage

| colonne | usage | manquants | décision | pourquoi |
|---|---|---|---|---|
| brands | affichage, substitution (même marque), assistant | 34 % | garder NA + drapeau ; « inconnue » à l'affichage seulement | aucune valeur plausible à inventer |
| categories_tags | substitution, features ML (rayon), assistant | 56 % | règle métier : inclassable si vide et rayon unknown → hors périmètre | sans catégorie, pas de substitution |
| ingredients_text | assistant, features texte | 72 % | garder NA + drapeau | aucune valeur plausible à inventer |
| nova_group | affichage | 75 % | garder NA + drapeau | dérivée des ingrédients, si ingredient absent = 98.5% de chance que nova absent aussi |
| nutriscore_score/_grade | cible du modèle, affichage | 34 % | garder ; « unknown » → NA ; jamais imputer | une cible imputée est une cible inventée |
| energy_kcal_100g | score, affichage, features ML, substitution, assistant | 28 % | imputation métier : kJ / 4,184, sinon 4/4/9 ; reste → médiane par rayon calculée sur le train uniquement, après le split | dérivable avant d'être devinée |
| sugars_100g | score, features ML, affichage, assistant | 32 % | garder NA + drapeau sucres_manquant, jamais imputer | une valeur inventée fausserait le score, manque MAR lié à la complétude de la fiche et au rayon |
| salt_100g / sodium_100g | score, features ML, substitution, affichage, assistant | 37 % | imputation métier : sel = sodium × 2,5 (et inverse) | relation exacte, zéro risque |
| fiber_100g | score, features ML, substitution, affichage, assistant | 62 % | garder NA + drapeau fiber_manquant | MNAR : absence = souvent « pas de fibres » |
| fruit_vegetables_legumes_100g | score, features ML, subsitution, affichage, assistant | 83 % | NA + drapeau, jamais imputer | a limité aux rayons elle est indiqué, sinon traiter NA comme 0 et l'afficher |
| serving_size | sel par portion (affichage) | 68 % | a garder, affichage des valeurs pour 100g si NA | utile quand présente, jamais imputée |
| fat_100g | features ML, contrôle de cohérence, substitution, affichage, assistant | 28 % | garder NA + drapeau fat_manquant ; métier (énergie − 4 × protéines − 4 × glucides) / 9 possible si les 3 sont présentes ; reste → médiane par rayon calculée sur le train uniquement, après le split | MAR : suit la complétude du tableau nutritionnel ; sert de borne haute pour les saturées |
| proteins_100g | score, features ML, affichage, substitution, assistant | 28 % | garder NA + drapeau proteines_manquant ; reste → médiane par rayon calculée sur le train uniquement, après le split ; score non calculable si NA | MAR : manque groupé composante favorable du Nutri-Score |
| carbohydrates_100g | features ML, contrôle de cohérence, substitution, affichage, assistant | 28 % | garder NA + drapeau glucides_manquant ; valeurs > 100 → NA ; sert de borne haute pour sugars_100g ; jamais imputée | utile au profil nutritionnel ; une valeur inventée fausserait les contrôles de cohérence |
| saturated_fat_100g | score, features ML, affichage, substitution, assistant | 34 % | garder NA + drapeau graisses_sat_manquant, règle métier : si fat_100g < 0,5 g → saturées = 0 ; sinon jamais imputer ; score non calculable si NA | composante directe du Nutri-Score, une valeur inventée fausserait le score |
| produit sans aucun nutriment clé | — | 27 % | supprimer la ligne | inutilisable pour le score et la substitution |