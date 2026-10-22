# Benchmark : mesures

- Date : 2026-10-22
- Données : 521 240 produits (`data/clean/products_clean.parquet`) ; Open Food Facts contributors - ODbL (https://opendatacommons.org/licenses/odbl/1-0/)
- Répétitions par mesure : 3
- Généré par `python -m src.storage.benchmark` : ne pas modifier à la main. La lecture des résultats est rédigée dans `docs/data/benchmark.md`.

## Ce que mesure ce rapport

Les mêmes produits existent sous trois formes (les **supports**) : un Parquet nettoyé d'un seul tenant, la base PostgreSQL, un Parquet partitionné par rayon. Pour trois requêtes que l'analyse fera vraiment, le rapport mesure ce que coûte chaque **moteur** (un outil qui lit un support) : le temps pour lire les données et calculer le résultat, et la mémoire du processus. Il donne aussi ce qu'a coûté la construction de chaque support.

Comment lire les tableaux :

- **Temps médian** : lecture + calcul, en millisecondes, médiane des répétitions.
- **× le plus rapide** : temps du moteur divisé par celui du plus rapide sur la même requête (1,0 = le plus rapide ; 3,0 = trois fois plus lent).
- **Pic mémoire** : mémoire maximale du processus, bibliothèques comprises.
- **Dont requête** : pic mémoire moins celui du même moteur quand il ne fait que charger ses bibliothèques.

## Les requêtes

| Requête | Ce qu'elle calcule | Type | Origine |
| --- | --- | --- | --- |
| Profil médian par rayon | par rayon : nombre de produits et médianes des sucres, du sel et des kcal ; rayon unknown exclu | agrégat sur tous les produits | TP 10, étape 1 (profil par rayon) |
| 20 boissons les plus sucrées | les 20 produits du rayon boissons les plus sucrés, du plus sucré au moins sucré | filtre sur un rayon, puis tri | TP 10, étape 4 (valeurs extrêmes) |
| Complétude par marque (≥ 20 produits, top 20) | par marque d'au moins 20 produits : % de Nutri-Score renseigné et % des sept nutriments présents ; les 20 plus grosses marques | agrégat à forte cardinalité (une ligne par marque) | TP 10, étape 2 (complétude par marque) |

## Résultats

### 1. Profil médian par rayon

| Moteur | Support | Temps médian (ms) | × le plus rapide | Pic mémoire (Mo) | Dont requête (Mo) | Lignes |
| --- | --- | --- | --- | --- | --- | --- |
| pandas | Parquet nettoyé, non partitionné | 156 | 3,8 | 228 | 146 | 11 |
| PostgreSQL | Base PostgreSQL | 387 | 9,4 | 37 | 3 | 11 |
| DuckDB | Parquet partitionné par rayon | 41 | 1,0 | 69 | 34 | 11 |
| DuckDB | Parquet nettoyé, non partitionné | 65 | 1,6 | 64 | 29 | 11 |

### 2. 20 boissons les plus sucrées

| Moteur | Support | Temps médian (ms) | × le plus rapide | Pic mémoire (Mo) | Dont requête (Mo) | Lignes |
| --- | --- | --- | --- | --- | --- | --- |
| pandas | Parquet nettoyé, non partitionné | 116 | 3,6 | 215 | 133 | 20 |
| PostgreSQL | Base PostgreSQL | 74 | 2,3 | 37 | 3 | 20 |
| DuckDB | Parquet partitionné par rayon | 32 | 1,0 | 45 | 10 | 20 |
| DuckDB | Parquet nettoyé, non partitionné | 82 | 2,6 | 49 | 14 | 20 |

### 3. Complétude par marque (≥ 20 produits, top 20)

| Moteur | Support | Temps médian (ms) | × le plus rapide | Pic mémoire (Mo) | Dont requête (Mo) | Lignes |
| --- | --- | --- | --- | --- | --- | --- |
| pandas | Parquet nettoyé, non partitionné | 161 | 2,9 | 235 | 153 | 20 |
| PostgreSQL | Base PostgreSQL | 469 | 8,3 | 37 | 3 | 20 |
| DuckDB | Parquet partitionné par rayon | 56 | 1,0 | 82 | 47 | 20 |
| DuckDB | Parquet nettoyé, non partitionné | 104 | 1,8 | 70 | 35 | 20 |

## Coût de construction des supports

Payé une fois, à chaque exécution du pipeline. Dernière durée de chaque étape dans `data/durees.jsonl`.

| Support | Lu par | Étapes | Durée (s) | Construit à partir de |
| --- | --- | --- | --- | --- |
| Parquet nettoyé, non partitionné | pandas et DuckDB | lecture + nettoyage + écriture | 9,9 | `data/raw/extrait_france.parquet` |
| Base PostgreSQL | PostgreSQL | schéma + chargement | 66,2 | `data/raw/extrait_france.parquet` |
| Parquet partitionné par rayon | DuckDB | conversion | 2,6 | `data/clean/products_clean.parquet` |

## Référence : imports seulement

Ce que coûte le seul chargement des bibliothèques de chaque moteur, sans lire de données.

| Moteur | Support | Imports (ms) | Pic mémoire (Mo) |
| --- | --- | --- | --- |
| pandas | Parquet nettoyé, non partitionné | 602 | 82 |
| PostgreSQL | Base PostgreSQL | 194 | 34 |
| DuckDB | Parquet partitionné par rayon | 40 | 35 |
| DuckDB | Parquet nettoyé, non partitionné | 39 | 35 |

## Vérification avant chronomètre

Chaque moteur doit rendre le même nombre de lignes et la même première ligne que DuckDB sur Parquet partitionné par rayon, sinon le benchmark s'arrête.

| Requête | Lignes | Même première ligne |
| --- | --- | --- |
| Profil médian par rayon | 11 pour chacun des 4 moteurs | ✓ |
| 20 boissons les plus sucrées | 20 pour chacun des 4 moteurs | ✓ |
| Complétude par marque (≥ 20 produits, top 20) | 20 pour chacun des 4 moteurs | ✓ |

## Méthode : ce que « honnête » veut dire ici

- Chaque mesure tourne dans un **sous-processus Python neuf** : aucun cache Python partagé entre moteurs.
- **Temps = lecture + calcul** (connexion comprise pour PostgreSQL), imports exclus ; **médiane** des répétitions.
- **Mémoire = pic du processus** (imports compris), **maximum** des répétitions : `psutil` (`peak_wset`) sous Windows, `VmHWM` de `/proc/self/status` sous Linux (`ru_maxrss` y garderait le pic du processus parent), `resource` sous macOS.
- **Mêmes résultats vérifiés avant le chronomètre** (section précédente).
- **pandas lit seulement les colonnes utiles** à chaque requête, comme DuckDB.
- **PostgreSQL garde ses index existants** (rayon, marque, grade), aucun n'est ajouté pour l'occasion.
- Limite : pour PostgreSQL, le pic mémoire est celui du **client** Python ; le serveur calcule dans ses propres processus, non mesurés ici.
- Limite : les caches du système de fichiers et de PostgreSQL restent chauds d'une mesure à l'autre (une passe de vérification précède les mesures) ; tous les moteurs en profitent de la même façon.

## Machine et versions

|  | Valeur |
| --- | --- |
| Système | Windows-11-10.0.22631-SP0 |
| Processeur | Intel64 Family 6 Model 167 Stepping 1, GenuineIntel |
| Cœurs logiques | 16 |
| Mémoire | 34.1 Go |
| Python | 3.12.10 |
| pandas | 3.0.5 |
| pyarrow | 25.0.1 |
| duckdb | 1.5.6 |
| psycopg | 3.3.6 |
| psutil | 7.2.2 |
| Serveur PostgreSQL | 17.11 (Debian 17.11-1.pgdg13+2) |
