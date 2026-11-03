"""Tests de src/storage/convert_parquet.py : un petit nettoyé fabriqué, puis l'échantillon réel s'il est présent."""

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src import cleaning, config
from src.storage import convert_parquet as cp

SAMPLE_RAW = config.SAMPLE_RAW_PATH


def _clean_frame() -> pd.DataFrame:
    """Petit nettoyé : 4 produits, 3 rayons (dont un NULL et un vide -> unknown), un code à zéro de tête."""
    rows = [
        {"code": "0012345678905", "food_groups_tag_1": "en:sugary-snacks", "nutriscore_grade": "e"},
        {"code": "3000000000001", "food_groups_tag_1": "en:fruits-and-vegetables", "nutriscore_grade": "a"},
        {"code": "3000000000002", "food_groups_tag_1": None, "nutriscore_grade": None},
        {"code": "3000000000003", "food_groups_tag_1": "", "nutriscore_grade": "c"},
    ]
    df = pd.DataFrame(rows)
    for column in cp.COLUMN_SPECS:
        if column not in df.columns:
            df[column] = None
    df["categories_tags"] = [["en:snacks"], ["en:fruits"], ["en:x"], ["en:y"]]
    df["additives_n"] = [2, 0, None, 1]
    df["nova_group"] = [4.0, 1.0, None, 3.0]
    df["created_t"] = [1600000000, 1600000001, 1600000002, 1600000003]
    df["last_modified_t"] = [1700000000, 1700000001, 1700000002, 1700000003]
    df["sugars_100g"] = [30.0, 10.0, None, 5.0]
    df["grade_not_applicable"] = pd.array([False, False, True, False], dtype="boolean")
    df["sugars_100g_missing"] = pd.array([False, False, True, False], dtype="boolean")
    return df


@pytest.fixture
def clean_parquet(tmp_path: Path) -> Path:
    """Nettoyé fabriqué, écrit en Parquet comme le ferait le pipeline."""
    path = tmp_path / "clean" / "products_clean.parquet"
    path.parent.mkdir()
    _clean_frame().to_parquet(path, index=False)
    return path


@pytest.fixture
def converted(clean_parquet: Path, tmp_path: Path) -> Path:
    """Dossier partitionné produit à partir du nettoyé fabriqué."""
    output = tmp_path / "parquet" / "products"
    cp.convert(clean_parquet, output)
    return output


def _read(output: Path) -> pd.DataFrame:
    """Relit le dossier partitionné avec la colonne aisle."""
    pattern = (output / "**" / "*.parquet").as_posix()
    return duckdb.sql(f"SELECT * FROM read_parquet('{pattern}', hive_partitioning = true)").df()


def _hashes(output: Path) -> dict[str, str]:
    """Empreinte SHA-256 de chaque fichier du dossier."""
    return {
        path.relative_to(output).as_posix(): hashlib.sha256(path.read_bytes()).hexdigest()
        for path in sorted(output.rglob("*")) if path.is_file()
    }


def test_one_partition_per_aisle(converted):
    """Un dossier aisle=<slug> par rayon ; NULL et vide tombent dans unknown."""
    folders = sorted(p.name for p in converted.iterdir() if p.is_dir())
    assert folders == ["aisle=en-fruits-and-vegetables", "aisle=en-sugary-snacks", "aisle=unknown"]


def test_all_rows_kept(clean_parquet, tmp_path):
    """Le nombre de lignes renvoyé et relu égale celui du nettoyé."""
    output = tmp_path / "out"
    assert cp.convert(clean_parquet, output) == 4
    assert len(_read(output)) == 4


def test_leading_zero_kept(converted):
    """Le code reste du texte : le zéro de tête survit."""
    assert "0012345678905" in set(_read(converted)["code"])


def test_types_match_schema(converted):
    """Chaque colonne du Parquet a le type annoncé dans son schéma (products_<AAAAMMJJ>.schema.json)."""
    schema = json.loads(cp.schema_path(converted).read_text(encoding="utf-8"))
    pattern = (converted / "**" / "*.parquet").as_posix()
    described = duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{pattern}', hive_partitioning = true)").fetchall()
    assert [(row[0], row[1]) for row in described] == [(c["name"], c["type"]) for c in schema["columns"]]


