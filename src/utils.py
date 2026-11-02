"""Fonctions utilitaires partagées par plusieurs modules du dépôt.

Règle d'entrée : une fonction n'arrive ici que si au moins deux modules s'en servent ; sinon elle reste,
privée (_), dans le module qui l'utilise. Les fonctions d'ici sont publiques : elles sont faites pour être importées.
"""

from __future__ import annotations

import datetime
import hashlib
import json
import re
import shutil
from pathlib import Path
from typing import TYPE_CHECKING

from src import config

# pandas n'est importé que par aisle_code : un module qui n'utilise que les autres fonctions (le benchmark,
# qui mesure la mémoire de chaque moteur) ne charge pas pandas sans le savoir.
if TYPE_CHECKING:
    import pandas as pd

DATE_FORMAT = "%Y%m%d"   # format des dates dans les noms de sortie : AAAAMMJJ


def sql_literal(value: str) -> str:
    """Chaîne SQL entre apostrophes, apostrophes internes doublées : « d'O'Neil » devient 'd''O''Neil'.

    À utiliser pour tout texte (chemin, tag, licence) inséré dans une requête DuckDB.
    """
    return "'" + value.replace("'", "''") + "'"


def display_path(path: Path) -> str:
    """Chemin relatif à la racine du dépôt quand c'est possible, sinon le seul nom du fichier.

    Sert dans les rapports et les schémas écrits : ils ne contiennent jamais le chemin absolu d'un poste.
    """
    path = Path(path).resolve()
    return path.relative_to(config.ROOT).as_posix() if path.is_relative_to(config.ROOT) else path.name


def aisle_slug_sql(column: str) -> str:
    """Expression SQL du slug de rayon (DuckDB et PostgreSQL) : « en:fruits-and-vegetables » -> « en-fruits-and-vegetables ».

    NULL, vide ou espaces -> UNKNOWN_AISLE ; minuscules ; toute suite de caractères non alphanumériques -> « - ».
    C'est la clé de partition du Parquet (convert_parquet), recalculée côté base pour comparer (run_queries).
    """
    return (
        f"lower(regexp_replace(coalesce(nullif(trim({column}), ''), "
        f"'{config.UNKNOWN_AISLE}'), '[^A-Za-z0-9]+', '-', 'g'))"
    )


def aisle_code(food_groups_tag_1: pd.Series) -> pd.Series:
    """Rayon de chaque produit : son tag food_groups_tag_1, ou UNKNOWN_AISLE si le tag est NULL ou vide.

    Le tag est gardé tel quel (« en:fruits-and-vegetables ») : c'est le code de rayon de la base.
    Le slug des partitions Parquet (« en-fruits-and-vegetables ») est calculé à part, en SQL : aisle_slug_sql.
    """
    import pandas as pd

    return food_groups_tag_1.astype("string").replace("", pd.NA).fillna(config.UNKNOWN_AISLE)


def duckdb_parquet_options() -> str:
    """Options communes d'un COPY ... TO ... (FORMAT PARQUET, ...) en DuckDB : compression, puis licence en métadonnées.

    Exemple : f"COPY ({query}) TO {sql_literal(path)} (FORMAT PARQUET, {duckdb_parquet_options()})"
    """
    return f"COMPRESSION {config.COMPRESSION.upper()}, KV_METADATA {{license: {sql_literal(config.LICENSE)}}}"


def format_int(number) -> str:
    """Entier avec une espace entre les milliers : 12345 devient « 12 345 »."""
    return f"{int(number):,}".replace(",", " ")


def markdown_table(headers: list[str], rows: list[list]) -> str:
    """Tableau Markdown : une ligne d'en-tête, une ligne de séparation, puis une ligne par élément de `rows`."""
    lines = ["| " + " | ".join(headers) + " |", "|" + "|".join(" --- " for _ in headers) + "|"]
    lines += ["| " + " | ".join(str(cell) for cell in row) + " |" for row in rows]
    return "\n".join(lines)


