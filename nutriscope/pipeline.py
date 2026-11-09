"""Pipeline NutriScope ML complète

5 étapes :

load      source --> brut daté + manifeste (SHA-256 de la source) --> src/extract.py
clean     brut --> nettoyé daté + rapport de nettoyage (règles métiers) --> src/clean_pipeline.py
load_db   nettoyé --> base Postgres et contrôles sur la base --> src/clean_pipeline.py et src/storage/run_queries.py
parquet   nettoyé --> Parquet partitionné daté et contrôles comparés à la base --> src/storage/convert_parquet.py et src/storage/run_queries.py
export    Parquet --> export features daté, avec son split train / test figé et schéma --> src/storage/export_features.py

python -m nutriscope.pipeline all                 # extrait France, sorties datées du jour
python -m nutriscope.pipeline clean               # une seule étape
python -m nutriscope.pipeline all --sample        # sur l'échantillon (data/raw/sample_raw.parquet)
python -m nutriscope.pipeline all --full          # sur le fichier complet
python -m nutriscope.pipeline export --date 20261102 --force   # rejouer une date
python -m nutriscope.pipeline all --docs          # rapports écrits dans docs/data/ (versionnés)
python -m nutriscope.pipeline reset               # supprime les sorties datées (jamais les exports)

sorties datées et périmètre france par défaut

Données : © Open Food Facts contributors — ODbL.
"""

import argparse
import datetime
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

from dotenv import load_dotenv

from src import clean_pipeline, config, extract, load_db
from src.storage import convert_parquet, export_features, run_queries
from src.utils import (
    DATE_FORMAT,
    append_duration,
    dated_path,
    display_path,
    format_int,
    parse_day,
    prune_versions,
    require_input,
    today,
)

# Noms des étapes (journal des durées, ligne de commande), dans l'ordre d'exécution
LOAD, CLEAN, LOAD_DB, PARQUET, EXPORT = "load", "clean", "load_db", "parquet", "export"
ALL, RESET = "all", "reset"
OK, FAILED = "ok", "failed"

# Périmètres : dossier de données, préfixe du brut, filtre pays de l'extraction
FRANCE, FULL, SAMPLE = "france", "full", "sample"
SCOPES = {
    FRANCE: (config.DATA_DIR, config.FRANCE_EXTRACT_PREFIX, extract.FRANCE_TAG),
    FULL: (config.FULL_DATA_DIR, config.FULL_RAW_PREFIX, None),
    SAMPLE: (config.SAMPLE_DATA_DIR, config.SAMPLE_RAW_PREFIX, None),
}
SCOPE_OPTIONS = {FRANCE: "", FULL: " --full", SAMPLE: " --sample"}


@dataclass(frozen=True)
class RunContext:
    """contexte initialisé dans main() et réutilisé par plusieurs fonctions du fichier : donne une même signature aux étapes et fige leurs champs (frozen)."""

    scope: str = FRANCE
    source: Path | None = None
    day: datetime.date = field(default_factory=today)
    force: bool = False
    docs: bool = False
    data_dir: Path | None = None
    conf: dict | None = None
    durations_path: Path | None = None

    @property
    def root(self) -> Path:
        return Path(self.data_dir) if self.data_dir is not None else SCOPES[self.scope][0]

    @property
    def raw_prefix(self) -> str:
        return SCOPES[self.scope][1]

    @property
    def country(self) -> str | None:
        return SCOPES[self.scope][2]

    # sous-dossiers, mêmes noms que ceux de config sous le root du périmètre
    @property
    def raw_dir(self) -> Path:
        return self.root / config.RAW_DIR.name

    @property
    def clean_dir(self) -> Path:
        return self.root / config.CLEAN_DIR.name

    @property
    def parquet_dir(self) -> Path:
        return self.root / config.PARQUET_DIR.name

    @property
    def exports_dir(self) -> Path:
        return self.root / config.EXPORTS_DIR.name

    @property
    def reports_dir(self) -> Path:
        return self.root / config.REPORTS_DIR.name


