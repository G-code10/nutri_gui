"""Tests de src/utils.py (échappement SQL, chemins affichés, rayon, options Parquet, journal des durées, sorties datées),
plus une garde sur les chemins de src/config.py, qui ne contient pas de logique à tester."""

import datetime
import hashlib
import json

import duckdb
import pandas as pd
import pytest

from src import config, utils


# --- sql_literal ---
def test_sql_literal_wraps_in_quotes():
    assert utils.sql_literal("en:france") == "'en:france'"


def test_sql_literal_doubles_inner_quotes():
    assert utils.sql_literal("d'O'Neil") == "'d''O''Neil'"


def test_sql_literal_is_valid_in_duckdb():
    """La chaîne produite est relue par DuckDB à l'identique, apostrophes comprises."""
    value = "en:côte-d'ivoire"
    assert duckdb.sql(f"SELECT {utils.sql_literal(value)}").fetchone()[0] == value


# --- display_path ---
def test_display_path_inside_repository_is_relative():
    assert utils.display_path(config.RAW_DIR / "x.parquet") == "data/raw/x.parquet"


def test_display_path_outside_repository_keeps_only_the_name(tmp_path):
    """Hors du dépôt : seul le nom du fichier, jamais le chemin d'une machine."""
    assert utils.display_path(tmp_path / "ailleurs" / "fichier.parquet") == "fichier.parquet"


# --- aisle_code ---
def test_aisle_code_keeps_tag_and_replaces_null_and_empty():
    tags = pd.Series(["en:beverages", None, "", "en:fruits-and-vegetables"])
    assert list(utils.aisle_code(tags)) == ["en:beverages", "unknown", "unknown", "en:fruits-and-vegetables"]


def test_aisle_code_returns_text_without_missing():
    result = utils.aisle_code(pd.Series([None, None]))
    assert str(result.dtype) == "string"
    assert not result.isna().any()


# --- duckdb_parquet_options ---
def test_duckdb_parquet_options_write_compression_and_license(tmp_path):
    """Un COPY avec ces options écrit un Parquet compressé en ZSTD, licence ODbL dans les métadonnées."""
    path = (tmp_path / "x.parquet").as_posix()
    duckdb.sql(f"COPY (SELECT 1 AS a) TO {utils.sql_literal(path)} (FORMAT PARQUET, {utils.duckdb_parquet_options()})")
    compression = duckdb.sql(f"SELECT DISTINCT compression FROM parquet_metadata('{path}')").fetchone()[0]
    license_ = duckdb.sql(
        f"SELECT decode(value) FROM parquet_kv_metadata('{path}') WHERE decode(key) = 'license'"
    ).fetchone()[0]
    assert compression.upper() == "ZSTD"
    assert license_ == config.LICENSE


# --- aisle_slug_sql ---
def test_aisle_slug_sql_gives_the_partition_slug():
    rows = duckdb.sql(
        f"SELECT {utils.aisle_slug_sql('t')} FROM (VALUES ('en:Fruits and Vegetables'), (NULL), ('  ')) AS v(t)"
    ).fetchall()
    assert [row[0] for row in rows] == ["en-fruits-and-vegetables", "unknown", "unknown"]


# --- format_int, markdown_table ---
def test_format_int_groups_thousands_with_a_space():
    assert utils.format_int(1586106) == "1 586 106"
    assert utils.format_int(12.0) == "12"


def test_markdown_table_has_header_separator_and_rows():
    assert utils.markdown_table(["a", "b"], [[1, 2]]) == "| a | b |\n| --- | --- |\n| 1 | 2 |"


# --- append_duration ---
def test_append_duration_adds_one_json_line_per_call(tmp_path):
    log = tmp_path / "logs" / "durations.jsonl"
    utils.append_duration("clean_rules", 1.23456, 42, "data/raw/x.parquet", log)
    utils.append_duration("report", 0.5, None, "data/raw/x.parquet", log)
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [entry["step"] for entry in entries] == ["clean_rules", "report"]
    assert entries[0] | {"timestamp": None} == {
        "timestamp": None, "step": "clean_rules", "seconds": 1.235, "status": "ok", "rows": 42,
        "source": "data/raw/x.parquet", "error": None,
    }


def test_append_duration_records_a_failure_with_its_message(tmp_path):
    log = tmp_path / "durations.jsonl"
    utils.append_duration("clean", 0.2, None, None, log, status="failed", error="FileNotFoundError: x")
    entry = json.loads(log.read_text(encoding="utf-8"))
    assert (entry["status"], entry["error"], entry["rows"]) == ("failed", "FileNotFoundError: x", None)


