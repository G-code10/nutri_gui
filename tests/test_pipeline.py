"""Tests de nutriscope/pipeline.py : chaque étape produit ce qu'elle annonce, trouve son entrée seule ou échoue
avec un message utile, ne change rien quand on la relance, et inscrit succès comme échecs au journal.

Données : une petite source déjà aplatie (forme de l'échantillon), tout écrit dans un dossier temporaire.
Les tests qui passent par la base lisent TEST_DATABASE_URL (jamais la vraie base) et sont ignorés sans elle.
"""

import datetime
import hashlib
import json
import os

import pandas as pd
import pytest
from psycopg.conninfo import conninfo_to_dict

from nutriscope import pipeline
from src import config, extract, load_db, utils
from src.storage import convert_parquet, export_features

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL")
needs_db = pytest.mark.skipif(not TEST_DATABASE_URL, reason="TEST_DATABASE_URL absente (base PostgreSQL de test)")

DAY = datetime.date(2026, 11, 2)
YESTERDAY = DAY - datetime.timedelta(days=1)


def raw_product(index: int) -> dict:
    """Produit brut utilisable n° index, avec toutes les colonnes de l'extraction ; grades a à e en alternance."""
    return {
        "code": f"{index:013d}", "product_name": f"Produit {index}", "brands": f"Marque {index % 3}",
        "categories_tags": ["en:snacks"], "main_category": "en:snacks",
        "food_groups_tag_1": ["en:beverages", "en:sugary-snacks", None][index % 3],
        "food_groups_tag_2": ["en:sweetened-beverages", "en:biscuits-and-cakes", None][index % 3],
        "allergens": "", "ingredients_text": "sucre", "additives_n": 1, "nova_group": 4, "nutriscore_score": 5,
        "nutriscore_grade": "abcde"[index % 5], "serving_size": "30 g", "completeness": 0.5,
        "created_t": 1600000000, "last_modified_t": 1700000000,
        "energy_kcal_100g": 4 * 60.0 + 4 * 6.0 + 9 * 20.0, "energy_kj_100g": (4 * 60.0 + 4 * 6.0 + 9 * 20.0) * 4.184,
        "fat_100g": 20.0, "saturated_fat_100g": 8.0, "carbohydrates_100g": 60.0, "sugars_100g": 25.0,
        "fiber_100g": 3.0, "proteins_100g": 6.0, "salt_100g": 0.5, "sodium_100g": 0.2,
        "fruits_vegetables_legumes_100g": 0.0,
    }


@pytest.fixture
def flat_source(tmp_path):
    """Source aplatie de 50 produits (10 par grade), colonnes de l'extraction."""
    path = tmp_path / "source" / "sample_raw.parquet"
    path.parent.mkdir()
    pd.DataFrame([raw_product(index) for index in range(50)])[extract.COLUMNS].to_parquet(path, index=False)
    return path


@pytest.fixture
def make_ctx(tmp_path, flat_source):
    """Fabrique de RunContext : périmètre échantillon, dossier de données et journal temporaires, base de TEST."""
    conf = None
    if TEST_DATABASE_URL:
        params = conninfo_to_dict(TEST_DATABASE_URL)
        conf = {**params, "database": params.pop("dbname")}

    def make(**changes) -> pipeline.RunContext:
        values = {
            "scope": pipeline.SAMPLE, "source": flat_source, "day": DAY, "data_dir": tmp_path / "data",
            "conf": conf, "durations_path": tmp_path / "durations.jsonl",
        }
        return pipeline.RunContext(**{**values, **changes})

    return make


def _journal(ctx) -> list[dict]:
    return [json.loads(line) for line in ctx.durations_path.read_text(encoding="utf-8").splitlines()]


def _hashes(folder) -> dict[str, str]:
    """Empreinte SHA-256 de chaque fichier d'un dossier (relance sans changement)."""
    return {path.relative_to(folder).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in sorted(folder.rglob("*")) if path.is_file()}


# --- Chaque étape produit ce qu'elle annonce ---
def test_load_writes_a_dated_raw_file_and_its_manifest(make_ctx, flat_source):
    ctx = make_ctx()
    result = pipeline.run_step(pipeline.LOAD, ctx)
    raw = utils.dated_path(ctx.raw_dir, config.SAMPLE_RAW_PREFIX, DAY, ".parquet")
    assert result.rows == 50 and result.outputs == [raw, extract.manifest_path(raw)]
    manifest = json.loads(extract.manifest_path(raw).read_text(encoding="utf-8"))
    assert manifest["source_sha256"] == utils.file_sha256(flat_source)


