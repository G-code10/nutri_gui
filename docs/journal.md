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

création de sql/create_db.sql, modification par rapport a l'énoncé, les colonnes sont traduites en anglais

# TP5 - Parties prenantes et persona 

Carte des partie prenantes réalisé avec 3 personnas différentes, trame d'entretien faite et entretien "réel" fait, tout est dans docs/cadrage/parties_prenantes.md

# TP6 - Opportunités et concurrence

Benchmark existant fait, et matrice comparitive, Swot effectué et proposition de valeur énoncé, docs/cadrage/benchmark.md est commité

# TP7 - KPI, coûts & ROI

Définition des KPI, Hypothèse de cout et revenu faite, ROI fait sur les trois scénarios demandé, cependant des valeurs comme le nombre de token sont inventé, le ROI n'est pas forcément fiable, a revoir
docs/cadrage/kpi_roi.xlsx commité

# TP8 - Note de cadrage & backlog

Note de cadrage + backlog outillé, docs/cadrage/planning.md commité

# TP9 - Nettoyage industrialisé 

Il a été décidé a partir de ce TP que chacun de nous travaillerais sur son propre repo
En effet l'expérience entre les différents développeur est très différentes, certains travaillant beaucoup plus vite que d'autre, il vallais mieux séparer les repo afin que chacun puisse avancer a son rythme sur les TPs, car sinon il y avais de gros risque qu'un seul développeur soit responsable de plus de 80% du code, et je voulais être seul pour mieux m'approprier les différents principes et méthodes qu'on me présente dans les TP et exercices

### Fait