@dataclass
class StepResult:
    """ce que renvoie chaque étape : lignes traitées, fichiers écrits et supprimés, entrée , détails, durée"""

    step: str
    rows: int
    outputs: list[Path]
    source: str
    removed: list[Path] = field(default_factory=list)
    details: dict = field(default_factory=dict)
    seconds: float = 0.0


class StepError(Exception):
    """echec d'une étape son nom et l'erreur d'origine"""

    def __init__(self, step: str, cause: Exception):
        super().__init__(f"[{step}] {type(cause).__name__} : {cause}")
        self.step = step
        self.cause = cause


# outils
def _hint(step: str, ctx: RunContext) -> str:
    """commande à lancer avant étape pour fabriquer le message d'erreur d'une entrée absente"""
    date_option = "" if ctx.day == today() else f" --date {ctx.day.strftime(DATE_FORMAT)}"
    return f"python -m nutriscope.pipeline {step}{SCOPE_OPTIONS[ctx.scope]}{date_option}"


def _report_path(ctx: RunContext, prefix: str, docs_path: Path) -> Path:
    """choisis le chemin pour écrire un rapport, avec --docs pour les rapports finaux"""
    return docs_path if ctx.docs else dated_path(ctx.reports_dir, prefix, ctx.day, ".md")


def _prune_reports(ctx: RunContext, prefix: str) -> list[Path]:
    """supprime les rapport daté au dela de 3 version, rien avec --docs (rapports finaux non daté)"""
    return [] if ctx.docs else prune_versions(ctx.reports_dir, prefix)


def resolve_source(ctx: RunContext) -> Path:
    """source de l'étape load = --source si précisé, sinon l'échantillon avec --sample, sinon NUTRISCOPE_SOURCE
    (terminal, puis db.env), sinon data/food.parquet
    NUTRISCOPE_SOURCE part de la racine sauf si chemin absolu, pas du dossier courant"""
    if ctx.source is not None:
        return Path(ctx.source)
    if ctx.scope == SAMPLE:
        return config.SAMPLE_RAW_PATH
    load_dotenv(load_db.ENV_PATH)   # n'écrase pas ce qui est déjà défini dans le terminal
    value = os.environ.get(config.SOURCE_ENV)
    if not value:
        return config.FOOD_PARQUET
    path = Path(value).expanduser()
    return path if path.is_absolute() else config.ROOT / path


# les cinq étapes : même signature, (RunContext) -> StepResult 
def load_step(ctx: RunContext) -> StepResult:
    """source -> brut daté et son manifeste | filtre France sur la source du périmètre par défaut"""
    source = resolve_source(ctx)
    if not source.exists():
        raise FileNotFoundError(
            f"source introuvable : {display_path(source)} (placer food.parquet dans data/, ou définir {config.SOURCE_ENV}, "
            "ou passer --source ; pour l'échantillon : --sample)"
        )
    output = dated_path(ctx.raw_dir, ctx.raw_prefix, ctx.day, ".parquet")
    rows = extract.extract(source, output, ctx.country)
    removed = prune_versions(ctx.raw_dir, ctx.raw_prefix)
    return StepResult(LOAD, rows, [output, extract.manifest_path(output)], display_path(source), removed)


def clean_step(ctx: RunContext) -> StepResult:
    """brut le plus récent -> nettoyé daté + rapport de nettoyage"""
    raw = require_input(ctx.raw_dir, ctx.raw_prefix, ".parquet", ctx.day, _hint(LOAD, ctx))
    clean_path = dated_path(ctx.clean_dir, config.CLEAN_PREFIX, ctx.day, ".parquet")
    report_path = _report_path(ctx, config.CLEANING_REPORT_PREFIX, config.CLEANING_REPORT_PATH)
    summary = clean_pipeline.clean(raw, clean_path, report_path, ctx.durations_path)
    removed = prune_versions(ctx.clean_dir, config.CLEAN_PREFIX) + _prune_reports(ctx, config.CLEANING_REPORT_PREFIX)
    return StepResult(CLEAN, summary["rows_clean"], [clean_path, report_path], display_path(raw), removed,
                      {"rows_read": summary["rows_read"]})


