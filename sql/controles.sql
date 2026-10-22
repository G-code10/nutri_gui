-- ============================================================================
-- NutriScope : les cinq requêtes de contrôle (TP 12, étape 2)
-- ----------------------------------------------------------------------------
-- Exécutées par src/storage/run_queries.py, qui découpe ce fichier sur les
-- marqueurs « -- @nom: <nom> » : une requête par marqueur, dans cet ordre.
--
-- Écrites contre une vue `produits`, créée par run_queries.py avec les MÊMES
-- colonnes dans DuckDB (sur le Parquet partitionné) et dans PostgreSQL (sur la
-- base) : le même texte tourne sur les deux moteurs, d'où la comparaison.
-- Colonnes de la vue : code, product_name, brands, aisle (slug du rayon),
-- aisle_tag (tag d'origine), nutriscore_grade, nutriscore_score,
-- grade_not_applicable, les nutriments en g/100 g ou kcal, has_categories.
--
-- SQL commun aux deux moteurs : les pourcentages et moyennes sont rendus en
-- DOUBLE PRECISION, l'arrondi est fait à l'affichage (pas d'écart d'arrondi
-- entre moteurs). Chaque requête a un ORDER BY total : résultat reproductible.
--
-- Les $parametres sont remplacés par run_queries.py avec les constantes de
-- src/cleaning.py : les contrôles appliquent les tolérances du nettoyage.
-- $<nom> s'écrit avec un point (syntaxe SQL) ; $<nom>_label avec une virgule,
-- pour les libellés affichés dans le rapport.
--
-- Données : © Open Food Facts contributors — ODbL.
-- ============================================================================

-- @nom: comptage_par_rayon
-- Une ligne par rayon (une partition) : nombre de produits et part du total.
SELECT
    aisle AS rayon,
    count(*) AS produits,
    CAST(100.0 * count(*) / sum(count(*)) OVER () AS DOUBLE PRECISION) AS part_pct
FROM produits
GROUP BY aisle
ORDER BY produits DESC, rayon;

-- @nom: completude
-- Par rayon : Nutri-Score renseigné (a-e), sept nutriments clés tous présents, catégories présentes.
SELECT
    aisle AS rayon,
    count(*) AS produits,
    CAST(100.0 * count(*) FILTER (WHERE nutriscore_grade IN ('a', 'b', 'c', 'd', 'e')) / count(*)
         AS DOUBLE PRECISION) AS nutriscore_pct,
    CAST(100.0 * count(*) FILTER (
             WHERE energy_kcal_100g IS NOT NULL AND fat_100g IS NOT NULL AND saturated_fat_100g IS NOT NULL
               AND carbohydrates_100g IS NOT NULL AND sugars_100g IS NOT NULL AND proteins_100g IS NOT NULL
               AND salt_100g IS NOT NULL
         ) / count(*) AS DOUBLE PRECISION) AS sept_nutriments_pct,
    CAST(100.0 * count(*) FILTER (WHERE has_categories) / count(*) AS DOUBLE PRECISION) AS categories_pct
FROM produits
GROUP BY aisle
ORDER BY rayon;

-- @nom: doublons
-- Codes-barres en double (0 attendu) ; couples nom + marque répétés (une information, pas une erreur).
SELECT 'codes en double' AS controle, count(*) AS groupes, CAST(coalesce(sum(n - 1), 0) AS BIGINT) AS lignes_en_trop
FROM (SELECT code, count(*) AS n FROM produits GROUP BY code HAVING count(*) > 1) AS codes
UNION ALL
SELECT 'couples nom + marque répétés', count(*), CAST(coalesce(sum(n - 1), 0) AS BIGINT)
FROM (
    SELECT product_name, brands, count(*) AS n
    FROM produits
    WHERE product_name IS NOT NULL AND brands IS NOT NULL
    GROUP BY product_name, brands
    HAVING count(*) > 1
) AS couples
ORDER BY controle;

-- @nom: bornes_coherences
-- Bornes (0 attendu) puis cohérences restantes (listées, pas cachées), avec les tolérances du nettoyage.
SELECT 1 AS ordre, 'borne' AS nature, 'nutriment hors [0, 100] g' AS anomalie, count(*) AS produits
FROM produits
WHERE fat_100g NOT BETWEEN 0 AND 100 OR saturated_fat_100g NOT BETWEEN 0 AND 100
   OR carbohydrates_100g NOT BETWEEN 0 AND 100 OR sugars_100g NOT BETWEEN 0 AND 100
   OR fiber_100g NOT BETWEEN 0 AND 100 OR proteins_100g NOT BETWEEN 0 AND 100
   OR salt_100g NOT BETWEEN 0 AND 100 OR sodium_100g NOT BETWEEN 0 AND 100
   OR fruits_vegetables_legumes_100g NOT BETWEEN 0 AND 100
UNION ALL
SELECT 2, 'borne', 'énergie hors [0, $kcal_max_label] kcal', count(*)
FROM produits
WHERE energy_kcal_100g NOT BETWEEN 0 AND $kcal_max
UNION ALL
SELECT 3, 'cohérence', 'sucres > glucides + $sugars_tolerance_label g', count(*)
FROM produits
WHERE sugars_100g > carbohydrates_100g + $sugars_tolerance
UNION ALL
SELECT 4, 'cohérence', 'saturés > lipides + $saturated_tolerance_label g', count(*)
FROM produits
WHERE saturated_fat_100g > fat_100g + $saturated_tolerance
UNION ALL
SELECT 5, 'cohérence', 'sel ≠ sodium × $salt_per_sodium_label (écart > $salt_sodium_tolerance_label g)', count(*)
FROM produits
WHERE abs(salt_100g - $salt_per_sodium * sodium_100g) > $salt_sodium_tolerance
UNION ALL
SELECT 6, 'cohérence', 'énergie nulle avec un macronutriment positif (hors alcool)', count(*)
FROM produits
WHERE energy_kcal_100g = 0
  AND (fat_100g > 0 OR carbohydrates_100g > 0 OR proteins_100g > 0)
  AND coalesce(aisle_tag, '') <> '$alcohol_group'
ORDER BY ordre;

-- @nom: distribution_nutriscore
-- Par grade : a-e, not-applicable (drapeau du nettoyage), null (inclut « unknown », effacé au nettoyage).
SELECT
    CASE
        WHEN nutriscore_grade IN ('a', 'b', 'c', 'd', 'e') THEN nutriscore_grade
        WHEN grade_not_applicable THEN 'not-applicable'
        ELSE 'null'
    END AS grade,
    count(*) AS produits,
    CAST(100.0 * count(*) / sum(count(*)) OVER () AS DOUBLE PRECISION) AS part_pct,
    CAST(avg(nutriscore_score) AS DOUBLE PRECISION) AS score_moyen
FROM produits
GROUP BY 1
ORDER BY grade;