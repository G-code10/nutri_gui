# Architecture des données NutriScope

> Données : © Open Food Facts contributors — ODbL.
> En une phrase : la base PostgreSQL sert l'application, les fichiers Parquet servent l'analyse et le machine learning ; les deux sont reconstruits à partir du même fichier nettoyé.

Les mentions « À faire » signalent ce qui n'existe pas encore dans le dépôt ou ce qui reste à décider.

## 1. Schéma du flux

```
data/food.parquet  --load-->  data/raw/france_extract_<AAAAMMJJ>.parquet + manifeste
    source Open Food Facts, imbriquée, téléchargée à la main

data/raw/france_extract_<AAAAMMJJ>.parquet  --clean-->  data/clean/products_clean_<AAAAMMJJ>.parquet
    nettoyé : SOURCE DE VÉRITÉ UNIQUE (règles du TP 9, src/cleaning.py)

data/clean/products_clean_<AAAAMMJJ>.parquet  --load_db-->  base PostgreSQL
    lue par : contrôles ; plus tard, l'API de l'application

data/clean/products_clean_<AAAAMMJJ>.parquet  --parquet-->  data/parquet/products_<AAAAMMJJ>/aisle=<rayon>/
    lu par : export, contrôles (comparés à la base), benchmark ; plus tard, l'EDA (TP 10)

data/parquet/products_<AAAAMMJJ>/  --export-->  data/exports/features_nutriscore_<AAAAMMJJ>.parquet (colonne split)
    lu par : entraînement (TP 14 à 16)
```

Chaque étape écrit sa durée dans `data/durees.jsonl` (journal des durées, relu par le benchmark).

## 2. Magasins de données

| Magasin | Contenu | Producteur | Format | Emplacement | Dans Git |
|---|---|---|---|---|---|
| Source | export Open Food Facts complet, champs imbriqués | téléchargement (À faire : documenter, `download_parquet.py` étant retiré) | Parquet | `data/food.parquet` | non |
| Brut | table `products_nutrition` aplatie, non nettoyée : fichier complet (4,6 M de lignes), extrait France (1,2 M), échantillon de test | `src/extract.py`, `scripts/make_sample_raw.py` | Parquet ZSTD | `data/raw/` | non |
| Nettoyé | sortie de `cleaning.clean()` : extrait France ou fichier complet selon le lancement | `src/clean_pipeline.py` | Parquet ZSTD, un fichier | `data/clean/products_clean.parquet` | non |
| Base | le même nettoyé, en schéma normalisé (`products`, `nutrients`, `brands`, `categories`, `product_categories`, `aisles`) | `src/clean_pipeline.py` (`create_db`, `load_db`) | PostgreSQL | serveur configuré par `db.env` | non (schéma : `sql/create_db.sql`, dans Git) |
| Parquet analytique | le même nettoyé, typé, partitionné par rayon, avec `schema_produits.json` et `_SUCCESS` | `src/storage/convert_parquet.py` | Parquet ZSTD, un dossier par rayon | `data/parquet/produits/` | non |
| Export features | produits utilisables pour prédire le Nutri-Score (grade a-e, sept nutriments clés, cohérences), figé et daté, avec `features_nutriscore_<AAAAMMJJ>.schema.json` | `src/storage/export_features.py` | Parquet ZSTD, un fichier | `data/exports/` | non (seule la commande est dans Git) |
| Journal des durées | une ligne par étape réussie : horodatage, étape, durée, lignes, source | `src/clean_pipeline.py`, `convert_parquet.py` | JSON Lines | `data/durees.jsonl` | non |
| Rapports générés | rapport de nettoyage, contrôles, mesures du benchmark | `report.py`, `run_queries.py`, `benchmark.py` | Markdown | `docs/data/` | oui |

## 3. Qui lit quoi

