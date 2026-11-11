"""Tests de src/extract.py sur un petit Parquet au format Open Food Facts fabriqué pour l'occasion,
puis sur une source déjà aplatie (forme de l'échantillon), et le manifeste écrit à côté du brut."""

import hashlib
import json
from pathlib import Path

import duckdb
import pandas as pd
import pytest

from src import extract

# Trois produits : France avec zéro de tête, Belgique, France sans 'energy-kj' (repli sur 'energy')
FAKE_OFF_SQL = """
    COPY (
        SELECT * FROM (VALUES
            ('0123456789012',
             [{'lang': 'fr', 'text': 'Biscuit'}], 'MarqueA', ['en:snacks'], 'en:biscuits',
             ['en:sugary-snacks', 'en:biscuits-and-cakes'], ['en:gluten', 'en:milk'],
             [{'lang': 'fr', 'text': 'farine, sucre'}], 2, 4, 18, 'e', '30 g', 0.8::FLOAT,
             1600000000::BIGINT, 1700000000::BIGINT, ['en:france'],
             [{'name': 'energy-kcal', '100g': 450.0::FLOAT}, {'name': 'energy-kj', '100g': 1880.0::FLOAT},
              {'name': 'fat', '100g': 20.0::FLOAT}, {'name': 'sugars', '100g': 30.0::FLOAT},
              {'name': 'salt', '100g': 0.5::FLOAT}]),
            ('5400000000001',
             [{'lang': 'fr', 'text': 'Eau'}], '', ['en:waters'], 'en:waters',
             ['en:beverages'], [],
             [{'lang': 'fr', 'text': 'eau'}], 0, 1, 0, 'a', NULL, 0.5::FLOAT,
             1600000001::BIGINT, 1700000001::BIGINT, ['en:belgium'],
             [{'name': 'energy-kcal', '100g': 0.0::FLOAT}]),
            ('3000000000002',
             [{'lang': 'fr', 'text': 'Pomme'}], 'MarqueB', ['en:fruits'], 'en:apples',
             ['en:fruits-and-vegetables'], [],
             NULL, NULL, 1, -5, 'a', NULL, 0.6::FLOAT,
             1600000002::BIGINT, 1700000002::BIGINT, ['en:france', 'en:belgium'],
             [{'name': 'energy', '100g': 218.0::FLOAT}])
        ) AS v(code, product_name, brands, categories_tags, compared_to_category, food_groups_tags,
               allergens_tags, ingredients_text, additives_n, nova_group, nutriscore_score, nutriscore_grade,
               serving_size, completeness, created_t, last_modified_t, countries_tags, nutriments)
    ) TO '{path}' (FORMAT PARQUET)
"""


@pytest.fixture
def off_parquet(tmp_path: Path) -> Path:
    """Faux Parquet OFF de trois produits, avec les champs imbriqués du vrai fichier."""
    path = tmp_path / "food.parquet"
    duckdb.sql(FAKE_OFF_SQL.replace("{path}", path.as_posix()))  # pas de format() : les structs SQL ont des accolades
    return path


def _read(path: Path):
    """Lit un Parquet produit en DataFrame trié par code."""
    return duckdb.sql(f"SELECT * FROM read_parquet('{path.as_posix()}') ORDER BY code").df()


def test_columns_match_reference_order(off_parquet, tmp_path):
    """Les colonnes écrites sont celles de COLUMNS, dans le même ordre, avec additives_n et created_t."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    assert list(_read(out).columns) == extract.COLUMNS
    assert {"additives_n", "created_t"} <= set(extract.COLUMNS)


def test_extract_keeps_all_rows_without_country(off_parquet, tmp_path):
    """Sans pays, toutes les lignes sont extraites et le compte renvoyé est juste."""
    assert extract.extract(off_parquet, tmp_path / "raw.parquet") == 3


def test_country_filter_keeps_only_country(off_parquet, tmp_path):
    """Avec en:france, seuls les produits vendus en France restent (y compris multi-pays)."""
    out = tmp_path / "fr.parquet"
    assert extract.extract(off_parquet, out, extract.FRANCE_TAG) == 2
    assert set(_read(out)["code"]) == {"0123456789012", "3000000000002"}


def test_leading_zero_code_preserved(off_parquet, tmp_path):
    """Le code-barres reste du texte : le zéro de tête survit."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    assert "0123456789012" in set(_read(out)["code"])


def test_nested_fields_flattened(off_parquet, tmp_path):
    """Nom, ingrédients, groupe et allergènes sont tirés des champs imbriqués ; marque vide -> NULL."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    df = _read(out).set_index("code")
    biscuit = df.loc["0123456789012"]
    assert biscuit["product_name"] == "Biscuit"
    assert biscuit["ingredients_text"] == "farine, sucre"
    assert biscuit["food_groups_tag_1"] == "en:sugary-snacks"
    assert biscuit["food_groups_tag_2"] == "en:biscuits-and-cakes"
    assert pd.isna(df.loc["5400000000001", "food_groups_tag_2"])
    assert biscuit["allergens"] == "en:gluten,en:milk"
    assert pd.isna(df.loc["5400000000001", "brands"])


def test_nutriments_unfolded_with_energy_fallback(off_parquet, tmp_path):
    """Les nutriments sont dépliés ; sans 'energy-kj', les kJ viennent de 'energy'."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    df = _read(out).set_index("code")
    assert df.loc["0123456789012", "energy_kcal_100g"] == pytest.approx(450.0)
    assert df.loc["0123456789012", "sugars_100g"] == pytest.approx(30.0)
    assert df.loc["3000000000002", "energy_kj_100g"] == pytest.approx(218.0)


