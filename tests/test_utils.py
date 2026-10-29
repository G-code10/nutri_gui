"""Tests de src/utils.py (échappement SQL, chemins affichés, rayon, options Parquet, journal des durées),
plus une garde sur les chemins de src/config.py, qui ne contient pas de logique à tester."""

import json

import duckdb
import pandas as pd

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
    assert utils.display_path(config.RAW_PATH) == "data/raw/products_nutrition.parquet"


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
    log = tmp_path / "logs" / "durees.jsonl"
    utils.append_duration("nettoyage", 1.23456, 42, "data/raw/x.parquet", log)
    utils.append_duration("rapport", 0.5, None, "data/raw/x.parquet", log)
    entries = [json.loads(line) for line in log.read_text(encoding="utf-8").splitlines()]
    assert [entry["step"] for entry in entries] == ["nettoyage", "rapport"]
    assert entries[0] | {"timestamp": None} == {
        "timestamp": None, "step": "nettoyage", "seconds": 1.235, "status": "ok", "rows": 42, "source": "data/raw/x.parquet",
    }


# --- Chemins de src/config.py ---
CONFIG_PATHS = [
    config.DATA_DIR, config.FOOD_PARQUET, config.RAW_DIR, config.RAW_PATH, config.FRANCE_EXTRACT_PATH,
    config.SAMPLE_RAW_PATH, config.CLEAN_PATH, config.PARQUET_DIR, config.PRODUCTS_PARQUET_DIR,
    config.EXPORTS_DIR, config.DURATIONS_LOG_PATH, config.CLEANING_REPORT_PATH,
]


def test_config_paths_are_absolute_and_inside_root():
    """Tous les chemins de config.py sont absolus et sous la racine du dépôt : aucun chemin d'un poste particulier."""
    for path in CONFIG_PATHS:
        assert path.is_absolute()
        assert path.is_relative_to(config.ROOT)