def file_sha256(path: Path) -> str:
    """Empreinte SHA-256 d'un fichier, lu par blocs de 1 Mo (un fichier de plusieurs Go ne passe pas en mémoire)."""
    digest = hashlib.sha256()
    with Path(path).open("rb") as file:
        for block in iter(lambda: file.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def append_duration(
    step: str, seconds: float, rows: int | None, source: str | None, path: Path | None = None,
    status: str = "ok", error: str | None = None,
) -> Path:
    """Ajoute une ligne au journal des durées (JSON Lines) : horodatage, étape, durée, statut, lignes, source, erreur.

    `status` vaut « ok » ou « failed » ; `error` porte le message d'un échec (None sinon). `path` vaut
    config.DURATIONS_LOG_PATH par défaut (lu à l'appel, pas à l'import).
    """
    path = Path(config.DURATIONS_LOG_PATH if path is None else path)
    path.parent.mkdir(parents=True, exist_ok=True)
    entry = {
        "timestamp": datetime.datetime.now().astimezone().isoformat(timespec="seconds"),
        "step": step,
        "seconds": round(seconds, 3),
        "status": status,
        "rows": rows,
        "source": source,
        "error": error,
    }
    with path.open("a", encoding="utf-8", newline="\n") as log:
        log.write(json.dumps(entry, ensure_ascii=False) + "\n")
    return path


# --- Sorties datées : <préfixe>_<AAAAMMJJ><suffixe> ---
def today() -> datetime.date:
    """Date du jour, en heure locale (celle de la machine qui lance le pipeline)."""
    return datetime.datetime.now().astimezone().date()


def parse_day(text: str) -> datetime.date:
    """Date écrite AAAAMMJJ (noms de sortie, option --date) ; lève ValueError si le texte n'est pas une date valide."""
    if len(text) != 8 or not text.isdigit():
        raise ValueError(f"date attendue au format AAAAMMJJ : {text}")
    return datetime.date.fromisoformat(text)


def dated_path(directory: Path, prefix: str, day: datetime.date, suffix: str = "") -> Path:
    """Chemin daté : dated_path(data/clean, "products_clean", 2 nov. 2026, ".parquet") -> data/clean/products_clean_20261102.parquet."""
    return Path(directory) / f"{prefix}_{day.strftime(DATE_FORMAT)}{suffix}"


def _version_pattern(prefix: str) -> re.Pattern:
    """Nom d'une version datée et de ses fichiers voisins : <préfixe>_<AAAAMMJJ>, suivi ou non d'extensions."""
    return re.compile(rf"^{re.escape(prefix)}_(\d{{8}})(\..+)?$")


def dated_versions(directory: Path, prefix: str) -> dict[datetime.date, list[Path]]:
    """Versions datées présentes dans `directory` : {date: [fichiers et dossiers de cette date]}, dates croissantes.

    Un nom dont la date est invalide (20261399) est ignoré. Dossier absent : aucune version.
    """
    directory = Path(directory)
    if not directory.is_dir():
        return {}
    pattern = _version_pattern(prefix)
    versions: dict[datetime.date, list[Path]] = {}
    for entry in sorted(directory.iterdir()):
        match = pattern.match(entry.name)
        if not match:
            continue
        try:
            day = parse_day(match.group(1))
        except ValueError:
            continue
        versions.setdefault(day, []).append(entry)
    return dict(sorted(versions.items()))


def find_input(
    directory: Path, prefix: str, suffix: str = "", day: datetime.date | None = None, require_success: bool = False,
) -> Path | None:
    """Entrée d'une étape : la version datée de `day` (aujourd'hui par défaut), sinon la plus récente avant elle.

    `suffix` désigne le fichier attendu (« .parquet » ; vide pour un dossier). Avec `require_success`, un dossier
    sans marqueur _SUCCESS est incomplet : il est ignoré. Renvoie None si rien ne convient.
    """
    day = day or today()
    candidates = []
    for version_day in dated_versions(directory, prefix):
        path = dated_path(directory, prefix, version_day, suffix)
        if version_day > day or not path.exists():
            continue
        if require_success and not (path / config.SUCCESS_MARKER).exists():
            continue
        candidates.append(path)
    return candidates[-1] if candidates else None


def require_input(
    directory: Path, prefix: str, suffix: str, day: datetime.date | None, hint: str, require_success: bool = False,
) -> Path:
    """Comme find_input, mais lève FileNotFoundError avec un message qui dit quoi lancer avant (`hint`)."""
    found = find_input(directory, prefix, suffix, day, require_success)
    if found is None:
        expected = f"{prefix}_<AAAAMMJJ>{suffix or '/'}"
        complete = f" complet (avec {config.SUCCESS_MARKER})" if require_success else ""
        raise FileNotFoundError(
            f"Aucun {expected}{complete} dans {display_path(directory)} jusqu'au {(day or today()).isoformat()} : "
            f"lancer d'abord {hint}"
        )
    return found


def prune_versions(directory: Path, prefix: str, keep: int = config.KEEP_VERSIONS) -> list[Path]:
    """Supprime les versions datées au-delà des `keep` plus récentes (fichiers voisins compris) ; renvoie ce qui est supprimé.

    À appeler seulement après l'écriture réussie de la nouvelle version : un échec ne fait jamais perdre une
    version valide. keep=0 supprime toutes les versions (commande reset). Jamais utilisé sur les exports.
    """
    versions = dated_versions(directory, prefix)
    old_days = list(versions)[: max(len(versions) - keep, 0)]
    removed = []
    for day in old_days:
        for path in versions[day]:
            if path.is_dir():
                shutil.rmtree(path)
            else:
                path.unlink()
            removed.append(path)
    return removed