def test_extract_is_replayable(off_parquet, tmp_path):
    """Relancer écrase la sortie : un extrait France après un extrait complet ne garde que la France."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    assert extract.extract(off_parquet, out, extract.FRANCE_TAG) == 2
    assert len(_read(out)) == 2


def test_license_written_in_metadata(off_parquet, tmp_path):
    """La licence ODbL est écrite dans les métadonnées clé-valeur du Parquet."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    rows = duckdb.sql(
        f"SELECT decode(value) FROM parquet_kv_metadata('{out.as_posix()}') WHERE decode(key) = 'license'"
    ).fetchall()
    assert rows and "ODbL" in rows[0][0]


def test_create_raw_table_matches_extract(off_parquet):
    """La table créée pour make_sample_raw a les mêmes colonnes que l'extraction."""
    con = duckdb.connect()
    extract.create_raw_table(con, off_parquet)
    columns = [row[0] for row in con.execute("DESCRIBE products_nutrition").fetchall()]
    assert columns == extract.COLUMNS


def test_missing_source_raises(tmp_path):
    """Une source absente lève FileNotFoundError, sans créer de sortie."""
    out = tmp_path / "raw.parquet"
    with pytest.raises(FileNotFoundError):
        extract.extract(tmp_path / "absent.parquet", out)
    assert not out.exists()


def test_paths_with_quote_are_escaped(off_parquet, tmp_path):
    """Une apostrophe dans le chemin source ou de sortie ne casse pas la requête."""
    folder = tmp_path / "dossier d'O'Neil"
    folder.mkdir()
    source = folder / "food.parquet"
    off_parquet.rename(source)
    assert extract.extract(source, folder / "raw.parquet") == 3


def test_country_with_quote_is_escaped(off_parquet, tmp_path):
    """Une apostrophe dans le tag pays ne casse pas la requête (aucune ligne, pas d'erreur)."""
    assert extract.extract(off_parquet, tmp_path / "x.parquet", "en:côte-d'ivoire") == 0


# --- Source déjà aplatie (forme de l'échantillon) et manifeste ---
@pytest.fixture
def flat_parquet(off_parquet, tmp_path) -> Path:
    """Source aplatie : le brut extrait du faux OFF, colonnes dans un autre ordre et une colonne en trop."""
    raw = tmp_path / "raw.parquet"
    extract.extract(off_parquet, raw)
    df = _read(raw)
    flat = tmp_path / "flat.parquet"
    df[list(reversed(extract.COLUMNS))].assign(extra=1).to_parquet(flat, index=False)
    return flat


def test_source_format_recognizes_both_shapes(off_parquet, flat_parquet):
    with duckdb.connect() as con:
        assert extract.source_format(con, off_parquet) == extract.NESTED
        assert extract.source_format(con, flat_parquet) == extract.FLAT


def test_flat_source_is_copied_with_reference_columns(flat_parquet, tmp_path):
    """Une source aplatie est recopiée telle quelle, colonnes remises dans l'ordre de COLUMNS, colonne en trop ignorée."""
    out = tmp_path / "copy.parquet"
    assert extract.extract(flat_parquet, out) == 3
    df = _read(out)
    assert list(df.columns) == extract.COLUMNS
    assert "0123456789012" in set(df["code"])


def test_flat_source_refuses_a_country_filter(flat_parquet, tmp_path):
    with pytest.raises(ValueError, match="déjà aplatie"):
        extract.extract(flat_parquet, tmp_path / "x.parquet", extract.FRANCE_TAG)


def test_unknown_source_shape_is_refused(tmp_path):
    source = tmp_path / "autre.parquet"
    pd.DataFrame({"code": ["1"]}).to_parquet(source)
    with pytest.raises(ValueError, match="ni imbriquée"):
        extract.extract(source, tmp_path / "x.parquet")


def test_manifest_describes_source_and_output(off_parquet, tmp_path):
    out = tmp_path / "fr.parquet"
    extract.extract(off_parquet, out, extract.FRANCE_TAG)
    manifest = json.loads(extract.manifest_path(out).read_text(encoding="utf-8"))
    assert manifest["source_sha256"] == hashlib.sha256(off_parquet.read_bytes()).hexdigest()
    assert manifest["sha256"] == hashlib.sha256(out.read_bytes()).hexdigest()
    assert (manifest["rows"], manifest["country"], manifest["source_format"]) == (2, extract.FRANCE_TAG, extract.NESTED)
    assert "written_at" in manifest and "ODbL" in manifest["license"]


def test_replay_writes_the_same_bytes(off_parquet, tmp_path):
    """Relancer sur la même source réécrit le même brut, octet pour octet (l'horodatage est dans le manifeste)."""
    out = tmp_path / "raw.parquet"
    extract.extract(off_parquet, out)
    first = out.read_bytes()
    extract.extract(off_parquet, out)
    assert out.read_bytes() == first
    assert sorted(p.name for p in tmp_path.iterdir()) == ["food.parquet", "raw.manifest.json", "raw.parquet"]