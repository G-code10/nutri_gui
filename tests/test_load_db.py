"""Tests du chargement : l'entrée est refusée sans base ; le reste tourne sur une base PostgreSQL de TEST.

ATTENTION : load() supprime et recrée les tables. Les tests avec base lisent donc TEST_DATABASE_URL,
jamais DATABASE_URL : ils ne touchent pas à ta vraie base. Sans TEST_DATABASE_URL, ils sont ignorés.
Exemple : export TEST_DATABASE_URL=postgresql://utilisateur:motdepasse@localhost:5432/nutriscope_test
"""

import os

import pandas as pd
import pandera.pandas as pa
import psycopg
import pytest

from src import cleaning, create_db, load_db

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL absente (base PostgreSQL de test)")


def raw_product(code, brands, tags, aisle, **changes):
    """Un produit brut valide ; `changes` écrase des colonnes."""
    row = {
        "code": code, "product_name": "Produit " + code, "brands": brands, "ingredients_text": "sucre",
        "allergens": "", "serving_size": "30 g", "energy_kcal_100g": 450.0, "energy_kj_100g": 1883.0,
        "fat_100g": 20.0, "saturated_fat_100g": 8.0, "carbohydrates_100g": 60.0, "sugars_100g": 25.0,
        "fiber_100g": 3.0, "proteins_100g": 6.0, "salt_100g": 0.5, "sodium_100g": 0.2,
        "fruits_vegetables_legumes_100g": 0.0, "completeness": 0.5, "nutriscore_score": 12,
        "nutriscore_grade": "d", "nova_group": 4, "food_groups_tag_1": aisle, "categories_tags": tags,
    }
    return {**row, **changes}


@pytest.fixture
def clean_df():
    """Trois produits nettoyés : deux marques dont une absente, un rayon inconnu, un code à zéro de tête."""
    raw = pd.DataFrame([
        raw_product("0012345", "Marque A", ["en:snacks", "en:sweets"], "en:biscuits"),
        raw_product("2000002", "Marque A", ["en:snacks"], "en:beverages"),
        raw_product("3000003", None, ["en:drinks"], None),
    ])
    res, _ = cleaning.clean(raw)
    assert len(res) == 3
    return res


# --- Sans base : l'entrée est contrôlée avant toute écriture ---
def test_check_input_accepts_clean_dataframe(clean_df):
    load_db.check_input(clean_df)


def test_check_input_refuses_duplicate_code(clean_df):
    with pytest.raises(ValueError, match="en double"):
        load_db.check_input(pd.concat([clean_df, clean_df], ignore_index=True))


def test_check_input_refuses_schema_violation(clean_df):
    clean_df["nutriscore_grade"] = "f"
    with pytest.raises(pa.errors.SchemaErrors):
        load_db.check_input(clean_df)


def test_aisle_label():
    assert load_db.aisle_label("en:fruits-and-vegetables") == "Fruits and vegetables"


@pytest.fixture
def isolated_env(monkeypatch, tmp_path):
    """Ni db.env réel ni variables POSTGRES_* : le test ne dépend pas de ta machine."""
    monkeypatch.setattr(load_db, "ENV_PATH", tmp_path / "db.env")
    # Copie jetable de l'environnement : ce que le test y écrit disparaît avec lui
    copy = {k: v for k, v in os.environ.items() if k not in load_db.ENV_VARIABLES}
    monkeypatch.setattr(os, "environ", copy)
    return tmp_path / "db.env"


def test_settings_without_env_file_uses_conf(isolated_env):
    assert load_db.settings() == load_db.CONF


def test_settings_reads_database_and_password_from_env_file(isolated_env):
    isolated_env.write_text("POSTGRES_DB=autre_base\nPOSTGRES_PASSWORD=secret\n", encoding="utf-8")
    settings = load_db.settings()
    assert settings["database"] == "autre_base"
    assert settings["password"] == "secret"
    assert settings["user"] == "postgres"   # le reste vient de CONF


def test_settings_optional_variables_override_conf(isolated_env):
    isolated_env.write_text("POSTGRES_USER=moi\nPOSTGRES_HOST=db\nPOSTGRES_PORT=5433\n", encoding="utf-8")
    settings = load_db.settings()
    assert (settings["user"], settings["host"], settings["port"]) == ("moi", "db", 5433)   # port en entier


def test_settings_ignores_commented_lines(isolated_env):
    isolated_env.write_text("# POSTGRES_HOST=db\nPOSTGRES_DB=autre_base\n", encoding="utf-8")
    assert load_db.settings()["host"] == "localhost"


def test_connect_translates_conf_for_psycopg(isolated_env, monkeypatch):
    received = {}
    monkeypatch.setattr(psycopg, "connect", lambda **kwargs: received.update(kwargs))
    load_db.connect()
    assert received == {"dbname": "nutriscope", "user": "postgres", "host": "localhost", "port": 5432,
                        "autocommit": True}   # « database » devient « dbname », « debug » est retiré


# --- Avec une base de test ---
@pytest.fixture
def conn():
    connection = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    create_db.create_schema(connection)   # base vide et schéma neuf avant chaque test
    yield connection
    connection.close()


@needs_db
def test_load_fills_every_table(conn, clean_df):
    counts = load_db.load(clean_df, conn)
    assert counts == {
        "aisles": 3,               # unknown + biscuits + beverages
        "brands": 1,
        "categories": 3,           # snacks, sweets, drinks
        "products": 3,
        "nutrients": 3,
        "product_categories": 4,   # 2 + 1 + 1
    }


@needs_db
def test_load_keeps_leading_zero_missing_brand_and_unknown_aisle(conn, clean_df):
    load_db.load(clean_df, conn)
    assert conn.execute("SELECT code FROM products WHERE code = '0012345'").fetchone() is not None
    brand_id, aisle = conn.execute("SELECT brand_id, aisle_code FROM products WHERE code = '3000003'").fetchone()
    assert brand_id is None
    assert aisle == "unknown"


@needs_db
def test_load_keeps_category_order(conn, clean_df):
    load_db.load(clean_df, conn)
    rows = conn.execute(
        "SELECT c.tag FROM product_categories pc JOIN categories c USING (category_id) "
        "WHERE pc.code = '0012345' ORDER BY pc.position"
    ).fetchall()
    assert [tag for (tag,) in rows] == ["en:snacks", "en:sweets"]


@needs_db
def test_reload_is_complete_and_never_duplicates(conn, clean_df):
    first = load_db.load(clean_df, conn)
    create_db.create_schema(conn)   # rechargement complet : schéma recréé puis rechargé
    second = load_db.load(clean_df, conn)
    assert first == second


@needs_db
def test_loading_twice_without_recreating_the_schema_is_refused(conn, clean_df):
    load_db.load(clean_df, conn)
    with pytest.raises(psycopg.errors.UniqueViolation):
        load_db.load(clean_df, conn)
    assert load_db.count_rows(conn)["products"] == 3   # le second chargement n'a rien écrit


@needs_db
def test_refused_input_leaves_the_database_untouched(conn, clean_df):
    before = load_db.load(clean_df, conn)
    with pytest.raises(ValueError):
        load_db.load(pd.concat([clean_df, clean_df], ignore_index=True), conn)
    assert load_db.count_rows(conn) == before


@needs_db
def test_controls_after_load(conn, clean_df):
    load_db.load(clean_df, conn)
    results = load_db.controls(conn)
    assert results["codes en double"] == [(0,)]
    assert results["produits sans catégorie"] == [(0,)]
    assert results["top marques"] == [("Marque A", 2)]