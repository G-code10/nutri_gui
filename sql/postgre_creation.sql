-- ============================================================================
-- NutriScope : schéma PostgreSQL des données NETTOYÉES (sortie de cleaning.clean)
-- ----------------------------------------------------------------------------
-- La base ne reçoit que des données nettoyées : les contraintes CHECK reprennent
-- les bornes de cleaning.py (RANGES) et sont le dernier garde-fou si une règle
-- laisse passer une valeur aberrante. Un CHECK laisse passer NULL : un nutriment
-- manquant (NA après nettoyage) est donc accepté, une valeur hors borne est refusée.
--
-- Les colonnes portent les mêmes noms que le DataFrame nettoyé, pour que le
-- chargement n'ait rien à renommer.
--
-- Les drapeaux <col>_missing qui valent exactement « <col> IS NULL » ne sont PAS
-- stockés (ils se retrouvent par requête, et ils vivent dans le Parquet pour le ML).
-- Seuls sont stockés ceux qu'on ne peut pas retrouver depuis les colonnes :
--   grade_not_applicable, saturated_fat_100g_missing, energy_kcal_100g_missing.
-- ============================================================================

-- On supprime d'abord les tables qui dépendent des autres
DROP TABLE IF EXISTS product_categories CASCADE;
DROP TABLE IF EXISTS nutrients CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS brands CASCADE;
DROP TABLE IF EXISTS aisles CASCADE;

-- ============================================================================
-- Table: aisles (rayons, issus de food_groups_tag_1)
-- ============================================================================
CREATE TABLE aisles (
    aisle_code  TEXT PRIMARY KEY,
    label       TEXT NOT NULL
);

-- Rayon par défaut des produits sans groupe alimentaire
INSERT INTO aisles (aisle_code, label) VALUES ('unknown', 'Inconnu');

-- ============================================================================
-- Table: brands
-- ============================================================================
CREATE TABLE brands (
    brand_id    BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        TEXT NOT NULL,

    CONSTRAINT uq_brands_name UNIQUE (name)
);

-- ============================================================================
-- Table: categories (une ligne par tag distinct de categories_tags)
-- ============================================================================
CREATE TABLE categories (
    category_id BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    tag         TEXT NOT NULL,

    CONSTRAINT uq_categories_tag UNIQUE (tag)
);

-- ============================================================================
-- Table: products
-- ============================================================================
CREATE TABLE products (
    -- Code-barres en TEXTE : un BIGINT perdrait les zéros de tête
    code                 TEXT PRIMARY KEY,
    product_name         TEXT,
    brand_id             BIGINT,
    aisle_code           TEXT NOT NULL DEFAULT 'unknown',
    main_category        TEXT,
    ingredients_text     TEXT,
    allergens            TEXT,          -- NULL = inconnu, '' = aucun allergène déclaré
    serving_size         TEXT,
    nova_group           SMALLINT,
    nutriscore_score     SMALLINT,
    nutriscore_grade     CHAR(1),
    -- Vrai si le grade valait « not-applicable » avant d'être effacé (NULL ne le dit pas)
    grade_not_applicable BOOLEAN NOT NULL DEFAULT FALSE,
    completeness         DOUBLE PRECISION,
    last_modified_t      BIGINT,        -- horodatage source (secondes depuis 1970)

    CONSTRAINT ck_products_code
        CHECK (code <> '' AND code = btrim(code)),
    CONSTRAINT ck_products_nova
        CHECK (nova_group BETWEEN 1 AND 4),
    -- Étendue observée dans les données : -17 à 55
    CONSTRAINT ck_products_nutriscore_score
        CHECK (nutriscore_score BETWEEN -17 AND 55),
    CONSTRAINT ck_products_nutriscore_grade
        CHECK (nutriscore_grade IN ('a', 'b', 'c', 'd', 'e')),
    -- Pas de borne haute : le maximum observé est 1,1 (en float32, soit 1,100000024 une fois converti en float64)
    CONSTRAINT ck_products_completeness
        CHECK (completeness >= 0),
    -- Un grade « non applicable » n'a pas de grade a-e
    CONSTRAINT ck_products_grade_not_applicable
        CHECK (NOT grade_not_applicable OR nutriscore_grade IS NULL),

    CONSTRAINT fk_products_brand
        FOREIGN KEY (brand_id) REFERENCES brands (brand_id) ON DELETE SET NULL,
    CONSTRAINT fk_products_aisle
        FOREIGN KEY (aisle_code) REFERENCES aisles (aisle_code)
);

