"""Tests de la création du schéma, sur une base PostgreSQL de TEST (TEST_DATABASE_URL, jamais DATABASE_URL).

create_schema() supprime et recrée les tables : ne jamais viser la vraie base.
Sans TEST_DATABASE_URL, ces tests sont ignorés.
"""

import os

import psycopg
import pytest

from src import create_db, load_db

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
pytestmark = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL absente (base PostgreSQL de test)")


@pytest.fixture
def conn():
    connection = psycopg.connect(TEST_DATABASE_URL, autocommit=True)
    yield connection
    connection.close()


def test_create_schema_creates_every_table_empty_except_unknown_aisle(conn):
    create_db.create_schema(conn)
    counts = load_db.count_rows(conn)
    assert counts == {"aisles": 1, "brands": 0, "categories": 0, "products": 0, "nutrients": 0,
                      "product_categories": 0}   # seul le rayon 'unknown' existe


def test_create_schema_can_be_replayed(conn):
    create_db.create_schema(conn)
    create_db.create_schema(conn)   # ne doit pas échouer


def test_create_database_if_missing_creates_once(conn):
    params = psycopg.conninfo.conninfo_to_dict(TEST_DATABASE_URL)
    params.pop("dbname", None)
    conf = {**params, "database": "nutriscope_create_test"}   # base jetable, distincte de la base de test
    conn.execute("DROP DATABASE IF EXISTS nutriscope_create_test")
    try:
        assert create_db.create_database_if_missing(conf) is True    # elle manquait : créée
        assert create_db.create_database_if_missing(conf) is False   # elle existe : rien à faire
    finally:
        conn.execute("DROP DATABASE IF EXISTS nutriscope_create_test")


def test_check_constraint_refuses_an_invalid_grade(conn):
    create_db.create_schema(conn)
    with pytest.raises(psycopg.errors.CheckViolation):
        conn.execute("INSERT INTO products (code, nutriscore_grade) VALUES ('1', 'f')")