DROP TABLE IF EXISTS brands CASCADE;
DROP TABLE IF EXISTS categories CASCADE;
DROP TABLE IF EXISTS products CASCADE;
DROP TABLE IF EXISTS products_categories CASCADE;

-- ============================================
-- Table: brands
-- ============================================
CREATE TABLE brands (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    TEXT NOT NULL,

    CONSTRAINT uq_name_brands
        UNIQUE (name)
);

-- ============================================
-- Table: categories
-- ============================================
CREATE TABLE categories (
    id      BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name    TEXT NOT NULL,

    CONSTRAINT uq_name_categories
        UNIQUE (name)
);

-- ============================================
-- Table: products
-- ============================================
CREATE TABLE products (
    code            BIGINT PRIMARY KEY,
    brand_id        BIGINT NOT NULL,
    brand           TEXT NOT NULL,
    name            TEXT NOT NULL,
    lang            VARCHAR(255) NOT NULL,
    nutriscore      FLOAT,
    fiber           FLOAT,
    proteins        FLOAT,
    energy          FLOAT,
    saturated_fat   FLOAT,
    sugars          FLOAT,
    salt            FLOAT
);

-- CREATE TABLE products (
--     code            BIGINT PRIMARY KEY,
--     brand_id        BIGINT NOT NULL,
--     brand           TEXT NOT NULL,
--     name            TEXT NOT NULL,
--     lang            VARCHAR(255) NOT NULL,
--     nutriments      TEXT
-- );

-- ============================================
-- Table: products_categories (table d'association)
-- ============================================
CREATE TABLE products_categories (
    id              BIGINT GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    category_id     BIGINT NOT NULL,
    product_id      BIGINT NOT NULL,

    CONSTRAINT fk_categories
        FOREIGN KEY (category_id)
        REFERENCES categories (id),

    CONSTRAINT fk_products
        FOREIGN KEY (product_id)
        REFERENCES products (code)
);