def test_clean_reads_the_most_recent_raw_and_dates_its_own_output(make_ctx):
    pipeline.run_step(pipeline.LOAD, make_ctx(day=YESTERDAY))
    ctx = make_ctx()
    result = pipeline.run_step(pipeline.CLEAN, ctx)   # pas de brut du jour : celui de la veille
    assert result.source.endswith(f"sample_raw_{YESTERDAY:%Y%m%d}.parquet")
    assert result.outputs[0] == utils.dated_path(ctx.clean_dir, config.CLEAN_PREFIX, DAY, ".parquet")
    assert result.outputs[1].parent == ctx.reports_dir and result.rows == 50


def test_export_finds_the_parquet_of_the_day_before_after_exports_are_deleted(make_ctx):
    """Point de contrôle 2 : data/exports/ effacé, la seule étape export retrouve le Parquet de la veille."""
    yesterday = make_ctx(day=YESTERDAY)
    pipeline.run(["load", "clean"], yesterday)
    clean_path = utils.dated_path(yesterday.clean_dir, config.CLEAN_PREFIX, YESTERDAY, ".parquet")
    convert_parquet.convert(clean_path, utils.dated_path(yesterday.parquet_dir, config.PRODUCTS_PREFIX, YESTERDAY),
                            yesterday.durations_path)
    ctx = make_ctx()
    result = pipeline.run_step(pipeline.EXPORT, ctx)
    assert result.rows == 50 and result.source.endswith(f"products_{YESTERDAY:%Y%m%d}")
    for path in result.outputs:
        path.unlink()
    assert pipeline.run_step(pipeline.EXPORT, ctx).details["sha256"] == result.details["sha256"]


def test_export_is_frozen_unless_forced(make_ctx):
    ctx = make_ctx()
    pipeline.run(["load", "clean"], ctx)
    clean_path = utils.dated_path(ctx.clean_dir, config.CLEAN_PREFIX, DAY, ".parquet")
    convert_parquet.convert(clean_path, utils.dated_path(ctx.parquet_dir, config.PRODUCTS_PREFIX, DAY), ctx.durations_path)
    first = pipeline.run_step(pipeline.EXPORT, ctx)
    with pytest.raises(pipeline.StepError, match="--force"):
        pipeline.run_step(pipeline.EXPORT, ctx)
    forced = pipeline.run_step(pipeline.EXPORT, make_ctx(force=True))
    assert forced.details["sha256"] == first.details["sha256"]


# --- Une étape lancée sans son entrée échoue avec un message utile, inscrit au journal ---
def test_clean_without_raw_names_the_step_to_run_and_logs_the_failure(make_ctx):
    ctx = make_ctx()
    with pytest.raises(pipeline.StepError, match="lancer d'abord python -m nutriscope.pipeline load --sample"):
        pipeline.run_step(pipeline.CLEAN, ctx)
    entry = _journal(ctx)[-1]
    assert (entry["step"], entry["status"]) == (pipeline.CLEAN, pipeline.FAILED)
    assert entry["error"].startswith("FileNotFoundError")


def test_load_refuses_a_flat_source_for_the_france_extract(make_ctx):
    with pytest.raises(pipeline.StepError, match="déjà aplatie"):
        pipeline.run_step(pipeline.LOAD, make_ctx(scope=pipeline.FRANCE))


def test_main_fails_with_a_message_and_exit_code_1_without_traceback(tmp_path, monkeypatch, capsys):
    monkeypatch.setitem(pipeline.SCOPES, pipeline.SAMPLE, (tmp_path / "data", config.SAMPLE_RAW_PREFIX, None))
    assert pipeline.main(["export", "--sample", "--date", "20261020"]) == 1
    error = capsys.readouterr().err
    assert "ÉCHEC [export]" in error and "parquet --sample --date 20261020" in error
    assert "Traceback" not in error


def test_journal_has_one_ok_line_per_pipeline_step(make_ctx):
    ctx = make_ctx()
    pipeline.run(["load", "clean"], ctx)
    steps = [(entry["step"], entry["status"]) for entry in _journal(ctx) if entry["step"] in pipeline.STEPS]
    assert steps == [(pipeline.LOAD, pipeline.OK), (pipeline.CLEAN, pipeline.OK)]