def load_db_step(ctx: RunContext) -> StepResult:
    """nettoyé le plus récent -> base rechargée entièrement puis les cinq contrôles sur la base seule"""
    clean_path = require_input(ctx.clean_dir, config.CLEAN_PREFIX, ".parquet", ctx.day, _hint(CLEAN, ctx))
    summary = clean_pipeline.load_database(clean_path, ctx.conf, ctx.durations_path)
    controls = run_queries.check_database(ctx.conf)
    print("      Contrôles sur la base (sql/controles.sql) :")
    for label, passed in controls["checks"]:
        print(f"        [{'ok' if passed else 'ÉCHEC'}] {label}")
    return StepResult(LOAD_DB, summary["tables"]["products"], [], display_path(clean_path),
                      details={"tables": summary["tables"], "checks": controls["checks"]})


def parquet_step(ctx: RunContext) -> StepResult:
    """nettoyé le plus récent -> parquet partitionné daté puis contrôles comparés à la base (même nettoyé ?)."""
    clean_path = require_input(ctx.clean_dir, config.CLEAN_PREFIX, ".parquet", ctx.day, _hint(CLEAN, ctx))
    output = dated_path(ctx.parquet_dir, config.PRODUCTS_PREFIX, ctx.day)
    rows = convert_parquet.convert(clean_path, output, ctx.durations_path)
    report_path = _report_path(ctx, config.CONTROLS_REPORT_PREFIX, config.CONTROLS_REPORT_PATH)
    summary = run_queries.check_parquet_against_database(output, report_path, ctx.conf)
    print(f"      Base et Parquet : {format_int(summary['database'].total)} et {format_int(summary['parquet'].total)} "
          "produits, contrôles identiques")
    removed = prune_versions(ctx.parquet_dir, config.PRODUCTS_PREFIX) + _prune_reports(ctx, config.CONTROLS_REPORT_PREFIX)
    outputs = [output, convert_parquet.schema_path(output), report_path]
    return StepResult(PARQUET, rows, outputs, display_path(clean_path), removed)


def export_step(ctx: RunContext) -> StepResult:
    """Parquet partitionné complet le plus récent -> export features daté, avec son split ; jamais supprimé ensuite."""
    source = require_input(ctx.parquet_dir, config.PRODUCTS_PREFIX, "", ctx.day, _hint(PARQUET, ctx), require_success=True)
    schema = export_features.export(source, ctx.exports_dir, frozen_on=ctx.day, force=ctx.force)
    for grade, counts in schema["split"]["counts"].items():
        print(f"      Grade {grade} : {format_int(counts['train'])} train, {format_int(counts['test'])} test "
              f"({counts['test_pct']:.1f} % en test)".replace(".", ","))
    print(f"      SHA-256 : {schema['sha256']}")
    outputs = list(export_features.export_paths(ctx.exports_dir, ctx.day))
    return StepResult(EXPORT, schema["rows"], outputs, display_path(source), details={"sha256": schema["sha256"]})


STEPS = {LOAD: load_step, CLEAN: clean_step, LOAD_DB: load_db_step, PARQUET: parquet_step, EXPORT: export_step}


# exécution et journal
def _print_result(result: StepResult) -> None:
    """Résumé d'une étape : lignes, durée, fichiers écrits et versions supprimées."""
    print(f"[{result.step}] {format_int(result.rows)} lignes en {result.seconds:.1f} s".replace(".", ","))
    for path in result.outputs:
        print(f"      écrit : {display_path(path)}")
    for path in result.removed:
        print(f"      supprimé (au-delà de {config.KEEP_VERSIONS} versions) : {display_path(path)}")


def run_step(name: str, ctx: RunContext) -> StepResult:
    """Lance une étape, l'inscrit au journal des durées (ok ou failed), affiche son résumé ; renvoie son résultat.

    Lève StepError si l'étape échoue, après avoir inscrit l'échec au journal : le journal ne ment pas.
    """
    print(f"[{name}] démarrage")
    started = time.perf_counter()
    try:
        result = STEPS[name](ctx)
    except Exception as error:
        append_duration(name, time.perf_counter() - started, None, None, ctx.durations_path,
                        status=FAILED, error=f"{type(error).__name__}: {error}")
        raise StepError(name, error) from error
    result.seconds = time.perf_counter() - started
    append_duration(name, result.seconds, result.rows, result.source, ctx.durations_path)
    _print_result(result)
    return result


