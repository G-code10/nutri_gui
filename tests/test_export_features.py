"""Tests de src/storage/export_features.py : filtres, ratios, schéma, export figé et reproductible.

Données : un petit nettoyé fabriqué produit par produit (un cas par règle), converti en Parquet partitionné
par convert_parquet, comme dans la chaîne réelle.
"""

import json
from datetime import date

import duckdb
import pandas as pd
import pytest

from src import cleaning, config
from src.storage import convert_parquet
from src.storage import export_features as ef

FROZEN_ON = date(2026, 10, 28)

# Produit utilisable de référence : sept nutriments présents, ratios sous 1
BASE = {
    "food_groups_tag_1": "en:sugary-snacks", "nutriscore_grade": "c", "nutriscore_score": 5,
    "energy_kcal_100g": 400.0, "fat_100g": 20.0, "saturated_fat_100g": 5.0, "carbohydrates_100g": 50.0,
    "sugars_100g": 25.0, "proteins_100g": 6.0, "salt_100g": 0.5, "fiber_100g": 3.0,
    "fruits_vegetables_legumes_100g": 0.0, "additives_n": 2, "nova_group": 4,
}

# code -> écarts à BASE ; les codes en « 1… » sont retenus, ceux en « 9… » écartés par un filtre
PRODUCTS = {
    "0000000000001": {},                                                    # zéro de tête : reste du texte
    "1000000000002": {"food_groups_tag_1": None},                           # rayon unknown : retenu
    "1000000000003": {"carbohydrates_100g": 0.0, "sugars_100g": 0.0},       # ratio 0 / 0 -> 0
    "1000000000004": {"carbohydrates_100g": 0.0, "sugars_100g": 0.3},       # dénominateur 0 seul -> NULL
    "1000000000005": {"carbohydrates_100g": 10.0, "sugars_100g": 10.3},     # ratio 1,03 -> plafonné à 1
    "1000000000006": {"fiber_100g": None, "nova_group": None, "additives_n": None},
    "9000000000001": {"nutriscore_grade": None},                            # cible absente
    "9000000000002": {"salt_100g": None},                                   # nutriment clé absent
    "9000000000003": {"energy_kcal_100g": 0.0},                             # énergie nulle
    "9000000000004": {"carbohydrates_100g": 10.0, "sugars_100g": 10.6},     # sucres > glucides + 0,5
    "9000000000005": {"fat_100g": 5.0, "saturated_fat_100g": 5.6},          # saturés > lipides + 0,5
}
KEPT = sorted(code for code in PRODUCTS if not code.startswith("9"))


def _clean_frame() -> pd.DataFrame:
    """Nettoyé fabriqué : toutes les colonnes attendues par convert_parquet, puis BASE et les écarts."""
    rows = []
    for index, (code, changes) in enumerate(PRODUCTS.items()):
        row = dict.fromkeys(convert_parquet.COLUMN_SPECS)
        row.update(BASE, code=code, categories_tags=["en:snacks"], created_t=1600000000 + index,
                   last_modified_t=1700000000 + index, grade_not_applicable=False)
        row.update(changes)
        rows.append(row)
    df = pd.DataFrame(rows)
    df["grade_not_applicable"] = df["grade_not_applicable"].astype("boolean")
    return df


@pytest.fixture
def source(tmp_path):
    """Parquet partitionné (avec _SUCCESS) construit à partir du nettoyé fabriqué."""
    clean_path = tmp_path / "products_clean.parquet"
    _clean_frame().to_parquet(clean_path, index=False)
    output = tmp_path / "parquet" / "produits"
    convert_parquet.convert(clean_path, output, durations_path=tmp_path / "durees.jsonl")
    return output


@pytest.fixture
def exported(source, tmp_path):
    """(schéma renvoyé, Parquet exporté, schéma écrit) d'un export daté FROZEN_ON."""
    out_dir = tmp_path / "exports"
    schema = ef.export(source, out_dir, frozen_on=FROZEN_ON)
    parquet_path, schema_file = ef.export_paths(out_dir, FROZEN_ON)
    return schema, parquet_path, schema_file


def _read(path) -> pd.DataFrame:
    return duckdb.sql(f"SELECT * FROM read_parquet('{path.as_posix()}')").df()


# --- Noms et filtres ---
def test_export_paths_are_dated():
    parquet_path, schema_file = ef.export_paths(config.EXPORTS_DIR, FROZEN_ON)
    assert parquet_path.name == "features_nutriscore_20261028.parquet"
    assert schema_file.name == "features_nutriscore_20261028.schema.json"


