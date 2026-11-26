# À faire

Tâches en cours, reprises des parties "À reprendre" du journal le 26/11/2026 et vérifiées une par une. Le journal garde les décisions et leurs raisons, ce fichier garde ce qui reste à faire. La date entre parenthèses renvoie à l'entrée du journal d'origine.

## Notebook TP 21 (assistant)

- [x] 3.9 : fonctions "rag_search_docs" et "rag_search_products" (avec le filtre sur la note), au format id, score, texte, métadonnées. (26/11)
- [ ] Sections 4 à 8 : outils, agent avec mémoire courte, journalisation JSONL et MLflow, scénarios, bilan. (26/11)
- [ ] Corriger l'introduction du notebook : le tableau des outils dit encore "placeholder" pour tous les outils. (26/11)
- [ ] Section 5 : consigne du prompt système. Si une valeur est "non renseigné", le dire au lieu de l'inventer, et ne jamais donner un chiffre absent de la source. (26/11)
- [ ] Section 5 : l'agent doit vérifier que les fiches rendues par "rag_search_products" correspondent à la demande (avec un filtre, des résultats hors sujet restent possibles, score environ 0,5). Envisager un seuil de score, à fixer sur des exemples. (26/11)
- [ ] Section 7 : rejouer les 3 questions du corpus de la 3.8 avec l'agent (outil choisi, source, fidélité : 50 g de poisson, 10 verres par semaine, pas de chiffre inventé pour les produits sucrés). Ajouter un scénario sur les fibres d'un produit où elles manquent. (26/11)
- [ ] Section 4 : docstring de l'outil sur "rag_search_products". Dire quand l'utiliser (une description, pas un code-barres), les valeurs de "grade" (une lettre de A à E), le laisser vide si l'utilisateur dit seulement "sain", et appeler l'outil une fois par note si plusieurs notes sont demandées. (26/11)
- [ ] Section 7 : scénario « un yaourt noté A ou B », vérifier dans la trace MLflow que l'agent fait deux appels avec les bonnes lettres. (26/11)
- [ ] Noms des outils en anglais : écart au contrat du TP 18, qui impose "chercher_produit". À signaler à la revue croisée. (23/11)

## RAG dans le code principal (src/rag/)

- [ ] Mise à jour par upsert : supprimer les ids ("delete_nodes") puis ajouter ("insert_nodes"), car le connecteur LlamaIndex ne fait que "add". Tester "delete_nodes" sur des ids absents. (26/11)
- [ ] Fiches pour l'intégralité des produits, avec la durée de vectorisation mesurée. (26/11)
- [ ] Jeu d'évaluation du TP 20 : 30 questions (factuelles, comparatives, 5 pièges hors périmètre) avec réponses et sources attendues, hit rate et MRR, deux améliorations mesurées. La 3.8 n'en compte que 6. (24/11)

## Corpus et licences

- [ ] Écrire "docs/ia/corpus.md" (fichier attendu par le TP 19) : les 25 sources du corpus du collègue avec titre lisible, éditeur, URL, date et licence, et les sources écartées (PNNS 5, dossier "Non Conservés"). (24/11 et 25/11)
- [ ] Lire les conditions d'utilisation de Manger Bouger et de Santé publique France, les éditeurs du corpus actuel. (24/11)
- [ ] Demander au collègue la provenance des fichiers et sa stratégie de découpage, pour pouvoir la justifier (demandé au TP 19). (25/11)

## Sécurité et configuration

- [ ] Ajouter ".env" au ".gitignore" par précaution : "load_dotenv" le lit, et une clé d'API écrite dedans partirait sur Git. Le fichier n'existe pas encore. (26/11)
- [ ] Si MLflow passe à un stockage SQLite, ajouter "mlflow.db" au ".gitignore". (23/11)
- [ ] "load_image" (atelier scanner) : les EXIF sont bien retirés quand l'image est ré-encodée, mais une photo JPEG ou PNG sans "max_size" est renvoyée telle quelle, avec ses EXIF (dont la position GPS). À corriger avant tout envoi chez un fournisseur en ligne. (23/11, vérifié le 26/11)
- [ ] Au déploiement (J6) : serveur MLflow dans docker-compose avec ses données dans PostgreSQL, et Chroma en mode serveur si l'API et l'indexation y accèdent en même temps. (23/11 et 25/11)

## ML (bloc 3)

- [ ] Entraînement final et sauvegarde du modèle avec MLflow, et une fonction de prédiction pour un seul produit (rien dans "src/ml/" pour l'instant). (23/11)
- [ ] Mesurer la baisse du F1 macro quand les colonnes absentes d'une étiquette (nova_group, aisle, aisle2, peut-être fruits-légumes et additifs) sont mises à NaN, sur une validation tirée du train et pas sur le test. (23/11)

## Nettoyage (bloc 2)

- [ ] Drapeaux "_missing" redondants : décider s'il faut les retirer. (26/11)
    - Constat : dans le parquet nettoyé, les drapeaux "<col>_missing" des colonnes restées vides (fibres, sucres, glucides, protéines, matières grasses, fruits et légumes, nova, nom, marque, ingrédients) valent exactement "<col> IS NULL". Vérifié pour les fibres : 249 269 drapeaux pour 249 269 valeurs vides.
    - Ils ne servent nulle part en aval : la base ne les stocke pas ("sql/create_db.sql", ligne 12), l'export d'entraînement ne les contient pas, et le pipeline du modèle recrée son propre indicateur avec "SimpleImputer(add_indicator=True)" ("src/ml/modeling.py", ligne 35). Les fiches produits ne les lisent pas non plus.
    - La justification écrite dans "sql/create_db.sql" ("ils vivent dans le Parquet pour le ML") n'est donc plus vraie.
    - Règle retenue : un drapeau qui vaut exactement "<col> IS NULL", qui n'est utilisé ni en base ni dans les features, et qu'on ne sait pas justifier, ne sert à rien. Seuls les drapeaux qui gardent une information perdue autrement ont leur place : "grade_not_applicable", "saturated_fat_100g_missing" et "energy_kcal_100g_missing" (valeur remplie ou recalculée).
    - Pour les retirer : vérifier "allergens_missing" à part (NULL et chaîne vide n'ont pas le même sens), passer de "flag" à "keep" dans "DEFAULT_MISSING_STRATEGY" ("src/cleaning.py"), adapter les tests ("tests/test_cleaning.py" lignes 345 à 348, "tests/test_convert_parquet.py" lignes 36 et 114) et le commentaire de "sql/create_db.sql".
- [ ] Estimer les fruits-légumes à partir de la catégorie. (TP 14)
- [ ] Marquer comme suspect le grade d'une fiche dont l'énergie a été corrigée. (TP 14)
- [ ] Après l'EDA (TP 10, pas encore faite) : revoir les requêtes du benchmark et "docs/data/benchmark.md". (TP 12)
- [ ] Script de téléchargement de "food.parquet" dans "scripts/". Un brouillon existe : "notebooks/guillaume/download_parquet.py". (TP 13)

## Documentation

- [ ] Mettre à jour "docs/architecture.md" : il cite encore les anciennes commandes ("python -m src.extract", "src.clean_pipeline") au lieu de "python -m nutriscope.pipeline", un nettoyé non daté, et l'entraînement "À faire, TP 14". (TP 12 et TP 13)
- [ ] Rédiger une ADR sur les choix d'outils de l'assistant (LangChain, LlamaIndex, Chroma, MLflow). (23/11)
- [ ] Reporter la justification des nouvelles librairies dans le README, qui n'en cite aucune. (23/11)
