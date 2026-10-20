"""Création de la base PostgreSQL puis de son schéma (étape à part du chargement).

Deux niveaux : la base elle-même (create_database_if_missing), puis ses tables depuis sql/create_db.sql
(create_schema). Le fichier SQL supprime puis recrée toutes les tables : la base repart vide, sans donnée.
Lancement seul : python -m src.create_db   (connexion : CONF de load_db.py complétée par db.env)
"""

from pathlib import Path

import psycopg
from psycopg import sql

from src import load_db

SQL_PATH = Path(__file__).resolve().parent.parent / "sql" / "create_db.sql"
ADMIN_DATABASE = "postgres"   # base qui existe toujours : on s'y connecte pour créer les autres


def create_database_if_missing(conf: dict | None = None) -> bool:
    """Crée la base de `conf` (CONF par défaut) si elle manque. Renvoie True si elle vient d'être créée."""
    conf = dict(load_db.settings() if conf is None else conf)
    name = conf["database"]
    with load_db.connect({**conf, "database": ADMIN_DATABASE}) as admin:
        if admin.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone():
            return False
        admin.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))   # hors transaction : autocommit
        return True


def create_schema(conn: psycopg.Connection) -> None:
    """Recrée les tables, contraintes et index dans UNE transaction : tout est créé, ou rien."""
    with conn.transaction():
        conn.execute(SQL_PATH.read_text(encoding="utf-8"))


if __name__ == "__main__":
    created = create_database_if_missing()
    print(f"Base « {load_db.settings()['database']} » :", "créée" if created else "déjà existante")
    with load_db.connect() as connection:
        create_schema(connection)
    print("Schéma créé :", ", ".join(load_db.TABLES))