def test_only_usable_products_are_kept_sorted_by_code(exported):
    _, parquet_path, _ = exported
    assert list(_read(parquet_path)["code"]) == KEPT


def test_aisle_comes_from_the_partition(exported):
    df = _read(exported[1]).set_index("code")
    assert df.loc["0000000000001", "aisle"] == "en-sugary-snacks"
    assert df.loc["1000000000002", "aisle"] == config.UNKNOWN_AISLE


# --- Ratios ---
def test_ratios_follow_the_rules(exported):
    ratio = _read(exported[1]).set_index("code")["sugars_carbohydrates_ratio"]
    assert ratio["0000000000001"] == pytest.approx(0.5)
    assert ratio["1000000000003"] == 0.0              # 0 / 0
    assert pd.isna(ratio["1000000000004"])            # 0,3 / 0
    assert ratio["1000000000005"] == ef.RATIO_MAX     # 1,03 plafonné


def test_fat_energy_ratio_uses_nine_kcal_per_gram(exported):
    ratio = _read(exported[1]).set_index("code")["fat_energy_ratio"]
    assert ratio["0000000000001"] == pytest.approx(9 * 20.0 / 400.0)


def test_capped_ratios_are_counted_in_the_schema(exported):
    capped = exported[0]["ratios"]["capped"]
    assert capped == {"sugars_carbohydrates_ratio": 1, "saturated_fat_ratio": 0, "fat_energy_ratio": 0}


# --- Schéma ---
def test_schema_columns_match_the_parquet_in_order(exported):
    schema, parquet_path, schema_file = exported
    described = duckdb.sql(f"DESCRIBE SELECT * FROM read_parquet('{parquet_path.as_posix()}')").fetchall()
    written = json.loads(schema_file.read_text(encoding="utf-8"))
    assert written == schema
    assert [(c["name"], c["type"]) for c in schema["columns"]] == [(row[0], row[1]) for row in described]


def test_schema_describes_the_export(exported):
    schema, parquet_path, _ = exported
    assert schema["rows"] == len(KEPT) and schema["frozen_on"] == "2026-10-28"
    assert schema["target"] == "nutriscore_grade" and schema["identifier"] == "code"
    assert schema["target_distribution"] == {"c": len(KEPT)}
    assert schema["sha256"] == ef._sha256(parquet_path)
    assert "ODbL" in schema["license"] and schema["usage"]["interdits"]


def test_target_has_no_missing_values(exported):
    schema, parquet_path, _ = exported
    assert _read(parquet_path)["nutriscore_grade"].notna().all()
    target = next(c for c in schema["columns"] if c["name"] == "nutriscore_grade")
    assert target["missing_pct"] == 0.0 and target["role"] == "cible"


def test_missing_rates_and_policies(exported):
    columns = {c["name"]: c for c in exported[0]["columns"]}
    assert columns["fiber_100g"]["missing_pct"] == pytest.approx(100 / len(KEPT), abs=0.01)
    assert columns["fiber_100g"]["missing_policy"] == cleaning.DEFAULT_MISSING_STRATEGY["fiber_100g"]
    assert columns["nova_group"]["missing_policy"] == cleaning.DEFAULT_MISSING_STRATEGY["nova_group"]
    assert columns["additives_n"]["missing_policy"] == ef.DEFAULT_POLICY
    assert columns["fat_energy_ratio"]["missing_policy"] == ef.DEFAULT_POLICY
    assert columns["salt_100g"]["missing_policy"] == ef.NEVER_MISSING_POLICY


# --- Export figé et reproductible ---
def test_existing_export_is_not_overwritten_without_force(source, exported):
    _, parquet_path, _ = exported
    with pytest.raises(FileExistsError, match="--force"):
        ef.export(source, parquet_path.parent, frozen_on=FROZEN_ON)


def test_force_rewrites_the_same_bytes(source, exported):
    schema, parquet_path, _ = exported
    again = ef.export(source, parquet_path.parent, frozen_on=FROZEN_ON, force=True)
    assert again["sha256"] == schema["sha256"]
    assert not list(parquet_path.parent.glob("*.tmp"))


def test_incomplete_source_is_refused(source, tmp_path):
    (source / convert_parquet.SUCCESS_MARKER).unlink()
    with pytest.raises(FileNotFoundError, match="convert_parquet"):
        ef.export(source, tmp_path / "exports", frozen_on=FROZEN_ON)
    assert not (tmp_path / "exports").exists()