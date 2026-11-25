# Journal de bord

# TP1 - Démarrage

### Choix du format

Format Parquet retenu : plus léger que le CSV (7,2 Go contre 9 Go) et il permet de lire les colonnes séparément.

# TP2 - Profiling & périmètre

Taux de valeurs vides renseigné sur la majorité des colonnes du périmètre.
À vérifier : les colonnes proches de 0 % de vides ont sûrement une structure imbriquée, il faudra l'éclater pour retrouver les vrais vides.

# TP3 - Le dépôt au propre

Dépôt nutriscope créé : branche main protégée, branche features, .gitignore, pull request obligatoire.

# TP4 - La base nutriscope

sql/create_db.sql créé, avec les noms de colonnes traduits en anglais (écart à l'énoncé).

# TP5 - Parties prenantes et persona

Carte des parties prenantes, 3 personas, trame d'entretien et un entretien réel : docs/cadrage/parties_prenantes.md.

# TP6 - Opportunités et concurrence

Benchmark de l'existant, matrice comparative, SWOT et proposition de valeur : docs/cadrage/benchmark.md.

# TP7 - KPI, coûts & ROI

KPI, hypothèses de coûts et revenus, ROI sur les trois scénarios : docs/cadrage/kpi_roi.xlsx.
Limite : certaines valeurs (nombre de tokens) sont inventées, le ROI est à revoir.

# TP8 - Note de cadrage & backlog

Note de cadrage et backlog outillé : docs/cadrage/planning.md.

# TP9 - Nettoyage industrialisé

À partir de ce TP, chacun travaille sur son propre dépôt : nos niveaux sont très différents, et sur un dépôt commun un seul développeur aurait écrit l'essentiel du code. Seul, je m'approprie mieux les méthodes des TP.

### Fait

- src/cleaning.py : 15 règles enchaînées par clean() dans l'ordre du TP.
- 171 tests : pour chaque règle, un cas normal, un cas limite, la pureté et l'idempotence.
- docs/data/strategie_manquants.md : stratégie de manquants par colonne, appliquée par le code.
- Rapport de nettoyage généré (docs/data/rapport_nettoyage.md), identique d'une exécution à l'autre.
- Base PostgreSQL : 6 tables avec clés et contraintes CHECK, création et chargement en deux scripts.
- Pipeline testé sur la table complète : 4 636 471 lignes lues, 1 586 106 gardées, en 4 min 22 (pic mémoire 10,2 Go à la lecture).

### Décidé

- La base ne reçoit que des données nettoyées, parce qu'elle porte des CHECK.
- Mot de passe dans db.env (hors Git) ; les tests utilisent une base séparée, avec un garde-fou contre la vraie base.
- Unités avant bornes, comme le TP : un sel aberrant avec un sodium valide fait perdre les deux, on ne sait pas lequel est faux.
- Pas d'imputation dans le nettoyage : elle se fait dans le pipeline ML, après le split, pour éviter la fuite de données.

### Corrigé en route

- Règle 13 non idempotente : une ligne était comptée modifiée à chaque passage sans changer. Corrigé en ne comptant que les vraies modifications.
- Chargement PostgreSQL refusé à cause de caractères nuls dans brands : ajout d'une sous-règle qui les retire.

### Points ouverts

- Énergie : 612 lignes au rapport kJ/kcal hors plage et 69 à 0 kcal avec des macronutriments, surtout des petites valeurs mal arrondies. Laissé tel quel.
- Rayon unknown pour 18,9 % des produits (catégories présentes mais pas de food_groups_tag_1). Conforme à l'énoncé, à garder en tête pour les analyses par rayon.
- 2 849 Nutri-Scores hors −15..40 (0,2 %), laissés tels quels.

### Écarts avec l'énoncé

- Parquet Open Food Facts au lieu de echantillon_france.csv : les comptes de l'énoncé ne sont pas comparables.
- Rayon = food_groups_tag_1 au lieu de pnns_groups_1.
- PostgreSQL au lieu de SQLite, pandas 3.0 au lieu de 2.3.

# TP10 - Analyse exploratoire

Passé pour le moment.

# TP11 - Datastorytelling

Passé pour le moment.

# TP12 - Parquet & DuckDB

### Décisions

- CSV non mesuré dans le benchmark, parce que le Parquet est retenu depuis le TP 1. Le bonus « DuckDB sur CSV » est remplacé par DuckDB sur le Parquet non partitionné, pour mesurer l'effet du partitionnement.
- Mémoire mesurée avec psutil, parce que le module resource n'existe pas sous Windows.
- Deux documents : benchmark_mesures.md, généré par le script, et benchmark.md, rédigé à la main.
- Journal des durées écrit par le pipeline, pour n'avoir aucune mesure saisie à la main.
- Export features :
    tolérance de 0,5 dans les filtres (sucres ≤ glucides + 0,5), comme au nettoyage, au lieu de l'inégalité stricte de l'énoncé.
    ratios bornés à [0, 1], parce que des dénominateurs minuscules donnaient des ratios jusqu'à 1 million.
    schéma daté (features_nutriscore_<AAAAMMJJ>.schema.json) pour que plusieurs exports coexistent.
    pas de colonnes _missing : les manquants sont traités dans le pipeline ML.
- Les schémas JSON restent à côté de leurs données dans data/, hors Git.

### À reprendre

- Après l'EDA : revoir les requêtes du benchmark et docs/data/benchmark.md.
- Après les TP 10, 13 et 14 : mettre à jour docs/architecture.md.

# TP13 - Pipeline bout-en-bout

### Décisions

- Point d'entrée unique : python -m nutriscope.pipeline [load|clean|load_db|parquet|export|all|reset]. Pas de Makefile, parce que make n'est pas installé par défaut sous Windows.
- Ancien src/pipeline.py renommé src/clean_pipeline.py pour ne pas avoir deux pipeline.py.
- Les cinq étapes ont la même signature et reçoivent le même contexte, créé une fois au lancement.
- Contrôles automatiques : la base est vérifiée après chargement, le Parquet est comparé à la base.
- Sorties datées (<nom>_<AAAAMMJJ>) : chaque étape lit la sortie la plus récente de l'étape d'avant, sinon elle dit quelle étape lancer.
- Trois versions gardées par sortie ; les exports ne sont jamais supprimés, parce qu'ils sont figés.
- Manifeste avec le SHA-256 de la source et du brut, pour prouver d'où viennent les données.
- Trois périmètres : France (par défaut), --full, --sample.
- Split : colonne split dans l'export, stratifiée sur le grade, 20 % de test, graine 42, figée pour que tous les modèles soient comparés sur le même test (méthode revue le 16/11).
- pyproject.toml ajouté pour pip install -e . (non demandé, cité dans le dépannage de l'énoncé).
- docker-compose.yml versionné ; le mot de passe reste dans db.env.

### Écarts à l'énoncé

- Noms d'étapes en anglais (load, clean, load_db, parquet, export).
- Export nommé features_nutriscore_<AAAAMMJJ> au lieu de features_<AAAAMMJJ>.
- Pas de data/db/ : la base est un serveur PostgreSQL dans Docker.

### Résultats

- Extrait France : 1 247 336 lignes brutes, 521 240 nettoyées, 456 380 dans l'export. Pipeline complet en 2 min environ : pas besoin d'orchestrateur.
- Reproductibilité : export du 10/11 refait dans un clone neuf, même SHA-256 que celui du 09/11 (avant le changement de split du 16/11).
- README testé dans un clone neuf, manques corrigés.

### À reprendre

- docs/architecture.md : mettre à jour les commandes et les noms.
- Script de téléchargement de food.parquet, hors pipeline.

# TP 14 - Prédire le Nutri-Score (classification a→e)

### Synthèse

La forêt aléatoire (class_weight="balanced") obtient un F1 macro de 0,920 sur le test (0,898 sans les jumeaux), contre 0,77 pour la régression logistique et 0,09 pour la classe majoritaire. Ses erreurs portent sur des grades voisins, et les plus confiantes viennent des données (fiches fausses, catégorie absente, boissons), pas du modèle.

### Données

Export features avec split figé, validation croisée à 5 plis dans le train, test regardé une seule fois.
Features : nutriments, fibres, fruits-légumes, NOVA, additifs, rayons, 3 ratios et l'écart d'énergie ; imputation médiane, standardisation, one-hot.

### Constats

- L'accuracy trompe : la classe majoritaire a 0,29 d'accuracy mais 0,09 de F1 macro, d'où le choix du F1 macro.
- Jumeaux : 20 % des produits de validation ont un jumeau exact dans le train, ce qui gonfle le F1 d'environ 0,02. Mesure « sans jumeau » ajoutée.
- Fuite : nutriscore_score donnait 0,994 de F1 ; retiré des features, avec un garde-fou testé.
- Importances cohérentes avec le barème Nutri-Score (sel, sucres, saturés en tête).
- Déséquilibre des classes : class_weight="balanced" retenu, SMOTE n'apporte rien de plus.

### Actions pour le TP 9

Estimer les fruits-légumes à partir de la catégorie ; marquer comme suspect le grade d'une fiche dont l'énergie a été corrigée.
Limite : les produits notés avec l'algorithme des boissons.

# 16/11/2026 - Refactorisation de export_features.py

Objectif : modifier le fichier pour pouvoir l'expliquer plus simplement (détail dans le commit 2548d17).

### Décisions

- Split : train_test_split de scikit-learn (stratifié sur le grade, graine 42, 20 % de test) à la place du générateur fait main, parce que c'est l'outil standard, plus court et plus facile à justifier.
- Requête SQL écrite en clair dans _build_query, parce qu'elle se lit d'un coup au lieu d'être assemblée par plusieurs fonctions.
- Schéma allégé (plus de ratios plafonnés, de politique de manquants ni d'infos Git), parce que ces informations n'étaient pas demandées et compliquaient le code.

### À reprendre

- Le split a changé : un nouvel export n'aura plus le même SHA-256 que ceux du 09/11 et du 10/11.
- La politique de manquants n'est plus dans le schéma : la lire dans cleaning.DEFAULT_MISSING_STRATEGY.

# 23/11/2026 - Préparation de l'assistant (TP 21)

Objectif : décider comment construire l'assistant conversationnel (agent, RAG, outils ML et DL) à partir du cours 006 sur les frameworks LLM.

### Décisions

- L'agent n'est pas une compétence du référentiel en lui-même. Il sert surtout C1.5 (présenter les modèles aux utilisateurs) et C3.1 (veille, IA générative). Il devra être exposé par une API web, un notebook ne suffit pas.
- Deux outils distincts pour un produit. La recherche par code-barres dans la base renvoie le grade déjà connu, sans ML. La prédiction du Nutri-Score ne sert que pour un produit inconnu, à partir de son étiquette scannée, parce que prédire un grade déjà en base n'a pas d'intérêt.
- LlamaIndex pour le RAG, LangChain pour orchestrer l'assistant. Le corpus sera fait de documents bruts de formats variés : LlamaIndex fournit leur lecture, leur découpage et leur réindexation, qu'il faudrait sinon écrire à la main format par format. Je veux aussi maîtriser cet outil pour des utilisations futures. Ses vecteurs sont stockés dans Chroma. LlamaIndex ne fait que chercher, c'est LangChain qui génère les réponses (pas de llama-index-llms-ollama). LangSmith est écarté parce que c'est un service en ligne (les conversations sortiraient de la machine).
- MLflow pour le suivi, en local. Côté ML, chaque entraînement garde ses hyperparamètres, ses métriques et le modèle sauvegardé, ce qu'un fichier joblib seul ne garde pas. Côté assistant, il remplace LangSmith pour tracer les conversations sans que rien ne sorte de la machine. Le modèle reste sérialisé avec pickle, donc ne jamais charger un modèle d'origine inconnue. Les données de MLflow (mlruns/) restent hors Git. Le journal JSONL demandé au TP 21 reste nécessaire. Pas de serveur MLflow dans docker-compose pour l'instant : un dossier local suffit pour apprendre l'outil.
- Dépendances ajoutées à requirements.txt (pas encore installées) : langchain, langchain-openai, langgraph pour l'assistant, chromadb, llama-index-core, llama-index-vector-stores-chroma, llama-index-embeddings-ollama pour le RAG, mlflow pour le suivi. ChatOpenAI plutôt que ChatOllama, parce que c'est le même format OpenAI que l'atelier scanner : on passe d'Ollama à un fournisseur en ligne en changeant l'adresse et le nom du modèle.
- Plan du TP 21 : outils search_product, suggest_substitutes et answer_with_sources en placeholders qui respectent les contrats du TP 18 et du TP 19, données inventées signalées comme telles. Pour le RAG, d'abord un placeholder, puis un mini-index LlamaIndex sur quelques documents si le temps le permet. Mémoire courte avec InMemorySaver (un thread_id par conversation). Journalisation simple (chronomètre autour de chaque échange, outils et tokens lus dans les messages, une ligne JSONL par échange) plutôt qu'une classe de callbacks.
- RGPD : une photo d'étiquette peut contenir des données personnelles (visage, ticket, coordonnées GPS dans les EXIF). Avant un envoi chez un fournisseur en ligne, l'utilisateur doit savoir quelle donnée part, chez qui, pour quoi et combien de temps elle est gardée. Sinon, analyse en local avec Ollama.

### Essai des traces MLflow

Agent minimal (create_agent, ChatOpenAI branché sur qwen3:8b dans Ollama, un outil factice), MLflow 3.18 avec mlflow.langchain.autolog().

- Les tokens de chaque appel au modèle sont dans la trace, identiques à usage_metadata (167 et 241, puis 240 et 378), avec le total de l'échange (407 en entrée, 619 en sortie).
- La trace donne la durée de chaque étape : 14,3 s pour l'échange, environ 7 s par appel au modèle, moins de 0,01 s pour l'outil.
- Deux appels au modèle par question avec un outil : le premier demande l'outil, le second rédige la réponse. Le second relit tout l'historique, d'où plus de tokens en entrée.
- MLflow écrit ses traces en arrière-plan : pour les relire aussitôt dans le code, il faut forcer l'écriture (MLFLOW_ENABLE_ASYNC_TRACE_LOGGING=false).
- Avec un stockage SQLite, ajouter mlflow.db au .gitignore.
- qwen3:8b produit beaucoup de tokens de sortie, même pour un simple appel d'outil (il raisonne avant de répondre) : piste pour réduire la latence.

### À reprendre

- src/ml : aucun modèle sauvegardé ni fonction de prédiction pour un seul produit. Entraînement final et sauvegarde à faire avec MLflow.
- Mesurer la baisse du F1 macro quand les colonnes absentes d'une étiquette (nova_group, aisle, aisle2, peut-être fruits-légumes et additifs) sont mises à NaN. À faire sur une validation tirée du train, pas sur le test, pour garder le test neutre.
- Vérifier si load_image (atelier scanner) supprime les EXIF au ré-encodage.
- langsmith est installé automatiquement avec langchain : vérifier que LANGSMITH_TRACING n'est pas activé.
- Rédiger une ADR sur les choix d'outils de l'assistant (LangChain, LlamaIndex, MLflow).
- Reporter la justification des nouvelles librairies dans le README.
- RAG : choisir entre tout indexer avec LlamaIndex (fiches et documents) ou garder les fiches dans rechercher().
- Ajouter un lecteur de fichiers selon les formats du corpus (par exemple pypdf pour les PDF).
- Noms des outils en anglais : écart au contrat du TP 18, qui impose chercher_produit à toutes les équipes. À signaler à la revue croisée.
- Au déploiement (J6) : envisager un serveur MLflow dans docker-compose, avec ses données dans PostgreSQL, pour que l'API charge le modèle depuis ce serveur.

# 24/11/2026 - Corpus du RAG et lecteurs de fichiers (TP 21)

### Décisions

- Corpus du RAG : les pages et documents officiels conseillés (Vie publique, Santé.fr, Santé publique France, recommandations PNNS adultes, avis du HCSP de 2017). Ciqual n'est pas retenu.
- Le tableau des sources (id, titre, éditeur, URL, dates, licence) sera versionné dans docs/ : il sert C1.2 (sources listées) et C5.5 (licences). Trois licences restent à vérifier (Santé.fr, Santé publique France).
- llama-index-readers-file écarté : toutes ses versions récentes imposent pandas<3, ce qui aurait rétrogradé pandas 3.0.5 pour tout le projet (pipeline du bloc 2, pandera). À la place : pypdf pour les PDF et beautifulsoup4 pour les pages web (balise "main" seulement). Deux petites fonctions rendent des "Document" LlamaIndex, qui reste chargé du découpage, de l'indexation dans Chroma et de la recherche.
- pypdf 6.21.4 et beautifulsoup4 4.15.0 installés, aucun conflit (pip check), pandas toujours en 3.0.5.

### À reprendre

- Télécharger les 5 documents dans data/corpus/ et remplir le tableau des sources.
- Lire les conditions d'utilisation de Santé.fr et de Santé publique France avant d'indexer.
- Vérifier pour chaque page que le contenu utile est bien dans la balise "main".
- Section 3 du notebook TP 21 limitée aux 5 documents. Les fiches produits passent par l'outil search_product.
- Pour le vrai code (src/) : le TP 19 demande aussi les fiches produits dans le corpus (une fiche = un morceau, documents longs découpés avec chevauchement). Décider si on les indexe avec LlamaIndex.
- Tableau des sources et licences à écrire dans docs/ia/corpus.md (fichier attendu par le TP 19).
- Jeu d'évaluation du TP 20 : 30 questions (factuelles, comparatives, 5 pièges hors périmètre) avec réponses et sources attendues, hit rate et MRR, deux améliorations mesurées.

# 25/11/2026 - Lecture et découpage du corpus, reprise du corpus d'un collègue (TP 21)

### Ce qui a été fait

- Section 3.3 du notebook TP 21 : lecture des 5 documents (pages web avec beautifulsoup4, balise "main" seulement, PDF avec pypdf), un Document LlamaIndex par source avec ses métadonnées (source_id, titre, éditeur, URL, date de consultation, licence). URL, date et licence exclues de la vectorisation.
- Cellule de contrôle du texte extrait : aucune page de PDF vide, mais beaucoup de bruit.
- Section 3.4 : découpage avec SentenceSplitter (chunk_size 512, chunk_overlap 64), 154 morceaux.

### Problèmes constatés

- Bruit dans le texte extrait. En-tête du PDF PNNS répété 61 fois (une fois par page), en-tête du HCSP 9 fois, mots coupés par pypdf ("l eur", "nouv eaux"), sommaire du PNNS avec ses lignes de points, liens et listes d'autres articles dans la balise "main" des pages web ("En bref", "Lire l'article", "version française").
- Corpus déséquilibré : le PNNS fournit 116 morceaux sur 154 (75 %).
- Chevauchement irrégulier : 95 paires de morceaux consécutifs sur 149 se chevauchent. SentenceSplitter ne répète que des phrases entières, et le texte des pages web a beaucoup de lignes sans ponctuation.
- Licence du HCSP : l'avis indique "Cet avis doit être diffusé dans sa totalité, sans ajout ni modification". À prendre en compte avant d'en citer des extraits.

### Décision

- Pas de nettoyage de notre extraction. On reprend le corpus d'un collègue, déjà fourni et correctement découpé. Raisons : nettoyer notre texte demanderait du travail (en-têtes, sommaire, menus, mots coupés) pour refaire ce qui existe déjà dans l'équipe, et un corpus plus fourni et propre donnera une recherche plus fiable que nos 5 documents bruts. Le temps gagné va à l'assistant lui-même (outils, agent, mémoire, journalisation).
- Les sections 3.3 et 3.4 ont servi à comprendre la lecture et le découpage, et à mesurer ce qu'une extraction brute donne (un "avant" chiffré).

### À reprendre

- Vérifier le corpus du collègue : provenance et licence de chaque source, stratégie de découpage et sa justification (demandée au TP 19), métadonnées disponibles pour citer les sources (id, titre, URL, date).
- Vérifier avec quel modèle d'embeddings il a été vectorisé, s'il l'a été : documents et questions doivent passer par le même modèle.
- Décider quoi garder des sections 3.3 et 3.4 dans le notebook.
- Si le corpus arrive déjà découpé en fichiers texte, pypdf et beautifulsoup4 ne servent peut-être plus : à retirer de requirements.txt et de CLAUDE.md le cas échéant.

### Corpus du collègue (scan du 25/11)

- 26 sources conservées (21 pages Manger Bouger, 1 page Santé publique France, 4 PDF), 407 morceaux propres en fichiers chunk_N.txt, un dossier par source. Le dossier "Non Conservés" (bilans du PNNS 4, rapport Igas) n'est pas à indexer, et un .zip fait doublon.
- Le PNNS 5 (2026-2030) n'était découpé qu'en 2 morceaux, dont un de 184 602 caractères : source retirée du corpus plutôt que redécoupée.
- Pas de chevauchement entre morceaux, et aucune métadonnée dans les fichiers (ni URL, ni date, ni licence) : il faudra le tableau des sources pour citer.
- pypdf et beautifulsoup4 retirés de requirements.txt et de CLAUDE.md. Les cellules 3.3 et 3.4 du notebook restent comme démonstration, avec leurs sorties, mais ne se relancent plus (dépendances et fichiers retirés).

### Stockage de Chroma (C1.2, bloc 2 : acquérir, stocker et analyser des données)

- Phrase pour l'oral (critère "Les différents composants de l'architecture de l'entrepôt de données sont expliqués") : Chroma stocke les textes et les métadonnées dans SQLite, et les vecteurs dans un index HNSW à côté.
- Sur le disque, en mode persistant : un fichier chroma.sqlite3 (collections, textes, métadonnées, identifiants) et un dossier par collection avec les fichiers .bin de l'index HNSW (graphe qui relie chaque vecteur à ses voisins proches, pour une recherche rapide mais approximative).
- Mode persistant (comme SQLite, sans serveur, un seul programme à la fois) pour le notebook. Mode serveur dans docker-compose à envisager au déploiement (J6) si l'API et l'indexation doivent accéder à la base en même temps.

### Avancement du notebook TP 21 (25/11)

- passage au corpus du collègue (25 sources, 405 morceaux) qui est indexé dans Chroma "data/index_rag/". La recherche fonctionne : la question sur la charcuterie trouve deux sources qui donnent la réponse (150 g par semaine).
- Piège noté : le connecteur Chroma de LlamaIndex rend exp(-distance), pas 1 - distance. On recalcule la similarité cosinus avec 1 + log
- Reste : 3.7 (petite mesure, avec plusieurs sources attendues par question), 3.8 (search_docs), puis sections 4 à 8.
- Toujours manquant : les fiches produits à mettre dans le RAG 
