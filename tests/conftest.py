"""Préparation commune des tests : chemin des imports pour que pytest trouve les fichier .py, et base PostgreSQL de test créée si elle manque."""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import create_db, load_db

# Chargé dès l'import de ce fichier, donc avant la collecte des tests (qui lisent TEST_DATABASE_URL à l'import).
# TEST_DATABASE_URL peut être définie dans db.env ; un export fait dans le terminal l'emporte.
load_dotenv(load_db.ENV_PATH)


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Une fois par session : crée la base de TEST_DATABASE_URL si elle n'existe pas encore.

    TEST_DATABASE_URL vient de db.env (ou du terminal). Sans elle, ne fait rien (les tests avec base sont ignorés). Garde-fou : si l'URL vise la vraie
    base (celle de db.env), la session s'arrête avant que le moindre test ne vide ses tables.
    """
    url = os.environ.get("TEST_DATABASE_URL")
    if not url:
        return
    params = conninfo_to_dict(url)
    name = params.pop("dbname", None)
    if not name:
        pytest.exit("TEST_DATABASE_URL doit nommer une base (…/nutriscope_test).", returncode=2)
    if name == load_db.settings()["database"]:
        pytest.exit(
            f"TEST_DATABASE_URL vise la vraie base « {name} » : les tests la videraient. Choisis une autre base.",
            returncode=2,
        )
    create_db.create_database_if_missing({**params, "database": name})