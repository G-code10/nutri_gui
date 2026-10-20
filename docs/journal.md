# Journal de bord

# TP1 - Démarrage



### Choix du format

Nous avons choisi le format .parquet, c'est le format le plus léger entre le CSV de 9Go et celui-ci de 7.2Go

Nous l'avons choisi pour sa capacité à lire les colonnes séparémment. Sa réputation sur ses performance nous a confirmé dans cette direction.

# TP2 - Profiling & périmètre

Renseigné les valeurs vides sur la majorité des colonnes dans le perimetre.
Il faudra vérifier les colonnes s'approchant des 0% de valeur nulles, ceci est surement dû au fait que la colonnes ont un formattage pré-établi, il faudra éclater la structure et récupérer les valeurs nulles présentes sur les différents éléments de la structure.

# TP3 - Le dépot au propre

Le dépot nutriscope a été crée, branche main protégé, branche features, gitignore itinialisé, protection pull request activé

# TP4 - La base nutriscope

création de sql/create_db.sql, modification par rapport a l'énoncé, les colonnes sont traduites en anglais, ajout d'une table aisle supplémentaire

# TP5 - Parties prenantes et persona 

Carte des partie prenantes réalisé avec 3 personnas différentes, trame d'entretien faite et entretien "réel" fait, tout est dans docs/cadrage/parties_prenantes.md

# TP6 - Opportunités et concurrence

Benchmark existant fait, et matrice comparitive, Swot effectué et proposition de valeur énoncé, docs/cadrage/benchmark.md est commité

# TP7 - KPI, coûts & ROI

Définition des KPI, Hypothèse de cout et revenu faite, ROI fait sur les trois scénarios demandé, cependant certaines valeurs comme le nombre de token au moins sont inventé, le ROI n'est pas forcément fiable, a revoir
docs/cadrage/kpi_roi.xlsx commité

# TP8 - Note de cadrage & backlog

Note de cadrage + backlog outillé, docs/cadrage/planning.md commité

# TP9 - Nettoyage industrialisé 

Il a été décidé a partir de ce TP que chacun de nous travaillerais sur son propre repo
En effet l'expérience entre les différents développeur est très différentes, certains travaillant beaucoup plus vite que d'autre, il vallais mieux séparer les repo afin que chacun puisse avancer a son rythme sur les TPs, car sinon il y avais de gros risque qu'un seul développeur soit responsable de plus de 80% du code, et je voulais développer seul pour mieux m'approprier les différents principes et méthodes qu'on me présente dans les TP et exercices

### Fait