CREATE INDEX ix_products_brand ON products (brand_id);
CREATE INDEX ix_products_aisle ON products (aisle_code);
CREATE INDEX ix_products_grade ON products (nutriscore_grade);

-- ============================================================================
-- Table: nutrients (1 ligne par produit, valeurs pour 100 g)
-- ============================================================================
-- DOUBLE PRECISION : pas d'arrondi entre pandas (float64) et la base, donc les
-- bornes (dont 3765.6 kJ) se comparent exactement.
CREATE TABLE nutrients (
    code                            TEXT PRIMARY KEY,
    energy_kcal_100g                DOUBLE PRECISION,
    energy_kj_100g                  DOUBLE PRECISION,
    fat_100g                        DOUBLE PRECISION,
    saturated_fat_100g              DOUBLE PRECISION,
    carbohydrates_100g              DOUBLE PRECISION,
    sugars_100g                     DOUBLE PRECISION,
    fiber_100g                      DOUBLE PRECISION,
    proteins_100g                   DOUBLE PRECISION,
    salt_100g                       DOUBLE PRECISION,
    sodium_100g                     DOUBLE PRECISION,
    fruits_vegetables_legumes_100g  DOUBLE PRECISION,
    -- Vrai si la valeur manquait à l'origine et a été comblée ou recalculée ensuite
    saturated_fat_100g_missing      BOOLEAN NOT NULL DEFAULT FALSE,
    energy_kcal_100g_missing        BOOLEAN NOT NULL DEFAULT FALSE,

    -- Bornes de cleaning.RANGES
    CONSTRAINT ck_nutrients_energy_kcal
        CHECK (energy_kcal_100g BETWEEN 0 AND 900),
    CONSTRAINT ck_nutrients_energy_kj
        CHECK (energy_kj_100g BETWEEN 0 AND 3765.6),
    CONSTRAINT ck_nutrients_fat
        CHECK (fat_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_saturated_fat
        CHECK (saturated_fat_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_carbohydrates
        CHECK (carbohydrates_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_sugars
        CHECK (sugars_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_fiber
        CHECK (fiber_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_proteins
        CHECK (proteins_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_salt
        CHECK (salt_100g BETWEEN 0 AND 100),
    CONSTRAINT ck_nutrients_sodium
        CHECK (sodium_100g BETWEEN 0 AND 40),
    CONSTRAINT ck_nutrients_fruits_vegetables_legumes
        CHECK (fruits_vegetables_legumes_100g BETWEEN 0 AND 100),

    -- Cohérences imposées par neutralize_subpart_above_total (tolérance de 0,5 g)
    CONSTRAINT ck_nutrients_sugars_le_carbohydrates
        CHECK (sugars_100g <= carbohydrates_100g + 0.5),
    CONSTRAINT ck_nutrients_saturated_le_fat
        CHECK (saturated_fat_100g <= fat_100g + 0.5),

    CONSTRAINT fk_nutrients_product
        FOREIGN KEY (code) REFERENCES products (code) ON DELETE CASCADE
);

-- ============================================================================
-- Table: product_categories (association produit - catégorie)
-- ============================================================================
CREATE TABLE product_categories (
    code        TEXT NOT NULL,
    category_id BIGINT NOT NULL,
    -- Rang du tag dans categories_tags (1 = le plus général)
    position    SMALLINT NOT NULL,

    CONSTRAINT pk_product_categories
        PRIMARY KEY (code, category_id),
    CONSTRAINT ck_product_categories_position
        CHECK (position >= 1),
    CONSTRAINT fk_product_categories_product
        FOREIGN KEY (code) REFERENCES products (code) ON DELETE CASCADE,
    CONSTRAINT fk_product_categories_category
        FOREIGN KEY (category_id) REFERENCES categories (category_id) ON DELETE CASCADE
);

CREATE INDEX ix_product_categories_category ON product_categories (category_id);