| Lecteur | Ce qu'il lit | Pourquoi | Ce qu'il ne lit pas |
|---|---|---|---|
| API de l'application (À faire) | la base PostgreSQL : un produit par son code, les produits d'un rayon ou d'une marque | accès par clé et filtres indexés (code, rayon, marque, grade), lectures concurrentes | les Parquet : pas d'accès par clé, pas d'index |
| Notebooks d'EDA (À faire, TP 10) | le Parquet partitionné, avec DuckDB (ou pandas sur des colonnes choisies) | balayages et agrégats sur tous les produits : le plus rapide d'après le benchmark | la base : les agrégats y sont 8 à 9 fois plus lents ; le brut : non nettoyé |
| Entraînement (À faire, TP 14) | l'export features daté `data/exports/features_nutriscore_<AAAAMMJJ>.parquet` | jeu figé : deux entraînements sur le même export sont comparables | le Parquet partitionné (il change à chaque exécution du pipeline), la base |
| Contrôles (`run_queries.py`) | le Parquet partitionné, puis la base | vérifier que les deux supports donnent les mêmes résultats (`docs/data/controle.md`) | le brut |
| Benchmark (`benchmark.py`) | les trois supports et le journal des durées | mesurer chaque moteur sur les mêmes données (`docs/data/benchmark_mesures.md`) | le brut |
| Assistant (À faire) | À faire : à définir quand l'assistant sera spécifié | À faire | À faire |

Où l'API lira un produit : dans la base PostgreSQL, table `products` (clé `code`), jointe à `nutrients`.
Où le TP 14 lira ses features : dans `data/exports/features_nutriscore_<AAAAMMJJ>.parquet` et son schéma `features_nutriscore_<AAAAMMJJ>.schema.json` (colonnes, cible, filtres, politique de manquants, SHA-256).

## 4. Cinq règles

1. Source de vérité unique. La base et le Parquet partent du même nettoyé, produit par une seule exécution du pipeline. Si leurs comptages diffèrent, c'est la chaîne qui est fausse : on corrige la chaîne, pas le rapport. `run_queries.py` le vérifie sur les cinq contrôles.
2. Données hors Git. Le dépôt contient le code qui produit les données, jamais les données : tout `data/` est ignoré par Git. Seuls le schéma SQL (`sql/create_db.sql`) et les rapports générés (`docs/data/`) sont versionnés ; les schémas JSON (`schema_produits.json`, schéma de l'export) restent à côté de leurs données, hors Git.
3. Parquet reconstruit à chaque exécution. `convert_parquet` supprime le dossier avant d'écrire (aucune partition orpheline), trie les lignes (mêmes données, mêmes fichiers) et écrit `_SUCCESS` en dernier : un dossier sans ce marqueur est incomplet et n'est pas lu.
4. Export non réécrit. Un export features daté n'est jamais écrasé sans `--force` : un jeu d'entraînement qui change en silence rendrait les modèles incomparables. Réécrit avec `--force` à partir des mêmes données, il est identique (même SHA-256, inscrit dans son schéma).
5. Partition par rayon seulement. Les analyses filtrent et agrègent surtout par rayon ; une douzaine de partitions reste lisible et efficace (le benchmark mesure un gain de 2,6 fois sur un filtre par rayon). Partitionner aussi par marque ou par grade créerait des milliers de petits fichiers, plus lents à lire. À faire : reprendre ici le paragraphe de l'exercice 3.5.2.

## 5. Reconstruire tout le stockage

```bash
python -m src.extract --country en:france                                    # brut : extrait France
python -m src.clean_pipeline --source data/raw/extrait_france.parquet --report /tmp/rapport.md   # nettoyé + base
python -m src.storage.convert_parquet                                        # Parquet partitionné
python -m src.storage.run_queries                                            # contrôles Parquet / base
python -m src.storage.export_features                                        # export features daté (--force pour réécrire)
```

À faire : une commande unique qui enchaîne ces étapes (TP 13).

## 6. Ce qui change en phase 6-7

- Stockage objet : le Parquet partitionné et les exports quittent le disque local pour un stockage objet (de type S3). Le partitionnement par rayon et le marqueur `_SUCCESS` restent valables tels quels ; DuckDB sait lire directement depuis ce type de stockage. À faire : choix du fournisseur et de l'organisation des dossiers.
- Base managée : PostgreSQL passe sur un service managé (sauvegardes, haute disponibilité, mises à jour gérées par le fournisseur). La connexion reste décrite par `db.env`, sans changement de code. À faire : choix du fournisseur.
- Orchestration : la commande unique du TP 13 suffit tant que le pipeline dure quelques minutes ; un orchestrateur ne se justifiera que si les durées du journal l'exigent. À faire : décision à prendre au vu du journal des durées.
- À faire : compléter cette section quand les phases 6 et 7 seront cadrées.