- `src/cleaning.py` : 15 règles pures, chacune renvoie `(DataFrame, RuleReport)`, avec docstring et constantes nommées. `clean()` les enchaîne dans l'ordre du TP : types, textes, doublons, grade, inclassables, unités (sel/sodium, kcal/kJ), bornes (11 colonnes), sous-parties, allergènes, stratégie de manquants, saturées, énergie, lignes sans nutriment clé, kcal dérivées.
- `tests/` : 157 tests, tous verts (règles, schéma, création de base, chargement, rapport, pipeline). Chaque règle a un test nominal, un cas tordu et un test de pureté. L'idempotence est testée règle par règle sur l'échantillon réel.
- `docs/data/strategie_manquants.md` : décision par colonne et par usage, appliquée par `DEFAULT_MISSING_STRATEGY` (vocabulaire fermé, `ValueError` si la décision est inconnue).
- `python -m src.report` : génère `docs/data/rapport_nettoyage.md` ; régénéré deux fois, le fichier est identique à la date près.
- Base PostgreSQL : `sql/create_db.sql` (6 tables, clés primaires et étrangères, contraintes `CHECK`), `src/create_db.py` (création de la base et du schéma), `src/load_db.py` (chargement par `COPY` dans une seule transaction, `ValueError` si `code` n'est pas unique, validation par le schéma pandera de `src/schema.py`).
- `python -m src.pipeline` : lecture, règles, rapport, base. Sur l'échantillon : 5 656 lignes lues, 2 072 gardées ; aisles 12, brands 1 345, categories 1 592, products 2 072, nutrients 2 072, product_categories 10 400 ; 0 produit sans catégorie, 0 code en double.

### Décidé

- **La base ne reçoit que des données nettoyées.** Elle porte des contraintes `CHECK` : elle ne peut pas contenir les anomalies dont le test d'idempotence a besoin. L'échantillon brut est donc reconstruit directement depuis le parquet Open Food Facts, avec la requête DuckDB retenue après différents exercices sur ce fichier (`scripts/make_sample_raw.py`, une seule commande, sans serveur ni identifiants).
- **Schéma en plusieurs tables** (`aisles`, `brands`, `categories`, `products`, `nutrients`, `product_categories`) plutôt qu'une table à plat ; `main_category` est conservée. Trois drapeaux seulement sont stockés en base (`grade_not_applicable`, `saturated_fat_100g_missing`, `energy_kcal_100g_missing`).
- **Ordre du TP respecté : unités avant bornes.** Conséquence connue : un sel aberrant (5 000 g) avec un sodium valide donne un sodium recalculé aberrant, donc sel et sodium à NA ; on perd un sodium correct, faute de savoir lequel des deux est faux.
- **Défaut trouvé par le test d'idempotence sur l'échantillon réel :** des kcal absentes, dérivées des kJ par la dernière règle, n'étaient pas contrôlées par la règle d'énergie. Corrigé par `_effective_kcal`, avec deux tests de non-régression. Quand le recalcul 4/4/9 est impossible, kcal et kJ passent à NA ensemble.
- **Aucune imputation statistique** dans le nettoyage : `median_by_group` et `mode` sont reconnues mais appliquées plus tard, dans le pipeline ML, après le split.
- **Création et chargement séparés** (`create_db.py`, `load_db.py`) ; la base est créée si elle manque. Le chargement recrée le schéma : rechargement complet, jamais de doublon.
- **Configuration :** hôte, port et utilisateur dans `CONF` (`load_db.py`), nom de la base et mot de passe dans `db.env` (ignoré par Git, modèle `db.env.example`). Les tests avec base utilisent une base séparée, `TEST_DATABASE_URL`, créée automatiquement, un garde-fou arrête les tests si l'URL vise la vraie base.
- `pd.options.mode.copy_on_write = True` est conservée en tête des modules car demandé sur le TP cependant avec pandas 3 elle n'a plus d'effet et affiche un avertissement

### Écarts avec l'énoncé

- L'énoncé est écrit pour le CSV de l'extrait France (`echantillon_france.csv`, 8 689 produits) ; nous travaillons sur le parquet. Les comptes de contrôle de l'énoncé (120 valeurs au-dessus de 100 g, 26 doublons) ne sont donc pas comparables aux nôtres.
- Le rayon est `food_groups_tag_1` (colonne du parquet), pas `pnns_groups_1`. Un rayon manquant devient `unknown` à l'insertion en base.
- Identifiants de code en anglais (`RuleReport`, `clean`), docstrings en français ; pandas 3.0 au lieu de 2.3 ; PostgreSQL au lieu de SQLite.

### Bloqué / à faire

- **Source par défaut :** `report.py` et `pipeline.py` lisent l'échantillon (`DEFAULT_SOURCE`). À passer au parquet complet (4,6 millions de produits) quand l'étape de lecture extraira la table `products_nutrition` complète. Mesurer alors la mémoire et la durée de `clean()` avec pandas.
- **Chargement jamais essayé sur le jeu complet :** un caractère particulier dans un texte (par exemple un caractère nul) pourrait faire échouer `COPY`.
- **Scores Nutri-Score hors −15..40 :** 2 849 valeurs (environ 0,2 %), laissées telles quelles ; à examiner à l'analyse exploratoire (TP 10). Une règle de bornage reste possible.

# TP10 - Analyse exploratoire

Bypass pour le moment

# TP11 - Datastorytelling

Bypass pour le moment

# TP12 - Parquet & DuckDB

