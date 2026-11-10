"""Préparation commune des tests : chemin des imports pour que pytest trouve les fichier .py, et base PostgreSQL de test créée si elle manque."""

import os
import sys
from pathlib import Path

import pytest
from dotenv import load_dotenv
from psycopg.conninfo import conninfo_to_dict, make_conninfo

ROOT = Path(__file__).resolve().parent.parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import config, create_db, load_db  # après l'ajout de la racine au chemin des imports

# Chargé dès l'import de ce fichier, donc avant la collecte des tests (qui lisent TEST_DATABASE_URL à l'import).
# Un export fait dans le terminal l'emporte sur db.env.
load_dotenv(load_db.ENV_PATH)

TEST_URL_ENV = "TEST_DATABASE_URL"   # connexion complète à la base de test, lue par les fichiers de test
TEST_DB_ENV = "TEST_POSTGRES_DB"     # ou seulement le nom de la base de test : le reste vient de db.env


def _test_database_url() -> str | None:
    """Connexion à la base de test : TEST_DATABASE_URL si elle est définie, sinon celle de db.env avec TEST_POSTGRES_DB pour nom.

    Ainsi le mot de passe n'est écrit qu'une fois, dans POSTGRES_PASSWORD. TEST_DATABASE_URL définie mais vide
    (« TEST_DATABASE_URL= python -m pytest ») désactive les tests avec base. Rien de défini : None.
    """
    if TEST_URL_ENV in os.environ:
        return os.environ[TEST_URL_ENV]
    name = os.environ.get(TEST_DB_ENV)
    if not name:
        return None
    return make_conninfo(**{**load_db.connection_params(), "dbname": name})


# Les fichiers de test lisent TEST_DATABASE_URL à leur import, qui vient après celui de ce fichier
_url = _test_database_url()
if _url:
    os.environ[TEST_URL_ENV] = _url


@pytest.fixture(scope="session", autouse=True)
def test_database():
    """Une fois par session : crée la base de test (TEST_DATABASE_URL, ou TEST_POSTGRES_DB) si elle n'existe pas encore.

    Sans l'une ni l'autre, ne fait rien (les tests avec base sont ignorés). Garde-fou : si la connexion vise la vraie
    base (celle de db.env), la session s'arrête avant que le moindre test ne vide ses tables.
    """
    url = os.environ.get(TEST_URL_ENV)
    if not url:
        return
    params = conninfo_to_dict(url)
    name = params.pop("dbname", None)
    if not name:
        pytest.exit("La connexion de test doit nommer une base (TEST_POSTGRES_DB=nutriscope_test).", returncode=2)
    if name == load_db.settings()["database"]:
        pytest.exit(
            f"La base de test vise la vraie base « {name} » : les tests la videraient. Choisis un autre TEST_POSTGRES_DB.",
            returncode=2,
        )
    create_db.create_database_if_missing({**params, "database": name})


@pytest.fixture(scope="session", autouse=True)
def isolated_durations_log(tmp_path_factory):
    """Pour toute la session : le journal des durées écrit par les tests va dans un dossier temporaire.

    Portée « session » : elle s'applique avant les fixtures de module (une conversion faite par une fixture
    de module n'écrit donc jamais dans le data/durations.jsonl du dépôt).
    """
    with pytest.MonkeyPatch.context() as patch:
        path = tmp_path_factory.mktemp("durations") / "durations.jsonl"
        patch.setattr(config, "DURATIONS_LOG_PATH", path)
        yield path