- `src/cleaning.py` : 15 règles pures, chacune renvoie `(DataFrame, RuleReport)`, enchaînées par `clean()` dans l'ordre du TP.
- `tests/` : 171 tests verts (règles, schéma, création de base, chargement, rapport, pipeline, extraction). Chaque règle a un test nominal, un cas tordu, un test de pureté et un test d'idempotence sur l'échantillon réel.
- `docs/data/strategie_manquants.md` : décision par colonne et par usage, appliquée par le code.
- `python -m src.report` : génère `docs/data/rapport_nettoyage.md`, identique d'une exécution à l'autre (à la date près).
- Base PostgreSQL : `sql/create_db.sql` (6 tables, clés, contraintes `CHECK`), `src/create_db.py`, `src/load_db.py` (`ValueError` si `code` n'est pas unique, requêtes de contrôle).
- `python -m src.pipeline` : lecture, nettoyage, rapport, base. Testé sur la table complète : 4 636 471 lignes lues, 1 586 106 gardées, chargement réussi. Durée 4 min 22, mémoire 4,5 à 5,5 Go, pic à 10,2 Go à la lecture.

### Décidé

- **La base ne reçoit que des données nettoyées** (elle porte des `CHECK`). L'échantillon brut des tests est donc reconstruit depuis le parquet (`scripts/make_sample_raw.py`).
- **Création et chargement séparés** (`create_db.py`, `load_db.py`). Configuration : nom de base et mot de passe dans `db.env` (hors Git), le reste dans `CONF`. Les tests utilisent une base séparée (`TEST_DATABASE_URL`), avec un garde-fou contre la vraie base.
- **Ordre du TP respecté : unités avant bornes.** Un sel aberrant avec un sodium valide fait perdre le sodium (on ne sait pas lequel des deux est faux).
- **Aucune imputation statistique** dans le nettoyage : elle viendra dans le pipeline ML, après le split.
- **Source par défaut = table complète** (`data/raw/products_nutrition.parquet`, produite par `extract.py`) ; l'échantillon reste disponible avec `--source`.
- `pd.options.mode.copy_on_write = True` est gardée comme le TP le demande ; sous pandas 3 elle n'a plus d'effet (avertissement inoffensif).

### Bloqué / corrigé en route

- **Idempotence de la règle 13 (corrigé).** Sur le jeu complet, une ligne à kcal = kJ = 0 avec des macronutriments minuscules était comptée « touchée » à chaque passage sans rien changer. Corrigé en ne comptant que les valeurs réellement modifiées (`_changed`), avec un test de non-régression. Deux passes de `clean()` donnent désormais un résultat identique sur le jeu complet.
- **Chargement refusé par PostgreSQL (corrigé).** Des caractères nuls (0x00) dans `brands` faisaient échouer `COPY`. Ajout d'une sous-règle `nul_removed` dans `normalize_texts`, avec test.

### Points ouverts

- **Énergie résiduelle :** le rapport compte encore 612 lignes au rapport kJ/kcal hors plage et 69 lignes à kcal nulles avec macronutriments positifs. Ce sont surtout des valeurs minuscules où l'arrondi à 0,1 kcal fausse le rapport. Quelques lignes ont des macronutriments élevés pour une énergie ≤ 0,7 kcal (probablement des boissons alcoolisées, non vérifié). Laissé tel quel.
- **Rayon `unknown` (18,9 % des produits gardés) :** la règle 5 supprime les produits sans catégorie, pas ceux au rayon inconnu. Un produit qui a des catégories mais pas de `food_groups_tag_1` reste donc, avec le rayon `unknown` à l'insertion. Conforme à l'énoncé, à garder en tête pour les analyses par rayon.
- **Nutri-Score hors −15..40 :** 2 849 valeurs (≈ 0,2 %), laissées telles quelles, à revoir à l'analyse exploratoire (TP 10).

### Écarts avec l'énoncé

- Nous travaillons sur le parquet Open Food Facts et non sur `echantillon_france.csv` : les comptes de contrôle de l'énoncé ne sont pas comparables aux nôtres.
- Le rayon est `food_groups_tag_1` (pas `pnns_groups_1`) ; un rayon manquant devient `unknown` en base.
- PostgreSQL à la place de SQLite, pandas 3.0 à la place de 2.3.

# TP10 - Analyse exploratoire

Passé pour le moment

# TP11 - Datastorytelling

Passé pour le moment

# TP12 - Parquet & DuckDB

### Décisions

- CSV non mesuré dans le benchmark : le format Parquet est retenu depuis le TP 1, toute la chaîne en part. pandas lit le Parquet nettoyé (colonnes utiles seulement) ; le bonus « DuckDB sur CSV » est remplacé par DuckDB sur le Parquet non partitionné, qui mesure l'effet du partitionnement.
- Requêtes du benchmark choisies d'après l'énoncé du TP 10, l'EDA n'étant pas encore réalisée.
- Mémoire mesurée par psutil sous Windows (resource n'y existe pas) et par VmHWM sous Linux : ru_maxrss reprenait le pic du processus parent (161 Mo pour tous les moteurs).
- Deux documents de benchmark : docs/data/benchmark_mesures.md, généré par le script (à ne pas modifier à la main), et docs/data/benchmark.md, rédigé (lecture, limites, conséquences).
- Journal des durées (data/durees.jsonl) ajouté en anticipation du TP 13 : aucune mesure codée en dur ni saisie à la main, la base n'étant construite que par le pipeline, et le TP 13 le demandera. Contrainte : seules les étapes réussies sont inscrites pour l'instant ; les échecs viendront avec l'orchestration (TP 13).
- Export features : tolérance de 0,5 conservée dans les filtres (sucres ≤ glucides + 0,5, saturés ≤ lipides + 0,5), comme au nettoyage, au lieu de l'inégalité stricte de l'énoncé.
- Export features : ratios bornés à [0, 1] (plafond à 1, nombre de produits plafonnés écrit dans le schéma), 0 si numérateur et dénominateur valent 0, NULL si seul le dénominateur vaut 0. Règles propres à l'export, le nettoyage n'est pas modifié. Raison : sur l'extrait France, des dénominateurs minuscules donnaient des ratios jusqu'à 1 million.
- Export features : schéma nommé features_nutriscore_<AAAAMMJJ>.schema.json (au lieu de schema.json) pour que plusieurs exports datés coexistent dans data/exports/.
- Export features : politique de manquants « flag », lue dans cleaning.DEFAULT_MISSING_STRATEGY (flag par défaut pour additives_n et les ratios). Les colonnes _missing ne sont pas exportées : la politique est écrite dans le schéma et sera appliquée au TP 14.
- Les sept nutriments clés sont centralisés dans config.CORE_NUTRIENTS (benchmark et export).
- Les schémas JSON (schema_produits.json, schéma de l'export) ne sont pas committés : ils restent à côté de leurs données dans data/, ignoré par Git.

### À reprendre plus tard

- Après l'EDA (TP 10) : revoir les requêtes du benchmark et la rédaction de docs/data/benchmark.md.
- Après les TP 10, 13 et 14 : revoir docs/architecture.md (mentions « À faire », paragraphe de l'exercice 3.5.2, API, assistant, phase 6-7).
- TP 13 : en fin de session, après les TP 12 et 13, revoir les tests superflus et mettre en commun raw_product, needs_db et TEST_DATABASE_URL dans tests/conftest.py (aujourd'hui répétés dans plusieurs fichiers de test).
- TP 13 : renommer le paramètre run de run_queries.checks (même nom que la fonction run du module).
- TP 13 : inscrire aussi les étapes en échec dans le journal des durées (data/durees.jsonl), avec l'orchestration.
- TP 13 : commande unique qui enchaîne extraction, pipeline, conversion, contrôles et export (déjà signalée dans docs/architecture.md).
- TP 13 : découpage train / test de l'export features, stratifié sur la cible, avec sa graine, gelé dans data/exports/.
- TP 14 : appliquer la politique de manquants écrite dans le schéma de l'export (flag), les colonnes _missing n'étant pas exportées.

# TP13 - Pipeline bout-en-bout
