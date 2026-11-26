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

Déplacé dans docs/todo.md le 26/11.
Limite : les produits notés avec l'algorithme des boissons.

# 16/11/2026 - Refactorisation de export_features.py

Objectif : modifier le fichier pour pouvoir l'expliquer plus simplement (détail dans le commit 2548d17).

### Décisions

- Split : train_test_split de scikit-learn (stratifié sur le grade, graine 42, 20 % de test) à la place du générateur fait main, parce que c'est l'outil standard, plus court et plus facile à justifier.
- Requête SQL écrite en clair dans _build_query, parce qu'elle se lit d'un coup au lieu d'être assemblée par plusieurs fonctions.
- Schéma allégé (plus de ratios plafonnés, de politique de manquants ni d'infos Git), parce que ces informations n'étaient pas demandées et compliquaient le code.

### Conséquences à connaître

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

# 24/11/2026 - Corpus du RAG et lecteurs de fichiers (TP 21)

### Décisions

- Corpus du RAG : les pages et documents officiels conseillés (Vie publique, Santé.fr, Santé publique France, recommandations PNNS adultes, avis du HCSP de 2017). Ciqual n'est pas retenu.
- Le tableau des sources (id, titre, éditeur, URL, dates, licence) sera versionné dans docs/ : il sert C1.2 (sources listées) et C5.5 (licences). Trois licences restent à vérifier (Santé.fr, Santé publique France).
- llama-index-readers-file écarté : toutes ses versions récentes imposent pandas<3, ce qui aurait rétrogradé pandas 3.0.5 pour tout le projet (pipeline du bloc 2, pandera). À la place : pypdf pour les PDF et beautifulsoup4 pour les pages web (balise "main" seulement). Deux petites fonctions rendent des "Document" LlamaIndex, qui reste chargé du découpage, de l'indexation dans Chroma et de la recherche.
- pypdf 6.21.4 et beautifulsoup4 4.15.0 installés, aucun conflit (pip check), pandas toujours en 3.0.5.

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
- Suite du notebook : déplacé dans docs/todo.md le 26/11.

# 26/11/2026 - Fiches produits dans le RAG (TP 21, section 3.7)

### Fait

- Modèle de fiche : "docs/template/product_card_light.md" (le modèle full est rangé à côté, non utilisé). Les accolades portent exactement les noms des colonnes du parquet nettoyé : la requête DuckDB lit ces noms dans le modèle, la requête et le modèle ne peuvent pas se désynchroniser.
- Retirés du modèle : le code-barres et la source. Ils ne portent pas de sens et feraient du bruit dans le vecteur. Ils passent en métadonnées (avec la note et le groupe), exclues de l'embedding.
- Échantillon de 1000 produits avec nom et Nutri-Score, tiré avec une graine ("REPEATABLE (42)"). Piège : le filtre doit être dans une sous-requête, sinon DuckDB tire avant de filtrer (876 produits au lieu de 1000). La graine ne garantit le même tirage que sur le même fichier : "find_input" prend la version datée la plus récente.
- Fiches écrites dans "data/product_card/" (le dossier est vidé avant, il contient exactement ce qui est indexé), puis indexées dans une collection Chroma à part, "fiches_produits", avec des ids stables "fiche:{code}". Environ 30 s à 80 s selon la charge d'Ollama.
- Valeurs manquantes écrites "non renseigné", jamais 0 : l'agent doit distinguer "absent" de "inconnu" (fibres manquantes sur 487 fiches sur 1000).

### Résultats et choix justifiés

- Deux collections séparées : sinon les fiches prendraient la place des documents dans le top 3 (521 000 fiches contre 405 morceaux dans le vrai code), et chaque outil cherche dans un seul type de contenu.
- La note Nutri-Score est à la fois dans le texte (recherche par sens) et en métadonnée (filtre exact "uniquement des produits notés A").
- Test : "spaghettis complets bio" et "yaourt nature" sont bien trouvés (0.76 et 0.66). "une pâte à tartiner moins sucrée" ramène des produits notés E : la similarité compare des sens, pas des nombres. "search_products" devra filtrer par métadonnée ou trier en SQL.

### Phrases pour l'oral (26/11)

- Code-barres : « Le code-barres ne porte pas de sens, donc je l'exclus du vecteur. Je le garde en métadonnée pour retrouver le produit exact. »
- Identifiants : « Un id doit désigner la chose elle-même, pas sa position dans un tableau. C'est pour ça que j'utilise le code-barres et pas le numéro de ligne. »
- Mise à jour : « Chaque fiche a un id stable basé sur le code-barres. Quand un produit change, je remplace seulement sa fiche (upsert), au lieu de tout revectoriser. »
- Modèle de fiche : « Les colonnes sont lues dans le modèle, donc la requête et le modèle ne peuvent pas se désynchroniser. Une faute de frappe dans le modèle fait échouer la requête tout de suite. »
- Injection SQL : « La requête est construite avec une f-string parce qu'un paramètre ne peut pas remplacer un nom de colonne. C'est sans risque ici, car les noms viennent de notre modèle et jamais de l'utilisateur. Les valeurs tapées par l'utilisateur passeront en paramètres. »
- Graine : « La graine donne le même échantillon sur le même fichier. Si le parquet change, l'échantillon change aussi, donc je note le fichier lu à côté des résultats. »
- Deux collections : « Je sépare les collections pour que les fiches ne prennent pas la place des documents dans les résultats, et pour que chaque outil cherche dans un seul type de contenu. »
- Nutri-Score : « La note est dans le texte pour la recherche par sens, et en métadonnée pour pouvoir filtrer exactement. »
- Valeurs manquantes : « Une valeur manquante est écrite "non renseigné" et jamais remplacée par 0, pour que l'agent distingue "absent" de "inconnu". »
- Limite de la similarité : « La similarité compare des sens, pas des nombres. "Moins sucré" ne se trouve pas par similarité, il faut un filtre ou un tri. »
- Recherche et réponse : « Je mesure séparément la recherche et la réponse. La 3.8 vérifie que la bonne source est retrouvée, les scénarios vérifient que l'agent l'utilise sans inventer. »
- Portée de la mesure : « 100 % sur 4 questions ne prouve pas grand-chose. C'est un garde-fou qui signale une baisse si je change le modèle d'embeddings, le découpage ou les fiches. »
- Questions de la mesure : « J'écris chaque question et sa réponse attendue avant de lancer le test. Si je les choisissais après avoir vu les résultats, je ne garderais que celles qui marchent, et la mesure ne mesurerait plus rien. »
- Réponses attendues : « Je n'accepte que les sources qui répondent vraiment à la question posée. Accepter trop de sources gonfle le score. »

### Mesure de la recherche (3.8) et suite

- 3.8 faite : 3 questions par collection, écrites avec leur réponse attendue avant le test. Corpus 1.0, fiches 1.0 (sur "products_clean_20261116.parquet", graine 42). Question sur l'alcool corrigée ("le week-end" retiré, il rendait la limite par jour aussi valable).
- Pas de chaîne de génération séparée : la réponse du modèle sera testée directement avec l'agent (scénarios de la section 7, dans docs/todo.md).
- Chroma et la mémoire : « Chroma tourne sur le processeur et la RAM, pas sur la carte graphique. La VRAM est occupée par les modèles d'Ollama. La mémoire de Chroma dépend du nombre total de vecteurs (environ 4 Ko par vecteur de 1024 nombres), pas du nombre de collections. »
- Deux collections et performances : « Séparer les collections ne coûte presque rien en mémoire. Le vrai gain est la qualité des résultats, la vitesse gagnée est faible. »
- Fiches et drapeaux : « Les fiches viennent du parquet nettoyé, où une valeur manquante reste vide. Elle devient "non renseigné", ce qui revient au drapeau "_missing". Le remplacement par la médiane n'a lieu que dans le pipeline du modèle (SimpleImputer), jamais dans les fichiers : une valeur estimée est acceptable pour entraîner un modèle, pas pour informer un utilisateur. »

### Drapeaux "_missing" redondants (nettoyage C3.2)
- Phrase pour l'oral : « Je ne garde un drapeau que s'il apporte une information qu'un NULL ne donne pas, par exemple une valeur recalculée. Sinon, il fait doublon avec la case vide. »

### Fonctions de recherche (3.9, 26/11)

- "search_docs" et "search_products" rendent le format du TP 19 (id, score en similarité cosinus, texte, métadonnées). "search_products" accepte une note : filtre exact "MetadataFilters" sur "nutriscore_grade".
- Piège constaté : avec un filtre, le retriever rend toujours k résultats, même hors sujet. "un yaourt nature" noté A rend des eaux minérales (score environ 0,5, contre 0,62 à 0,66 pour les vrais yaourts), parce que l'échantillon n'a aucun yaourt noté A.
- Phrase pour l'oral : « Un retriever rend toujours les k plus proches, pas les k bons. Avec un filtre, il peut ne rester que des résultats hors sujet, donc l'agent doit vérifier la pertinence avant de répondre. »
- Noms : "search_docs" et "search_products" renommées "rag_search_docs" et "rag_search_products", pour ne pas confondre avec "search_product" du TP 18, qui interroge la base à partir d'un code-barres ou d'un nom. Le préfixe dit que la recherche se fait par similarité dans Chroma.
- Phrase pour l'oral (appel d'outil) : « L'utilisateur parle librement. C'est le modèle qui transforme sa phrase en appel d'outil avec les bons paramètres, à partir du nom, des paramètres et de la description de l'outil. Avec @tool, la docstring est envoyée au modèle : elle n'a plus seulement un rôle de documentation. »
- Phrase pour l'oral (filtre et résultats hors sujet) : « Le filtre réduit d'abord les candidats aux fiches de la note demandée, puis la recherche prend les plus proches parmi elles. S'il n'existe aucun produit pertinent avec cette note, le retriever rend quand même des fiches, souvent rapprochées par un mot commun ("nature" et "naturelle", "pâte" et "pâtes"), avec un score bas. » Vérifié : 138 fiches notées A sur 1000, aucun yaourt ni aucune pâte à tartiner parmi elles.

