# Benchmark du stockage analytique (TP 12, étape 3)

> Données : © Open Food Facts contributors — ODbL.
> Mesures détaillées (générées, à ne pas modifier à la main) : [`benchmark_mesures.md`](benchmark_mesures.md).
> Les chiffres cités ici sont ceux de l'exécution du 22/10/2026 ; relancer `python -m src.storage.benchmark` régénère les mesures, pas ce document.

## 1. Question posée

Pour les requêtes que l'analyse exploratoire et l'entraînement feront vraiment, quel couple support + moteur répond le plus vite et avec le moins de mémoire, et que coûte la construction de chaque support ?

## 2. Données et supports comparés

Extrait France nettoyé : 521 240 produits, présents sous trois formes (supports) :

| Support | Contenu | Construit par | Lu par |
|---|---|---|---|
| Parquet nettoyé, non partitionné | `data/clean/products_clean.parquet`, un seul fichier | le pipeline (`src/clean_pipeline.py`) | pandas, DuckDB |
| Base PostgreSQL | tables `products`, `nutrients`, `brands`… | le pipeline (`src/load_db.py`) | PostgreSQL |
| Parquet partitionné par rayon | `data/parquet/produits/aisle=<slug>/`, un dossier par rayon | `src/storage/convert_parquet.py` | DuckDB |

### Pourquoi le CSV n'a pas été mesuré

Notre projet n'utilise pas le CSV, le format Parquet a été retenu dès le TP 1 et toute la chaîne (extraction, nettoyage, base, conversion) part du Parquet Open Food Facts. Produire un CSV uniquement pour le benchmark aurait mesuré un format que le projet n'utilise nulle part, pandas lit donc ici le Parquet nettoyé en se limitant aux colonnes utiles à chaque requête.

Conséquence : l'écart entre pandas et DuckDB mesure l'effet du moteur, pas celui du format (CSV contre Parquet). Le bonus de l'énoncé « DuckDB sur CSV » est remplacé par DuckDB sur le Parquet non partitionné, qui isole l'effet du partitionnement (bonus « mesure avec et sans partition »).

## 3. Requêtes

Choisies d'après l'énoncé du TP 10, l'EDA n'étant pas encore réalisée (à revoir ensuite, voir `docs/journal.md`) :

| Requête | Ce qu'elle calcule | Type |
|---|---|---|
| Profil médian par rayon | médianes des sucres, du sel et des kcal par rayon, rayon unknown exclu | agrégat sur tous les produits |
| 20 boissons les plus sucrées | les 20 produits du rayon boissons aux sucres les plus élevés | filtre sur un rayon, puis tri |
| Complétude par marque | % de Nutri-Score et des sept nutriments clés, marques d'au moins 20 produits, top 20 | agrégat à forte cardinalité |

## 4. Méthode : ce que « honnête » veut dire ici

- Une mesure = un sous-processus Python neuf, le temps = lecture + calcul (imports exclus) ; trois répétitions, médiane des temps, maximum des pics mémoire.
- Une mesure « imports seulement » par moteur donne le poids des bibliothèques.
- Mêmes résultats vérifiés avant le chronomètre : les quatre moteurs rendent le même nombre de lignes et la même première ligne.
- Pas d'avantage caché : pandas lit seulement les colonnes utiles, comme DuckDB ; PostgreSQL garde ses index existants, aucun n'a été ajouté pour l'occasion.
- Mémoire mesurée par `psutil` sous Windows (`resource.getrusage` n'existe pas sous Windows), par `VmHWM` sous Linux.

Le détail complet figure dans [`benchmark_mesures.md`](benchmark_mesures.md).

## 5. Résultats

Machine : Windows 11, Intel 16 cœurs logiques, 34 Go de RAM ; Python 3.12.10, pandas 3.0.5, pyarrow 25.0.1, DuckDB 1.5.6, PostgreSQL 17.11.

### Temps médian (ms)

| Moteur et support | Profil par rayon | 20 boissons sucrées | Complétude par marque |
|---|---|---|---|
| pandas sur Parquet nettoyé | 156 | 116 | 161 |
| PostgreSQL | 387 | 74 | 469 |
| DuckDB sur Parquet partitionné | **41** | **32** | **56** |
| DuckDB sur Parquet nettoyé | 65 | 82 | 104 |

### Pic mémoire (Mo)

| Moteur et support | Profil par rayon | 20 boissons sucrées | Complétude par marque |
|---|---|---|---|
| pandas sur Parquet nettoyé | 228 | 215 | 235 |
| PostgreSQL (client seulement) | **37** | **37** | **37** |
| DuckDB sur Parquet partitionné | 69 | 45 | 82 |
| DuckDB sur Parquet nettoyé | 64 | 49 | 70 |

### Coût de construction des supports (s)

| Support | Durée |
|---|---|
| Parquet nettoyé (lecture + nettoyage + écriture) | 9,9 |
| Base PostgreSQL (schéma + chargement) | 66,2 |
| Parquet partitionné (conversion) | **2,6** |

## 6. Lecture

1. DuckDB sur le Parquet partitionné est le plus rapide sur les trois requêtes (de 32 à 56 ms, avec moins de 85 Mo). Le partitionnement compte surtout quand la requête filtre sur le rayon par exemple il est 2,6 fois plus rapide sur les boissons parce qu'il ne lit que la partition concernée, le gain est plus faible sur les agrégats dqui lisent toutes les partitions.
2. PostgreSQL est compétitif sur le filtre (74 ms, aidé par l'index sur le rayon) mais 8 à 9 fois plus lent sur les agrégats, à cause des médianes (tri) et des jointures du schéma.
3. L'écart entre pandas et DuckDB est de 3 à 4, et pandas tient sous 250 Mo, loin des « trois ordres de grandeur » et des « plusieurs Go » du point de contrôle 3 car pandas lit ici un Parquet et non un CSV complet. L'écart observé est celui du moteur, celui du format a été réglé dès le TP 1 en choisissant le Parquet.

## 7. Limites

- Temps très courts : Les ordres de grandeur sont fiables, les ratios précis beaucoup moins car en ms.
- Caches chauds : les caches du système et de PostgreSQL ne sont pas vidés entre les mesures ; tous les moteurs en profitent de la même façon.
- Serveur PostgreSQL : Celui ci tourne via un container Docker, de ce fait le requetage et la construction de support s'en retrouve pénalisé, par contre au niveau de la mémoire il s'en trouve amélioré car python ne calcule que ceux la depuis l'intérieur de container.
- Requêtes provisoires : choisies d'après l'énoncé du TP 10, à confirmer une fois l'EDA réalisée.

## 8. Conséquences pour l'architecture

- L'analyse et l'entraînement lisent le Parquet partitionné avec DuckDB, c'est le support le plus rapide et le moins coûteux à reconstruire (2,6 s).
- L'application lit la base PostgreSQL : accès par clé et filtres indexés, mais c'est celui qui est le plus long à construire (66 s).
- pandas reste utile pour les traitements qui en ont besoin (nettoyage, préparation des features).