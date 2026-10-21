"""Pipeline de bout en bout : lecture -> règles de nettoyage -> nettoyé écrit -> rapport -> base PostgreSQL.

Lancement : python -m src.pipeline [--source data/sample_raw.parquet] [--clean-out data/clean/products_clean.parquet]
                                   [--report docs/data/rapport_nettoyage.md] [--no-db]

Rejouable : sur un nouvel export, il repart de zéro (le nettoyé et le rapport sont réécrits, le schéma de la base
est recréé avant le chargement). Chaque étape annonce ses volumes ; le chargement affiche les lignes par table.
--no-db s'arrête après le rapport (utile quand PostgreSQL n'est pas lancé, ou pour nettoyer seulement).
Le nettoyé écrit est l'entrée de la conversion Parquet (src/storage/convert_parquet.py) : base et Parquet
partent ainsi du même nettoyé.
"""

import argparse
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src import cleaning, config, create_db, load_db, report
from src.utils import display_path

DEFAULT_SOURCE = config.RAW_PATH
DEFAULT_OUTPUT = config.CLEANING_REPORT_PATH
DEFAULT_CLEAN = config.CLEAN_PATH


def _write_clean(df: pd.DataFrame, path: Path) -> Path:
    """Écrit le nettoyé en Parquet (ZSTD, licence ODbL en métadonnées), via un fichier temporaire renommé à la fin.

    Une interruption ne laisse donc jamais un nettoyé à moitié écrit sous le nom attendu.
    """
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    table = pa.Table.from_pandas(df, preserve_index=False)
    table = table.replace_schema_metadata({**(table.schema.metadata or {}), b"license": config.LICENSE.encode()})
    temporary = path.with_name(path.name + ".tmp")
    pq.write_table(table, temporary, compression=config.COMPRESSION)
    temporary.replace(path)
    return path


def run(
    source: Path = DEFAULT_SOURCE,
    report_path: Path = DEFAULT_OUTPUT,
    conf: dict | None = None,
    load_to_db: bool = True,
    clean_path: Path = DEFAULT_CLEAN,
) -> dict:
    """Enchaîne les étapes et renvoie les volumes : lignes lues, lignes nettoyées, nettoyé écrit, lignes par table, contrôles."""
    before = pd.read_parquet(source)
    print(f"[1/6] Lecture : {display_path(source)} ({len(before)} lignes)")

    after, rule_reports = cleaning.clean(before)
    print(f"[2/6] Nettoyage : {len(before)} -> {len(after)} lignes ({len(rule_reports)} comptes rendus)")

    clean_written = _write_clean(after, clean_path)
    print(f"[3/6] Nettoyé : {display_path(clean_written)}")

    written = report.generate_report(before, after, rule_reports, report_path, display_path(source))
    print(f"[4/6] Rapport : {display_path(written)}")

    summary = {
        "rows_read": len(before), "rows_clean": len(after), "clean_path": clean_written,
        "tables": None, "controls": None,
    }
    if not load_to_db:
        print("[5/6] Base : ignorée (--no-db)")
        return summary

    name = (conf or load_db.settings())["database"]
    created = create_db.create_database_if_missing(conf)
    with load_db.connect(conf) as conn:
        create_db.create_schema(conn)
        print(f"[5/6] Base « {name} » : {'créée' if created else 'déjà existante'}, schéma recréé")

        summary["tables"] = load_db.load(after, conn)
        print("[6/6] Chargement, lignes par table :")
        for table, count in summary["tables"].items():
            print(f"      {table} : {count}")

        summary["controls"] = load_db.controls(conn)
        print("Contrôles :")
        for control, rows in summary["controls"].items():
            if control != "volumétrie par table":   # déjà affichée ci-dessus
                print(f"      {control} : {rows}")
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lecture, nettoyage, nettoyé écrit, rapport et chargement de la base.")
    parser.add_argument("--source", type=Path, default=DEFAULT_SOURCE, help="parquet brut (colonnes de products_nutrition)")
    parser.add_argument("--clean-out", type=Path, default=DEFAULT_CLEAN, help="parquet nettoyé à écrire")
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT, help="fichier Markdown du rapport")
    parser.add_argument("--no-db", action="store_true", help="s'arrêter après le rapport, sans toucher à la base")
    args = parser.parse_args(argv)
    run(args.source, args.report, load_to_db=not args.no_db, clean_path=args.clean_out)


if __name__ == "__main__":
    main()