# --- Relancée, une étape ne change rien ; les versions anciennes sont supprimées ---
def test_load_and_clean_replayed_the_same_day_rewrite_the_same_bytes(make_ctx):
    ctx = make_ctx()
    pipeline.run(["load", "clean"], ctx)
    raw = utils.dated_path(ctx.raw_dir, config.SAMPLE_RAW_PREFIX, DAY, ".parquet")
    clean = utils.dated_path(ctx.clean_dir, config.CLEAN_PREFIX, DAY, ".parquet")
    before = (utils.file_sha256(raw), utils.file_sha256(clean))
    pipeline.run(["load", "clean"], ctx)
    assert (utils.file_sha256(raw), utils.file_sha256(clean)) == before


def test_only_the_last_versions_are_kept(make_ctx):
    for offset in range(config.KEEP_VERSIONS + 2):
        pipeline.run_step(pipeline.LOAD, make_ctx(day=DAY - datetime.timedelta(days=offset)))
    ctx = make_ctx()
    kept = utils.dated_versions(ctx.raw_dir, config.SAMPLE_RAW_PREFIX)
    assert list(kept) == [DAY - datetime.timedelta(days=offset) for offset in reversed(range(config.KEEP_VERSIONS))]


def test_reset_removes_dated_outputs_but_keeps_exports(make_ctx):
    ctx = make_ctx()
    pipeline.run(["load", "clean"], ctx)
    ctx.exports_dir.mkdir(parents=True)
    export = export_features.export_paths(ctx.exports_dir, DAY)[0]
    export.write_bytes(b"fige")
    removed = pipeline.reset(ctx)
    assert len(removed) == 4   # brut, manifeste, nettoyé, rapport de nettoyage
    assert utils.find_input(ctx.raw_dir, config.SAMPLE_RAW_PREFIX, ".parquet", DAY) is None
    assert export.read_bytes() == b"fige"


# --- Source et ligne de commande ---
def test_source_comes_from_option_then_variable_then_default(make_ctx, tmp_path, monkeypatch):
    monkeypatch.setattr(load_db, "ENV_PATH", tmp_path / "absent.env")   # le db.env réel n'intervient pas
    monkeypatch.delenv(config.SOURCE_ENV, raising=False)
    explicit = tmp_path / "x.parquet"
    assert pipeline.resolve_source(make_ctx(scope=pipeline.FRANCE, source=explicit)) == explicit
    assert pipeline.resolve_source(make_ctx(scope=pipeline.FRANCE, source=None)) == config.FOOD_PARQUET
    assert pipeline.resolve_source(make_ctx(scope=pipeline.SAMPLE, source=None)) == config.SAMPLE_RAW_PATH
    monkeypatch.setenv(config.SOURCE_ENV, "autre/food.parquet")   # relatif : depuis la racine du dépôt
    assert pipeline.resolve_source(make_ctx(scope=pipeline.FRANCE, source=None)) == config.ROOT / "autre" / "food.parquet"


def test_command_line_options():
    args = pipeline.build_parser().parse_args(["all", "--full", "--date", "20261102", "--force", "--docs"])
    assert (args.step, args.scope, args.date, args.force, args.docs) == ("all", pipeline.FULL, DAY, True, True)
    assert pipeline.build_parser().parse_args(["clean"]).scope == pipeline.FRANCE
    with pytest.raises(SystemExit):
        pipeline.build_parser().parse_args(["clean", "--date", "2026-11-02"])


# --- Avec la base de test : les cinq étapes enchaînées ---
@needs_db
def test_all_steps_run_and_database_and_parquet_count_the_same_products(make_ctx):
    """Point de contrôle 1 : les cinq étapes, et le même nombre de produits dans la base et le Parquet."""
    results = pipeline.run(list(pipeline.STEPS), make_ctx())
    by_step = {result.step: result for result in results}
    assert list(by_step) == list(pipeline.STEPS)
    assert by_step[pipeline.LOAD_DB].rows == by_step[pipeline.PARQUET].rows == 50
    assert by_step[pipeline.EXPORT].rows == 50
    assert all(passed for _, passed in by_step[pipeline.LOAD_DB].details["checks"])


@needs_db
def test_parquet_replayed_changes_no_file(make_ctx):
    """Point de contrôle 2 : parquet relancé deux fois de suite, aucun fichier du dossier partitionné ne change."""
    ctx = make_ctx()
    pipeline.run(["load", "clean", "load_db", "parquet"], ctx)
    folder = utils.dated_path(ctx.parquet_dir, config.PRODUCTS_PREFIX, DAY)
    before = _hashes(folder)
    pipeline.run_step(pipeline.PARQUET, ctx)
    assert _hashes(folder) == before