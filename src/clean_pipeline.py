"""Nettoyage et chargement de la base : lecture -> règles de nettoyage -> nettoyé écrit -> rapport -> base PostgreSQL.

Deux fonctions, appelées séparément par le pipeline (nutriscope/pipeline.py) :
- clean() : lecture du brut, cleaning.clean(), nettoyé écrit, rapport (étape clean) ;
- load_database() : schéma recréé, nettoyé chargé, contrôles du chargement (étape load_db).
run() enchaîne les deux, pour la commande ci-dessous.

Lancement : python -m src.clean_pipeline [--source data/raw/sample_raw.parquet] [--clean-out data/clean/x.parquet]
                                         [--report docs/data/rapport_nettoyage.md] [--no-db]
Sans --source : le brut de l'extrait France le plus récent ; sans --clean-out : le nettoyé daté du jour.

Rejouable : sur un nouvel export, il repart de zéro (le nettoyé et le rapport sont réécrits, le schéma de la base
est recréé avant le chargement). Chaque étape annonce ses volumes ; le chargement affiche les lignes par table.
--no-db s'arrête après le rapport (utile quand PostgreSQL n'est pas lancé, ou pour nettoyer seulement).
Le nettoyé écrit est l'entrée du chargement et de la conversion Parquet (src/storage/convert_parquet.py) :
base et Parquet partent ainsi du même nettoyé.
"""

import argparse
import time
from pathlib import Path

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

from src import cleaning, config, create_db, load_db, report
from src.utils import append_duration, dated_path, display_path, require_input, today

DEFAULT_OUTPUT = config.CLEANING_REPORT_PATH


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


def _logger(source: Path, durations_path: Path | None):
    """Fonction qui inscrit une sous-étape réussie au journal des durées, avec la source indiquée."""
    source_label = display_path(source)

    def log(step: str, started: float, rows: int | None) -> None:
        append_duration(step, time.perf_counter() - started, rows, source_label, durations_path)

    return log


def clean(source: Path, clean_path: Path, report_path: Path, durations_path: Path | None = None) -> dict:
    """Lit le brut, le nettoie, écrit le nettoyé et le rapport ; renvoie les volumes et les fichiers écrits.

    Chaque sous-étape réussie ajoute sa durée au journal (config.DURATIONS_LOG_PATH par défaut) :
    le benchmark y lit le coût de construction du nettoyé.
    """
    log = _logger(source, durations_path)
    source_label = display_path(source)

    started = time.perf_counter()
    before = pd.read_parquet(source)
    log(config.STEP_READ, started, len(before))
    print(f"      Lecture : {source_label} ({len(before)} lignes)")

    started = time.perf_counter()
    after, rule_reports = cleaning.clean(before)
    log(config.STEP_CLEAN, started, len(after))
    print(f"      Nettoyage : {len(before)} -> {len(after)} lignes ({len(rule_reports)} comptes rendus)")

    started = time.perf_counter()
    clean_written = _write_clean(after, clean_path)
    log(config.STEP_WRITE_CLEAN, started, len(after))
    print(f"      Nettoyé : {display_path(clean_written)}")

    started = time.perf_counter()
    written = report.generate_report(before, after, rule_reports, report_path, source_label)
    log(config.STEP_REPORT, started, len(after))
    print(f"      Rapport : {display_path(written)}")

    return {"rows_read": len(before), "rows_clean": len(after), "clean_path": clean_written, "report_path": written}


def load_database(clean_path: Path, conf: dict | None = None, durations_path: Path | None = None) -> dict:
    """Recrée le schéma, charge le nettoyé écrit et rejoue les contrôles du chargement ; renvoie tables et contrôles.

    Rechargement complet : la base créée si elle manque, le schéma recréé (tables vides), puis le chargement en une
    transaction (load_db.load). Lit le nettoyé sur disque : la base part du même fichier que le Parquet.
    """
    log = _logger(clean_path, durations_path)
    df = pd.read_parquet(clean_path)

    name = (conf or load_db.settings())["database"]
    started = time.perf_counter()
    created = create_db.create_database_if_missing(conf)
    with load_db.connect(conf) as conn:
        create_db.create_schema(conn)
        log(config.STEP_DB_SCHEMA, started, None)
        print(f"      Base « {name} » : {'créée' if created else 'déjà existante'}, schéma recréé")

        started = time.perf_counter()
        tables = load_db.load(df, conn)
        log(config.STEP_DB_LOAD, started, tables["products"])
        print("      Chargement, lignes par table :")
        for table, count in tables.items():
            print(f"        {table} : {count}")

        controls = load_db.controls(conn)
        print("      Contrôles du chargement :")
        for control, rows in controls.items():
            if control != "volumétrie par table":   # déjà affichée ci-dessus
                print(f"        {control} : {rows}")
    return {"tables": tables, "controls": controls}


def run(
    source: Path,
    report_path: Path = DEFAULT_OUTPUT,
    conf: dict | None = None,
    load_to_db: bool = True,
    clean_path: Path | None = None,
    durations_path: Path | None = None,
) -> dict:
    """clean() puis, sauf load_to_db=False, load_database() ; renvoie les volumes, lignes par table et contrôles.

    `clean_path` vaut par défaut le nettoyé daté du jour dans config.CLEAN_DIR.
    """
    clean_path = clean_path or dated_path(config.CLEAN_DIR, config.CLEAN_PREFIX, today(), ".parquet")
    summary = clean(source, clean_path, report_path, durations_path)
    summary.update({"tables": None, "controls": None})
    if not load_to_db:
        print("      Base : ignorée (--no-db)")
        return summary
    summary.update(load_database(summary["clean_path"], conf, durations_path))
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Lecture, nettoyage, nettoyé écrit, rapport et chargement de la base.")
    parser.add_argument("--source", type=Path, help="parquet brut (défaut : extrait France le plus récent)")
    parser.add_argument("--clean-out", type=Path, help="parquet nettoyé à écrire (défaut : daté du jour)")
    parser.add_argument("--report", type=Path, default=DEFAULT_OUTPUT, help="fichier Markdown du rapport")
    parser.add_argument("--no-db", action="store_true", help="s'arrêter après le rapport, sans toucher à la base")
    args = parser.parse_args(argv)
    source = args.source or require_input(
        config.RAW_DIR, config.FRANCE_EXTRACT_PREFIX, ".parquet", None, "python -m nutriscope.pipeline load"
    )
    run(source, args.report, load_to_db=not args.no_db, clean_path=args.clean_out)


if __name__ == "__main__":
    main()