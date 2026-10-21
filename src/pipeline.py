"""Pipeline de bout en bout : lecture -> règles de nettoyage -> rapport -> base PostgreSQL.

Lancement : python -m src.pipeline [--source data/raw/products_nutrition.parquet] [--report docs/data/rapport_nettoyage.md] [--no-db]
Par défaut, la source est la table complète (extract.py) ; pour un essai rapide : --source data/sample_raw.parquet

Rejouable : sur un nouvel export, il repart de zéro (le rapport est réécrit, le schéma de la base est recréé
avant le chargement). Chaque étape annonce ses volumes ; le chargement affiche les lignes par table.
--no-db s'arrête après le rapport (utile quand PostgreSQL n'est pas lancé).
"""

import argparse
from pathlib import Path

import pandas as pd

from src import cleaning, create_db, load_db, report
from src.report import DEFAULT_OUTPUT, DEFAULT_SOURCE

def run(
    source: Path = DEFAULT_SOURCE,
    report_path: Path = DEFAULT_OUTPUT,
    conf: dict | None = None,
    load_to_db: bool = True,
) -> dict:
    """Enchaîne les étapes et renvoie les volumes : lignes lues, lignes nettoyées, lignes par table, contrôles."""
    before = pd.read_parquet(source)
    print(f"[1/5] Lecture : {report.display_path(source)} ({len(before)} lignes)")

    after, rule_reports = cleaning.clean(before)
    print(f"[2/5] Nettoyage : {len(before)} -> {len(after)} lignes ({len(rule_reports)} comptes rendus)")

    written = report.generate_report(before, after, rule_reports, report_path, report.display_path(source))
    print(f"[3/5] Rapport : {report.display_path(written)}")

    summary = {"rows_read": len(before), "rows_clean": len(after), "tables": None, "controls": None}
    if not load_to_db:
        print("[4/5] Base : ignorée (--no-db)")
        return summary

    name = (conf or load_db.settings())["database"]
    created = create_db.create_database_if_missing(conf)
    with load_db.connect(conf) as conn:
        create_db.create_schema(conn)
        print(f"[4/5] Base « {name} » : {'créée' if created else 'déjà existante'}, schéma recréé")

        summary["tables"] = load_db.load(after, conn)
        print("[5/5] Chargement, lignes par table :")
        for table, count in summary["tables"].items():
            print(f"      {table} : {count}")

        summary["controls"] = load_db.controls(conn)
        print("Contrôles :")
        for control, rows in summary["controls"].items():
            if control != "volumétrie par table":   # déjà affichée ci-dessus
                print(f"      {control} : {rows}")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lecture, nettoyage, rapport et chargement de la base.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="parquet brut (colonnes de products_nutrition) ; défaut : table complète")
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT, help="fichier Markdown du rapport")
    parser.add_argument("--no-db", action="store_true", help="s'arrêter après le rapport, sans toucher à la base")
    args = parser.parse_args(argv)
    run(args.source, args.report, load_to_db=not args.no_db)


if __name__ == "__main__":
    main()