# --- file_sha256 ---
def test_file_sha256_matches_hashlib(tmp_path):
    path = tmp_path / "x.bin"
    path.write_bytes(b"abc" * 1_000_000)   # plus d'un bloc de lecture
    assert utils.file_sha256(path) == hashlib.sha256(path.read_bytes()).hexdigest()


# --- Sorties datées ---
DAY = datetime.date(2026, 11, 2)


def _touch_versions(directory, prefix, days, suffix=".parquet"):
    """Crée une version datée (fichier vide) par date donnée, et renvoie leurs chemins."""
    directory.mkdir(parents=True, exist_ok=True)
    paths = [utils.dated_path(directory, prefix, day, suffix) for day in days]
    for path in paths:
        path.write_bytes(b"")
    return paths


def test_dated_path_uses_yyyymmdd():
    assert utils.dated_path(config.CLEAN_DIR, "products_clean", DAY, ".parquet").name == "products_clean_20261102.parquet"


def test_find_input_takes_the_day_then_the_most_recent_before(tmp_path):
    days = [datetime.date(2026, 10, 30), datetime.date(2026, 10, 31), datetime.date(2026, 11, 3)]
    _old, recent, future = _touch_versions(tmp_path, "products_clean", days)
    assert utils.find_input(tmp_path, "products_clean", ".parquet", DAY) == recent   # le 03/11 est après : ignoré
    assert utils.find_input(tmp_path, "products_clean", ".parquet", datetime.date(2026, 11, 3)) == future
    assert utils.find_input(tmp_path, "products_clean", ".parquet", datetime.date(2026, 10, 1)) is None


def test_find_input_ignores_other_prefixes_and_bad_dates(tmp_path):
    _touch_versions(tmp_path, "products_clean", [DAY])
    (tmp_path / "products_20261399").mkdir()   # date invalide
    assert utils.find_input(tmp_path, "products", "", DAY) is None   # « products_clean_… » n'est pas « products_… »


def test_find_input_skips_a_folder_without_success_marker(tmp_path):
    complete = utils.dated_path(tmp_path, "products", datetime.date(2026, 11, 1))
    complete.mkdir()
    (complete / config.SUCCESS_MARKER).write_text("")
    utils.dated_path(tmp_path, "products", DAY).mkdir()   # interrompu : sans _SUCCESS
    assert utils.find_input(tmp_path, "products", "", DAY, require_success=True) == complete


def test_require_input_names_the_step_to_run(tmp_path):
    with pytest.raises(FileNotFoundError, match="lancer d'abord python -m nutriscope.pipeline load"):
        utils.require_input(tmp_path, "france_extract", ".parquet", DAY, "python -m nutriscope.pipeline load")


def test_prune_versions_keeps_the_most_recent_with_their_companions(tmp_path):
    days = [datetime.date(2026, 11, day) for day in range(1, 6)]
    parquets = _touch_versions(tmp_path, "france_extract", days)
    manifests = _touch_versions(tmp_path, "france_extract", days, ".manifest.json")
    (tmp_path / "sample_raw.parquet").write_bytes(b"")   # non daté : jamais touché
    removed = utils.prune_versions(tmp_path, "france_extract", keep=3)
    assert sorted(removed) == sorted(parquets[:2] + manifests[:2])
    assert sorted(p.name for p in tmp_path.iterdir()) == sorted(
        [p.name for p in parquets[2:] + manifests[2:]] + ["sample_raw.parquet"]
    )


def test_prune_versions_removes_folders_and_keep_zero_removes_all(tmp_path):
    for day in (1, 2):
        folder = utils.dated_path(tmp_path, "products", datetime.date(2026, 11, day))
        (folder / "aisle=unknown").mkdir(parents=True)
    assert len(utils.prune_versions(tmp_path, "products", keep=0)) == 2
    assert list(tmp_path.iterdir()) == []


# --- Chemins de src/config.py ---
CONFIG_PATHS = [
    config.DATA_DIR, config.FOOD_PARQUET, config.RAW_DIR, config.SAMPLE_RAW_PATH, config.CLEAN_DIR,
    config.PARQUET_DIR, config.EXPORTS_DIR, config.REPORTS_DIR, config.DURATIONS_LOG_PATH,
    config.SAMPLE_DATA_DIR, config.FULL_DATA_DIR, config.CLEANING_REPORT_PATH, config.CONTROLS_REPORT_PATH,
]


def test_config_paths_are_absolute_and_inside_root():
    """Tous les chemins de config.py sont absolus et sous la racine du dépôt : aucun chemin d'un poste particulier."""
    for path in CONFIG_PATHS:
        assert path.is_absolute()
        assert path.is_relative_to(config.ROOT)