### Outil "search_product" (4.1, 26/11)

- Vraie fonction plutôt qu'un placeholder : requête DuckDB sur le parquet nettoyé, au contrat "chercher_produit" du TP 18 (arguments "nom", "code", "limite", résultat "statut", "total", "produits"). Seul le nom de la fonction reste en anglais.
- Testée : Nutella par code (ok), "comte AOP 6 mois" sans accent (ambigu, 19 produits), produit inexistant (introuvable), arguments invalides (erreur rendue, pas d'exception), tentative d'injection SQL (rien trouvé, la valeur passe en paramètre).
- Phrase pour l'oral : « Les arguments écrits par le modèle sont des données non fiables. Je les vérifie avant toute requête, je renvoie une erreur lisible au lieu de lever une exception, et le nom et le code passent en paramètres pour empêcher l'injection SQL. »
- Phrase pour l'oral : « "search_product" cherche par correspondance exacte (code ou nom), "rag_search_products" par similarité de sens. Le premier sert quand l'utilisateur connaît le produit, le second quand il le décrit. »
- Phrase pour l'oral (f-string ou paramètre) : « "nom" et "limite" viennent tous les deux du modèle, donc aucun n'est fiable. "limite" peut aller dans la requête après vérification, parce que sa forme se contrôle complètement (un entier de 1 à 5). "nom" est un texte libre impossible à contrôler, il passe toujours en paramètre. Ce n'est pas l'origine qui décide, c'est la forme. »