def test_schema_describes_volumes_and_license(converted):
    """Le schéma donne la clé de partition, la compression, le nombre de lignes et la licence ODbL."""
    schema = json.loads(cp.schema_path(converted).read_text(encoding="utf-8"))
    assert schema["partition_key"] == "aisle"
    assert schema["compression"] == "zstd"
    assert schema["row_count"] == 4
    assert "ODbL" in schema["license"]
    assert all(c["justification"] for c in schema["columns"])


def test_timestamps_converted(converted):
    """created_t (secondes Unix) devient une date UTC."""
    df = _read(converted).set_index("code")
    assert df.loc["0012345678905", "created_t"] == pd.Timestamp("2020-09-13 12:26:40")


def test_flags_typed_boolean(converted):
    """Les drapeaux <col>_missing, non listés un par un, sont typés BOOLEAN."""
    schema = json.loads(cp.schema_path(converted).read_text(encoding="utf-8"))
    types = {c["name"]: c["type"] for c in schema["columns"]}
    assert types["sugars_100g_missing"] == "BOOLEAN"


def test_schema_is_named_after_the_folder(converted):
    """Le schéma d'un dossier products_<AAAAMMJJ> s'appelle products_<AAAAMMJJ>.schema.json, à côté de lui."""
    assert cp.schema_path(converted) == converted.parent / f"{converted.name}.schema.json"
    assert cp.schema_path(converted).exists()


def test_success_marker_written(converted):
    """Le marqueur _SUCCESS est présent à la fin de la conversion."""
    assert (converted / cp.SUCCESS_MARKER).exists()


def test_replay_leaves_no_orphan_partition(clean_parquet, converted):
    """Relancer sur un nettoyé sans un rayon fait disparaître sa partition."""
    df = pd.read_parquet(clean_parquet)
    df[df["food_groups_tag_1"] != "en:sugary-snacks"].to_parquet(clean_parquet, index=False)
    cp.convert(clean_parquet, converted)
    assert not (converted / "aisle=en-sugary-snacks").exists()
    assert len(_read(converted)) == 3


def test_replay_writes_same_bytes(clean_parquet, converted):
    """Relancer sur le même nettoyé réécrit les mêmes données (schéma exclu : il porte la date)."""
    before = _hashes(converted)
    cp.convert(clean_parquet, converted)
    assert _hashes(converted) == before


def test_unknown_column_rejected(clean_parquet, tmp_path):
    """Une colonne sans type déclaré (hors drapeaux) est refusée."""
    df = pd.read_parquet(clean_parquet).assign(surprise=1)
    df.to_parquet(clean_parquet, index=False)
    with pytest.raises(ValueError, match="surprise"):
        cp.convert(clean_parquet, tmp_path / "out")


def test_missing_column_rejected(clean_parquet, tmp_path):
    """Une colonne attendue absente est refusée."""
    pd.read_parquet(clean_parquet).drop(columns=["additives_n"]).to_parquet(clean_parquet, index=False)
    with pytest.raises(ValueError, match="additives_n"):
        cp.convert(clean_parquet, tmp_path / "out")


def test_missing_source_raises(tmp_path):
    """Une source absente lève FileNotFoundError avec l'étape à lancer avant."""
    with pytest.raises(FileNotFoundError, match="nettoyage"):
        cp.convert(tmp_path / "absent.parquet", tmp_path / "out")


@pytest.mark.skipif(not SAMPLE_RAW.exists(), reason="data/raw/sample_raw.parquet absent (python -m scripts.make_sample_raw)")
def test_sample_conversion_keeps_clean_rows(tmp_path):
    """Sur l'échantillon réel nettoyé : toutes les lignes sont conservées, codes uniques, une ligne par rayon."""
    clean_df, _ = cleaning.clean(pd.read_parquet(SAMPLE_RAW))
    source = tmp_path / "products_clean.parquet"
    clean_df.to_parquet(source, index=False)
    output = tmp_path / "products"
    assert cp.convert(source, output) == len(clean_df)
    df = _read(output)
    assert df["code"].is_unique
    folders = {p.name.removeprefix("aisle=") for p in output.iterdir() if p.is_dir()}
    assert folders == set(df["aisle"])


def test_conversion_logs_its_duration(clean_parquet, tmp_path):
    log = tmp_path / "durations.jsonl"
    cp.convert(clean_parquet, tmp_path / "out", durations_path=log)
    entry = json.loads(log.read_text(encoding="utf-8").splitlines()[-1])
    assert entry["step"] == config.STEP_CONVERT and entry["rows"] == 4 and entry["status"] == "ok"