# Pipeline NutriScope (TP 13)

> Données : © Open Food Facts contributors — ODbL.
> Architecture des données (magasins, règles, phase 6-7) : docs/architecture.md
> Durées mesurées le 09/11/2026, lus dans data/durations.jsonl

## 1. Schéma du flux

```
data/food.parquet  --load-->  data/raw/france_extract_<AAAAMMJJ>.parquet + .manifest.json
    lu par : clean

data/raw/france_extract_<AAAAMMJJ>.parquet  --clean-->  data/clean/products_clean_<AAAAMMJJ>.parquet + rapport de nettoyage
    lu par : load_db, parquet, benchmark (SOURCE DE VÉRITÉ UNIQUE)

data/clean/products_clean_<AAAAMMJJ>.parquet  --load_db-->  base PostgreSQL + contrôles
    lu par : contrôles (load_db, parquet) ; plus tard, l'application

data/clean/products_clean_<AAAAMMJJ>.parquet  --parquet-->  data/parquet/products_<AAAAMMJJ>/ + schéma + contrôles comparés à la base
    lu par : export, benchmark ; plus tard, l'EDA (TP 10)

data/parquet/products_<AAAAMMJJ>/  --export-->  data/exports/features_nutriscore_<AAAAMMJJ>.parquet + .schema.json (colonne split)
    lu par : entraînement et évaluation (TP 14 à 16)
```

La base sert l'application : accès par code, filtres indexés. Le Parquet sert l'analyse et le ML : balayages et agrégats. Les deux partent du même nettoyé : l'étape parquet échoue si leurs contrôles diffèrent.

Toutes les sorties sont datées. Chaque étape lit son entrée du jour, sinon la plus récente, sinon elle échoue en disant quelle étape lancer. Seules les 3 dernières versions de chaque sortie sont gardées, sauf les exports, jamais supprimés.

## 2. Commandes

Depuis n'importe quel dossier, après pip install -e :

| Besoin | Commande |
|---|---|
| Tout le pipeline (extrait France) | `python -m nutriscope.pipeline all` |
| Une étape seule | `python -m nutriscope.pipeline load` (ou `clean`, `load_db`, `parquet`, `export`) |
| Sur l'échantillon (sorties dans `data/sample/`) | `python -m nutriscope.pipeline all --sample` |
| Sur le fichier complet (sorties dans `data/full/`) | `python -m nutriscope.pipeline all --full` |
| Rejouer une date | `python -m nutriscope.pipeline all --date 20261109` |
| Réécrire l'export de la date (figé par défaut) | `python -m nutriscope.pipeline export --force` |
| Mettre à jour les rapports versionnés de `docs/data/` | `python -m nutriscope.pipeline all --docs` |
| Lancer les tests (conteneur PostgreSQL démarré) | `python -m pytest -q -rs` |
| Lancer les tests sans base | `TEST_DATABASE_URL= python -m pytest -q -rs` |

Quand tout est cassé :

```bash
python -m nutriscope.pipeline reset      # supprime les sorties datées (brut, nettoyé, Parquet, rapports), jamais les exports
python -m nutriscope.pipeline all
```

Une étape en échec s'arrête avec un message (sans trace Python) et un code de retour 1. Elle est inscrite au journal avec `"status": "failed"` et le message d'erreur.

## 3. Durées réelles

Machine : (Windows 11, Intel 16 cœurs logiques, 32 Go de RAM. Python 3.12.10, pandas 3.0.5, pyarrow 25.0.1, DuckDB 1.5.6, NumPy 2.5.2, PostgreSQL 17.11 en conteneur Docker.

| Étape | Échantillon : lignes | Échantillon : durée (s) | Extrait France : lignes | Extrait France : durée (s) |
|---|---|---|---|---|
| load | 5 656 | 0,06 | 1 247 336 | 19,7 |
| clean | 2 072 | 0,21 | 521 240 | 17,4 |
| load_db | 2 072 | 0,79 | 521 240 | 69,3 |
| parquet | 2 072 | 0,25 | 521 240 | 10,5 |
| export | 1 482 | 0,11 | 456 380 | 1,5 |
| Total | | 1,4 | | 118,4 |

Périmètre france

Détail des deux étapes les plus longues (extrait France, même lancement) :

| Sous-étape | Durée (s) |
|---|---|
| clean : lecture du brut | 0,5 |
| clean : règles de nettoyage | 7,8 |
| clean : écriture du nettoyé | 1,4 |
| clean : rapport de nettoyage | 7,6 |
| load_db : schéma recréé | 0,2 |
| load_db : chargement des tables | 61,8 |

## Lecture

1. Le chargement de la base domine : 69s sur 118, dont 62s pour remplir les tables. C'est le prix du schéma normalisé, le serveur tournant dans un conteneur Docker ce qui peux pénaliser ces temps. 
Les supports analytiques, eux, sont rapides : 10 s pour le Parquet, 1,5 s pour l'export.
2. Le nettoyage (17 s) se partage presque à égalité entre les règles et le rapport, qui recompte les anomalies avant et après, load (20 s) comprend l'extraction et le calcul de l'empreinte SHA-256 de la source de 7,7 Go.
3. Le pipeline complet tient en deux minutes sur l'extrait france : un orchestrateur (Airflow) ne se justifie pas. La CLI suffit, et le journal des durées dira si cela change, par exemple avec le fichier complet (--full).

## Ce que la phase 4 lira

- Fichier : `data/exports/features_nutriscore_<AAAAMMJJ>.parquet` (exemple: celui du 09/11 : 456 380 produits, SHA-256 `82e5ad23a8e35ff470a3288982dc76f49527098d0a9ba004b6392a16a60bca5e`).
- Schéma : `features_nutriscore_<AAAAMMJJ>.schema.json`, à côté. Il contient les filtres, les colonnes (type, unité, rôle, % de manquants, politique de manquants), le split, le SHA-256, le commit Git et la licence.
- Cible : `nutriscore_grade` (a à e). Identifiant : `code`.
- Split : colonne `split` (train ou test), stratifiée sur le grade, 20 % de test pour chaque grade, graine 42.

| Grade | Train | Test |
|---|---|---|
| a | 48 035 | 12 009 |
| b | 37 835 | 9 459 |
| c | 76 320 | 19 080 |
| d | 97 688 | 24 422 |
| e | 105 226 | 26 306 |

Interdits :
- recalculer le split : utiliser la colonne split telle quelle ;
- utiliser `nutriscore_score` comme feature : le grade en est déduit ;
- utiliser `code`, `product_name` ou `brands` comme features.