def run(names: list[str], ctx: RunContext) -> list[StepResult]:
    """Lance les étapes dans l'ordre demandé ; s'arrête à la première qui échoue (StepError)."""
    return [run_step(name, ctx) for name in names]


def reset(ctx: RunContext) -> list[Path]:
    """Supprime toutes les sorties datées du périmètre (brut, nettoyé, Parquet, rapports) ; renvoie ce qui est supprimé.

    Jamais les exports (figés), ni l'échantillon, ni la source, ni le journal des durées, ni la base.
    """
    targets = [
        (ctx.raw_dir, ctx.raw_prefix),
        (ctx.clean_dir, config.CLEAN_PREFIX),
        (ctx.parquet_dir, config.PRODUCTS_PREFIX),
        (ctx.reports_dir, config.CLEANING_REPORT_PREFIX),
        (ctx.reports_dir, config.CONTROLS_REPORT_PREFIX),
    ]
    removed = []
    for directory, prefix in targets:
        removed += prune_versions(directory, prefix, keep=0)
    return removed


# ligne de commande
def _parse_day(value: str) -> datetime.date:
    """--date AAAAMMJJ -> date ; refusée par argparse si invalide."""
    try:
        return parse_day(value)
    except ValueError as error:
        raise argparse.ArgumentTypeError(f"date attendue au format AAAAMMJJ : {value}") from error


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m nutriscope.pipeline",
        description="Pipeline NutriScope : load, clean, load_db, parquet, export (ou all), et reset.",
    )
    parser.add_argument("step", choices=[*STEPS, ALL, RESET], help="étape à lancer, all pour les cinq, reset pour nettoyer")
    scope = parser.add_mutually_exclusive_group()
    scope.add_argument("--full", action="store_const", dest="scope", const=FULL, help="fichier complet (data/full/)")
    scope.add_argument("--sample", action="store_const", dest="scope", const=SAMPLE, help="échantillon (data/sample/)")
    parser.add_argument("--source", type=Path, help=f"source de load (défaut : {config.SOURCE_ENV} ou data/food.parquet)")
    parser.add_argument("--date", type=_parse_day, help="date des sorties, AAAAMMJJ (défaut : aujourd'hui)")
    parser.add_argument("--force", action="store_true", help="réécrire l'export de la date s'il existe")
    parser.add_argument("--docs", action="store_true", help="écrire les rapports dans docs/data/ (versionnés)")
    parser.set_defaults(scope=FRANCE)
    return parser


def main(argv: list[str] | None = None) -> int:
    """point d'entrée : renvoie 0 si tout a réussi, 1 si une étape a échoué (message sans trace Python)."""
    args = build_parser().parse_args(argv)
    ctx = RunContext(scope=args.scope, source=args.source, day=args.date or today(), force=args.force, docs=args.docs)
    print(f"Pipeline NutriScope : périmètre {ctx.scope}, date {ctx.day.isoformat()}, données {display_path(ctx.root)}")

    if args.step == RESET:
        removed = reset(ctx)
        for path in removed:
            print(f"      supprimé : {display_path(path)}")
        print(f"[reset] {len(removed)} sortie(s) supprimée(s) ; exports conservés")
        return 0

    names = list(STEPS) if args.step == ALL else [args.step]
    started = time.perf_counter()
    try:
        run(names, ctx)
    except StepError as error:
        print(f"ÉCHEC {error}", file=sys.stderr)
        print(f"Échec inscrit au journal : {display_path(ctx.durations_path or config.DURATIONS_LOG_PATH)}", file=sys.stderr)
        return 1
    if len(names) > 1:
        print(f"Pipeline terminé : {len(names)} étapes en {time.perf_counter() - started:.1f} s".replace(".", ","))
    return 0


if __name__ == "__main__":
    sys.exit(main())