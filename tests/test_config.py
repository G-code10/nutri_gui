"""Tests de src/config.py : chemins cohérents, ancrés à la racine du dépôt, constantes attendues."""

from pathlib import Path

from src import config

PATHS = [
    config.DATA_DIR, config.FOOD_PARQUET, config.RAW_DIR, config.RAW_PATH, config.FRANCE_EXTRACT_PATH,
    config.SAMPLE_RAW_PATH, config.CLEAN_PATH, config.PARQUET_DIR, config.PRODUCTS_PARQUET_DIR,
    config.EXPORTS_DIR, config.CLEANING_REPORT_PATH,
]


def test_root_is_the_repository():
    """ROOT est le dossier qui contient src/ et ce fichier de configuration."""
    assert (config.ROOT / "src" / "config.py").exists()


def test_root_does_not_depend_on_current_directory(monkeypatch, tmp_path):
    """Changer de dossier courant ne change pas les chemins (ils sont résolus depuis le fichier)."""
    monkeypatch.chdir(tmp_path)
    assert config.ROOT == Path(config.__file__).resolve().parent.parent


def test_paths_are_absolute_and_inside_root():
    """Tous les chemins sont absolus et sous la racine du dépôt : aucun chemin d'un poste particulier."""
    for path in PATHS:
        assert path.is_absolute()
        assert path.is_relative_to(config.ROOT)


def test_data_paths_are_under_data_dir():
    """Toutes les données vivent sous data/ (dossier ignoré par Git)."""
    for path in PATHS:
        if path != config.CLEANING_REPORT_PATH:
            assert path == config.DATA_DIR or path.is_relative_to(config.DATA_DIR)


def test_parquet_files_have_parquet_suffix():
    """Les fichiers de données portent l'extension .parquet."""
    for path in (config.FOOD_PARQUET, config.RAW_PATH, config.FRANCE_EXTRACT_PATH,
                 config.SAMPLE_RAW_PATH, config.CLEAN_PATH):
        assert path.suffix == ".parquet"


def test_shared_constants():
    """Constantes partagées : rayon inconnu, compression, table brute, licence ODbL."""
    assert config.UNKNOWN_AISLE == "unknown"
    assert config.COMPRESSION == "zstd"
    assert config.RAW_TABLE == "products_nutrition"
    assert "ODbL" in config.LICENSE and "Open Food Facts" in config.LICENSE