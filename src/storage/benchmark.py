"""Benchmark honnête (TP 12, étape 3) : trois requêtes types, trois moteurs, temps et mémoire.

Requêtes (choisies d'après l'énoncé du TP 10, voir docs/journal.md) :
    profil_rayon        profil médian par rayon (sucres, sel, kcal), rayon unknown exclu
    boissons_sucrees    les 20 boissons les plus sucrées (filtre sur un rayon, puis tri)
    completude_marques  complétude par marque (au moins 20 produits), top 20 par effectif

Moteurs :
    pandas       pandas sur le Parquet nettoyé (colonnes utiles seulement, lecture comprise)
    postgres     la base PostgreSQL, avec ses index existants (aucun ajouté pour l'occasion)
    duckdb       DuckDB sur le Parquet partitionné par rayon
    duckdb_flat  DuckDB sur le Parquet nettoyé, non partitionné (bonus : effet du partitionnement)

Méthode : chaque mesure tourne dans un sous-processus neuf (python -m src.storage.benchmark --one <moteur>
<requête>), qui renvoie en JSON le temps (lecture + requête), le pic mémoire du processus et le résultat.
Trois répétitions : médiane des temps, maximum des pics. Une mesure « imports » donne le poids de
l'interpréteur et des bibliothèques. Avant de chronométrer, les moteurs doivent rendre le même nombre de
lignes et la même première ligne, sinon le benchmark s'arrête.

Ce module n'importe au chargement que la bibliothèque standard et src.config : un sous-processus ne charge
que les bibliothèques de son moteur, et la mémoire mesurée est la sienne.

Sortie : docs/data/benchmark_mesures.md (généré). L'interprétation va dans docs/data/benchmark.md, rédigé à la main.

Usage (depuis la racine du dépôt) :
    python -m src.storage.benchmark                  # quatre moteurs, trois répétitions
    python -m src.storage.benchmark --no-db          # sans PostgreSQL
    python -m src.storage.benchmark --repeat 5

Données : © Open Food Facts contributors — ODbL.
"""

import argparse
import datetime
import importlib
import json
import math
import numbers
import os
import platform
import statistics
import subprocess
import sys
import time
from importlib import metadata
from pathlib import Path

from src import config

DEFAULT_OUTPUT = config.ROOT / "docs" / "data" / "benchmark_mesures.md"
DB_ENV = "NUTRISCOPE_BENCHMARK_DB"   # paramètres de connexion (JSON) transmis aux sous-processus PostgreSQL
REFERENCE_ENGINE = "duckdb"          # moteur auquel les autres résultats sont comparés
BASELINE = "imports"                 # pseudo-requête : imports seulement

BEVERAGES_TAG = "en:beverages"       # rayon de la requête 2 (tag d'origine)...
BEVERAGES_AISLE = "en-beverages"     # ... et son slug, nom de la partition Parquet
TOP = 20
MIN_PRODUCTS_PER_BRAND = 20          # seuil du TP 10 (completude_par_groupe, min_n=20)
KEY_NUTRIENTS = [
    "energy_kcal_100g", "fat_100g", "saturated_fat_100g", "carbohydrates_100g",
    "sugars_100g", "proteins_100g", "salt_100g",
]

# Les trois supports de données (mêmes produits, trois formes)
CLEAN_SUPPORT = "Parquet nettoyé, non partitionné"
DATABASE_SUPPORT = "Base PostgreSQL"
PARTITIONED_SUPPORT = "Parquet partitionné par rayon"

# Moteur : (outil qui calcule, support qu'il lit). Deux moteurs lisent le même Parquet nettoyé.
ENGINES = {
    "pandas": ("pandas", CLEAN_SUPPORT),
    "postgres": ("PostgreSQL", DATABASE_SUPPORT),
    "duckdb": ("DuckDB", PARTITIONED_SUPPORT),
    "duckdb_flat": ("DuckDB", CLEAN_SUPPORT),
}
QUERIES = {
    "profil_rayon": "Profil médian par rayon",
    "boissons_sucrees": f"{TOP} boissons les plus sucrées",
    "completude_marques": f"Complétude par marque (≥ {MIN_PRODUCTS_PER_BRAND} produits, top {TOP})",
}
# Ce que fait chaque requête, en une ligne, et l'étape du TP 10 dont elle vient
QUERY_DESCRIPTIONS = {
    "profil_rayon": (
        "par rayon : nombre de produits et médianes des sucres, du sel et des kcal ; rayon unknown exclu",
        "agrégat sur tous les produits", "TP 10, étape 1 (profil par rayon)",
    ),
    "boissons_sucrees": (
        f"les {TOP} produits du rayon boissons les plus sucrés, du plus sucré au moins sucré",
        "filtre sur un rayon, puis tri", "TP 10, étape 4 (valeurs extrêmes)",
    ),
    "completude_marques": (
        (f"par marque d'au moins {MIN_PRODUCTS_PER_BRAND} produits : % de Nutri-Score renseigné et % des sept "
         f"nutriments présents ; les {TOP} plus grosses marques"),
        "agrégat à forte cardinalité (une ligne par marque)", "TP 10, étape 2 (complétude par marque)",
    ),
}

# Bibliothèques chargées par chaque moteur avant le chronomètre (comptées dans la mémoire, pas dans le temps)
ENGINE_IMPORTS = {
    "pandas": ("pandas", "pyarrow", "src.utils"),
    "postgres": ("psycopg",),
    "duckdb": ("duckdb", "src.utils"),
    "duckdb_flat": ("duckdb", "src.utils"),
}

# Étapes du journal des durées qui construisent chaque support, et leur libellé dans le rapport
BUILD_STEPS = {
    CLEAN_SUPPORT: ([config.STEP_READ, config.STEP_CLEAN, config.STEP_WRITE_CLEAN], "lecture + nettoyage + écriture"),
    DATABASE_SUPPORT: ([config.STEP_DB_SCHEMA, config.STEP_DB_LOAD], "schéma + chargement"),
    PARTITIONED_SUPPORT: ([config.STEP_CONVERT], "conversion"),
}


def _all_present(prefix: str = "") -> str:
    """Condition SQL « les sept nutriments clés sont présents », colonnes éventuellement préfixées (n.)."""
    return " AND ".join(f"{prefix}{column} IS NOT NULL" for column in KEY_NUTRIENTS)


# DuckDB : {source} = read_parquet(...) ; {known} et {beverages} = filtres propres au support
DUCKDB_SQL = {
    "profil_rayon": """
        SELECT food_groups_tag_1 AS rayon, count(*) AS produits,
               median(sugars_100g) AS sucres_median, median(salt_100g) AS sel_median,
               median(energy_kcal_100g) AS kcal_median
        FROM {source} WHERE {known}
        GROUP BY food_groups_tag_1 ORDER BY rayon""",
    "boissons_sucrees": f"""
        SELECT code, product_name, sugars_100g
        FROM {{source}} WHERE {{beverages}} AND sugars_100g IS NOT NULL
        ORDER BY sugars_100g DESC, code LIMIT {TOP}""",
    "completude_marques": f"""
        SELECT brands AS marque, count(*) AS produits,
               100.0 * count(*) FILTER (WHERE nutriscore_grade IS NOT NULL) / count(*) AS nutriscore_pct,
               100.0 * count(*) FILTER (WHERE {_all_present()}) / count(*) AS sept_nutriments_pct
        FROM {{source}} WHERE brands IS NOT NULL
        GROUP BY brands HAVING count(*) >= {MIN_PRODUCTS_PER_BRAND}
        ORDER BY produits DESC, marque LIMIT {TOP}""",
}

# PostgreSQL : schéma normalisé, jointures ; COLLATE "C" = ordre binaire, comme DuckDB et pandas
POSTGRES_SQL = {
    "profil_rayon": f"""
        SELECT p.aisle_code AS rayon, count(*) AS produits,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY n.sugars_100g) AS sucres_median,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY n.salt_100g) AS sel_median,
               percentile_cont(0.5) WITHIN GROUP (ORDER BY n.energy_kcal_100g) AS kcal_median
        FROM products p JOIN nutrients n ON n.code = p.code
        WHERE p.aisle_code <> '{config.UNKNOWN_AISLE}'
        GROUP BY p.aisle_code ORDER BY p.aisle_code COLLATE "C"
    """,
    "boissons_sucrees": f"""
        SELECT p.code, p.product_name, n.sugars_100g
        FROM products p JOIN nutrients n ON n.code = p.code
        WHERE p.aisle_code = '{BEVERAGES_TAG}' AND n.sugars_100g IS NOT NULL
        ORDER BY n.sugars_100g DESC, p.code COLLATE "C" LIMIT {TOP}""",
    "completude_marques": f"""
        SELECT b.name AS marque, count(*) AS produits,
               CAST(100.0 * count(*) FILTER (WHERE p.nutriscore_grade IS NOT NULL) / count(*) AS DOUBLE PRECISION)
                   AS nutriscore_pct,
               CAST(100.0 * count(*) FILTER (WHERE {_all_present("n.")}) / count(*) AS DOUBLE PRECISION)
                   AS sept_nutriments_pct
        FROM products p JOIN brands b ON b.brand_id = p.brand_id JOIN nutrients n ON n.code = p.code
        GROUP BY b.name HAVING count(*) >= {MIN_PRODUCTS_PER_BRAND}
        ORDER BY produits DESC, b.name COLLATE "C" LIMIT {TOP}""",
}

# pandas : colonnes lues pour chaque requête (lecture limitée aux colonnes utiles)
PANDAS_COLUMNS = {
    "profil_rayon": ["food_groups_tag_1", "sugars_100g", "salt_100g", "energy_kcal_100g"],
    "boissons_sucrees": ["code", "product_name", "food_groups_tag_1", "sugars_100g"],
    "completude_marques": ["brands", "nutriscore_grade", *KEY_NUTRIENTS],
}


# =====================================================================
# Côté sous-processus : une mesure
# =====================================================================
def _query_pandas(query: str, clean_path: Path, parquet_dir: Path) -> list[tuple]:
    """Requête en pandas sur le Parquet nettoyé : lecture des colonnes utiles, puis calcul."""
    import pandas as pd

    from src.utils import aisle_code

    df = pd.read_parquet(clean_path, columns=PANDAS_COLUMNS[query])
    if query == "profil_rayon":
        aisle = aisle_code(df["food_groups_tag_1"])
        known = (aisle != config.UNKNOWN_AISLE).to_numpy()
        profile = (
            df.loc[known].assign(rayon=aisle[known])
            .groupby("rayon")
            .agg(produits=("sugars_100g", "size"), sucres_median=("sugars_100g", "median"),
                 sel_median=("salt_100g", "median"), kcal_median=("energy_kcal_100g", "median"))
            .sort_index()
        )
        return list(profile.itertuples(name=None))
    if query == "boissons_sucrees":
        beverages = df["food_groups_tag_1"].eq(BEVERAGES_TAG).fillna(False) & df["sugars_100g"].notna()
        top = df.loc[beverages.to_numpy()].sort_values(["sugars_100g", "code"], ascending=[False, True]).head(TOP)
        return list(top[["code", "product_name", "sugars_100g"]].itertuples(index=False, name=None))
    if query == "completude_marques":
        branded = df.loc[df["brands"].notna().to_numpy()]
        by_brand = (
            branded.assign(note=branded["nutriscore_grade"].notna(), complet=branded[KEY_NUTRIENTS].notna().all(axis=1))
            .groupby("brands")
            .agg(produits=("note", "size"), nutriscore_pct=("note", "mean"), sept_nutriments_pct=("complet", "mean"))
            .reset_index()
        )
        by_brand = by_brand.loc[by_brand["produits"] >= MIN_PRODUCTS_PER_BRAND]
        by_brand[["nutriscore_pct", "sept_nutriments_pct"]] *= 100
        top = by_brand.sort_values(["produits", "brands"], ascending=[False, True]).head(TOP)
        return list(top.itertuples(index=False, name=None))
    raise ValueError(f"Requête inconnue : {query}")


def _duckdb_sql(query: str, source: str, partitioned: bool) -> str:
    """Requête DuckDB pour un support : partitionné (filtres sur aisle, élagage des partitions) ou non."""
    if partitioned:
        known, beverages = f"aisle <> '{config.UNKNOWN_AISLE}'", f"aisle = '{BEVERAGES_AISLE}'"
    else:
        known, beverages = "nullif(food_groups_tag_1, '') IS NOT NULL", f"food_groups_tag_1 = '{BEVERAGES_TAG}'"
    return DUCKDB_SQL[query].format(source=source, known=known, beverages=beverages)


def _query_duckdb(query: str, clean_path: Path, parquet_dir: Path, partitioned: bool = True) -> list[tuple]:
    """Requête en DuckDB, sur le Parquet partitionné ou sur le Parquet nettoyé."""
    import duckdb

    from src.utils import sql_literal

    if partitioned:
        source = f"read_parquet({sql_literal((Path(parquet_dir) / '**' / '*.parquet').as_posix())}, hive_partitioning = true)"
    else:
        source = f"read_parquet({sql_literal(Path(clean_path).as_posix())})"
    with duckdb.connect() as con:
        return con.execute(_duckdb_sql(query, source, partitioned)).fetchall()


def _query_postgres(query: str, clean_path: Path, parquet_dir: Path) -> list[tuple]:
    """Requête sur la base, avec les paramètres de connexion reçus du processus parent (variable DB_ENV)."""
    import psycopg

    with psycopg.connect(**json.loads(os.environ[DB_ENV])) as conn:
        return conn.execute(POSTGRES_SQL[query]).fetchall()


QUERY_FUNCTIONS = {
    "pandas": _query_pandas,
    "postgres": _query_postgres,
    "duckdb": _query_duckdb,
    "duckdb_flat": lambda query, clean, parquet: _query_duckdb(query, clean, parquet, partitioned=False),
}


def run_query(engine: str, query: str, clean_path: Path, parquet_dir: Path) -> list[tuple]:
    """Exécute une requête avec un moteur et renvoie ses lignes (sans chronomètre)."""
    return QUERY_FUNCTIONS[engine](query, Path(clean_path), Path(parquet_dir))


def peak_memory_bytes() -> int | None:
    """Pic de mémoire résidente du processus courant, en octets ; None si aucune mesure n'est possible.

    Windows : psutil (peak_wset), le module resource n'y existe pas.
    Linux : VmHWM de /proc/self/status. ru_maxrss n'y convient pas pour un sous-processus : il garde le pic
    du processus parent au moment du lancement, et tous les moteurs afficheraient le même chiffre.
    macOS : resource.getrusage (ru_maxrss, en octets).
    """
    if sys.platform == "win32":
        import psutil

        return int(psutil.Process().memory_info().peak_wset)
    status = Path("/proc/self/status")
    if status.exists():
        for line in status.read_text(encoding="utf-8").splitlines():
            if line.startswith("VmHWM:"):
                return int(line.split()[1]) * 1024   # valeur en kilo-octets
    try:
        import resource
    except ImportError:
        return None
    return int(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)


def _jsonable(value):
    """Valeur transmissible en JSON : manquant (None, NaN, pd.NA) -> None, entier -> int, nombre -> float."""
    if value is None or type(value).__name__ == "NAType":
        return None
    if isinstance(value, (bool, str)):
        return value
    if isinstance(value, numbers.Integral):
        return int(value)
    try:
        number = float(value)
    except (TypeError, ValueError):
        return str(value)
    return None if math.isnan(number) else number


def measure(engine: str, query: str, clean_path: Path, parquet_dir: Path) -> dict:
    """Une mesure, dans le processus courant : imports, puis lecture + requête chronométrées, puis pic mémoire."""
    started = time.perf_counter()
    for module in ENGINE_IMPORTS[engine]:
        importlib.import_module(module)
    import_seconds = time.perf_counter() - started

    rows: list[tuple] = []
    seconds = import_seconds
    if query != BASELINE:
        started = time.perf_counter()
        rows = run_query(engine, query, clean_path, parquet_dir)
        seconds = time.perf_counter() - started
    return {
        "engine": engine,
        "query": query,
        "seconds": seconds,
        "import_seconds": import_seconds,
        "peak_bytes": peak_memory_bytes(),
        "rows": len(rows),
        "first": [_jsonable(value) for value in rows[0]] if rows else None,
    }


# =====================================================================
# Côté processus parent : orchestration
# =====================================================================
def spawn(engine: str, query: str, clean_path: Path, parquet_dir: Path, env: dict | None = None) -> dict:
    """Une mesure dans un sous-processus neuf ; renvoie le JSON qu'il imprime sur sa dernière ligne."""
    command = [
        sys.executable, "-m", "src.storage.benchmark", "--one", engine, query,
        "--clean", str(clean_path), "--parquet", str(parquet_dir),
    ]
    completed = subprocess.run(
        command, cwd=config.ROOT, env=env or os.environ.copy(), capture_output=True, text=True, encoding="utf-8",
        check=False,   # code de retour vérifié ci-dessous, pour joindre le message d'erreur du sous-processus
    )
    if completed.returncode != 0:
        raise RuntimeError(f"Mesure {engine} / {query} en échec :\n{completed.stderr.strip()}")
    return json.loads(completed.stdout.strip().splitlines()[-1])


def _same_value(left, right) -> bool:
    """Même valeur à 1e-9 près pour les nombres, égalité stricte sinon."""
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float)) and isinstance(right, (int, float)):
        return math.isclose(left, right, rel_tol=1e-9, abs_tol=1e-9)
    return left == right


def same_result(first: dict, second: dict) -> bool:
    """Deux mesures rendent-elles le même nombre de lignes et la même première ligne ?"""
    if first["rows"] != second["rows"]:
        return False
    if first["first"] is None or second["first"] is None:
        return first["first"] is second["first"]
    return len(first["first"]) == len(second["first"]) and all(map(_same_value, first["first"], second["first"]))


def verify(results: dict[str, dict[str, dict]]) -> None:
    """Lève RuntimeError si un moteur ne rend pas le même résultat que le moteur de référence."""
    for query, by_engine in results.items():
        reference = by_engine[REFERENCE_ENGINE]
        for engine, result in by_engine.items():
            if not same_result(reference, result):
                raise RuntimeError(
                    f"Résultats différents pour {query} : {REFERENCE_ENGINE} {reference['rows']} lignes, "
                    f"première {reference['first']} ; {engine} {result['rows']} lignes, première {result['first']}. "
                    "Les supports ne partent pas du même nettoyé, ou une requête diffère."
                )


def summarize(measures: list[dict]) -> dict:
    """Médiane des temps, maximum des pics (None si un pic manque), nombre de lignes."""
    peaks = [measure_["peak_bytes"] for measure_ in measures]
    return {
        "seconds": statistics.median(measure_["seconds"] for measure_ in measures),
        "peak_bytes": None if None in peaks else max(peaks),
        "rows": measures[0]["rows"],
        "repeat": len(measures),
    }


def read_durations(path: Path | None = None) -> list[dict]:
    """Entrées du journal des durées (liste vide si le journal n'existe pas)."""
    path = Path(config.DURATIONS_LOG_PATH if path is None else path)
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def build_costs(entries: list[dict]) -> list[dict]:
    """Coût de construction de chaque support : somme de la dernière entrée de chacune de ses étapes.

    Renvoie {support, seconds, sources, missing} ; seconds vaut None si une étape n'a jamais été journalisée.
    """
    latest = {entry["step"]: entry for entry in entries if entry.get("status") == "ok"}
    costs = []
    for support, (steps, _) in BUILD_STEPS.items():
        missing = [step for step in steps if step not in latest]
        found = [latest[step] for step in steps if step in latest]
        costs.append({
            "support": support,
            "seconds": None if missing else sum(entry["seconds"] for entry in found),
            "sources": sorted({entry["source"] for entry in found}),
            "missing": missing,
        })
    return costs


def machine_info() -> dict[str, str]:
    """Machine et versions : système, processeur, cœurs, mémoire, Python et bibliothèques."""
    try:
        import psutil

        memory = f"{psutil.virtual_memory().total / 1e9:.1f} Go"
    except ImportError:
        memory = "non disponible (psutil absent)"
    info = {
        "Système": platform.platform(),
        "Processeur": platform.processor() or platform.machine(),
        "Cœurs logiques": str(os.cpu_count()),
        "Mémoire": memory,
        "Python": platform.python_version(),
    }
    for package in ("pandas", "pyarrow", "duckdb", "psycopg", "psutil"):
        try:
            info[package] = metadata.version(package)
        except metadata.PackageNotFoundError:
            info[package] = "non installé"
    return info


def engine_label(engine: str) -> str:
    """Libellé complet d'un moteur : « DuckDB sur Parquet partitionné par rayon »."""
    tool, support = ENGINES[engine]
    return f"{tool} sur {support}"


def _milliseconds(seconds: float | None) -> str:
    """Durée en millisecondes, entière (« < 1 » en dessous d'une milliseconde)."""
    from src.utils import format_int

    if seconds is None:
        return "—"
    return "< 1" if seconds < 0.001 else format_int(round(seconds * 1000))


def _megabytes(value: int | None) -> str:
    """Octets en Mo (10^6 octets), arrondis à l'unité."""
    from src.utils import format_int

    return "non disponible" if value is None else format_int(round(value / 1e6))


def _net_megabytes(peak: int | None, baseline: int | None) -> str:
    """Mémoire due à la requête : pic de la mesure moins pic des imports seuls du même moteur."""
    return "non disponible" if peak is None or baseline is None else _megabytes(max(peak - baseline, 0))


def _readers(support: str) -> str:
    """Outils qui lisent un support : « pandas et DuckDB »."""
    tools = [tool for tool, read in ENGINES.values() if read == support]
    return " et ".join(dict.fromkeys(tools))


def build_markdown(context: dict, date: str | None = None) -> str:
    """Texte de docs/data/benchmark_mesures.md. La date est la seule donnée variable hors mesures."""
    from src.utils import format_int, markdown_table

    date = date or datetime.date.today().isoformat()
    results, baseline, checks = context["results"], context["baseline"], context["checks"]

    header = (
        "# Benchmark : mesures\n\n"
        f"- Date : {date}\n- Données : {format_int(context['rows'])} produits (`{context['clean']}`) ; "
        f"{config.LICENSE}\n"
        f"- Répétitions par mesure : {context['repeat']}\n"
        "- Généré par `python -m src.storage.benchmark` : ne pas modifier à la main. "
        "La lecture des résultats est rédigée dans `docs/data/benchmark.md`."
    )
    sections = [header]

    sections.append(
        "## Ce que mesure ce rapport\n\n"
        "Les mêmes produits existent sous trois formes (les **supports**) : un Parquet nettoyé d'un seul tenant, "
        "la base PostgreSQL, un Parquet partitionné par rayon. Pour trois requêtes que l'analyse fera vraiment, "
        "le rapport mesure ce que coûte chaque **moteur** (un outil qui lit un support) : le temps pour lire les "
        "données et calculer le résultat, et la mémoire du processus. Il donne aussi ce qu'a coûté la construction "
        "de chaque support.\n\n"
        "Comment lire les tableaux :\n\n"
        "- **Temps médian** : lecture + calcul, en millisecondes, médiane des répétitions.\n"
        "- **× le plus rapide** : temps du moteur divisé par celui du plus rapide sur la même requête "
        "(1,0 = le plus rapide ; 3,0 = trois fois plus lent).\n"
        "- **Pic mémoire** : mémoire maximale du processus, bibliothèques comprises.\n"
        "- **Dont requête** : pic mémoire moins celui du même moteur quand il ne fait que charger ses bibliothèques."
    )

    rows = [[QUERIES[query], *QUERY_DESCRIPTIONS[query]] for query in results]
    sections.append("## Les requêtes\n\n" + markdown_table(["Requête", "Ce qu'elle calcule", "Type", "Origine"], rows))

    parts = ["## Résultats"]
    for number, (query, by_engine) in enumerate(results.items(), start=1):
        fastest = min(result["seconds"] for result in by_engine.values())
        rows = []
        for engine, result in by_engine.items():
            tool, support = ENGINES[engine]
            ratio = result["seconds"] / fastest if fastest else float("nan")
            rows.append([
                tool, support, _milliseconds(result["seconds"]), f"{ratio:.1f}".replace(".", ","),
                _megabytes(result["peak_bytes"]),
                _net_megabytes(result["peak_bytes"], baseline[engine]["peak_bytes"]),
                format_int(result["rows"]),
            ])
        parts.append(f"### {number}. {QUERIES[query]}\n\n" + markdown_table(
            ["Moteur", "Support", "Temps médian (ms)", "× le plus rapide", "Pic mémoire (Mo)",
             "Dont requête (Mo)", "Lignes"], rows,
        ))
    sections.append("\n\n".join(parts))

    rows = []
    for cost in context["costs"]:
        if cost["seconds"] is None:
            value = f"non mesuré (absent du journal : {', '.join(cost['missing'])})"
        else:
            value = f"{cost['seconds']:.1f}".replace(".", ",")
        sources = ", ".join(f"`{source}`" for source in cost["sources"]) or "—"
        rows.append([cost["support"], _readers(cost["support"]), BUILD_STEPS[cost["support"]][1], value, sources])
    sections.append(
        "## Coût de construction des supports\n\n"
        f"Payé une fois, à chaque exécution du pipeline. Dernière durée de chaque étape dans `{context['durations']}`.\n\n"
        + markdown_table(["Support", "Lu par", "Étapes", "Durée (s)", "Construit à partir de"], rows)
    )

    rows = [[*ENGINES[engine], _milliseconds(result["seconds"]), _megabytes(result["peak_bytes"])]
            for engine, result in baseline.items()]
    sections.append(
        "## Référence : imports seulement\n\n"
        "Ce que coûte le seul chargement des bibliothèques de chaque moteur, sans lire de données.\n\n"
        + markdown_table(["Moteur", "Support", "Imports (ms)", "Pic mémoire (Mo)"], rows)
    )

    rows = []
    for query, by_engine in checks.items():
        lines = format_int(next(iter(by_engine.values()))["rows"])
        rows.append([QUERIES[query], f"{lines} pour chacun des {len(by_engine)} moteurs", "✓"])
    sections.append(
        "## Vérification avant chronomètre\n\n"
        f"Chaque moteur doit rendre le même nombre de lignes et la même première ligne que {engine_label(REFERENCE_ENGINE)}, "
        "sinon le benchmark s'arrête.\n\n"
        + markdown_table(["Requête", "Lignes", "Même première ligne"], rows)
    )

    sections.append(
        "## Méthode : ce que « honnête » veut dire ici\n\n"
        "- Chaque mesure tourne dans un **sous-processus Python neuf** : aucun cache Python partagé entre moteurs.\n"
        "- **Temps = lecture + calcul** (connexion comprise pour PostgreSQL), imports exclus ; "
        "**médiane** des répétitions.\n"
        "- **Mémoire = pic du processus** (imports compris), **maximum** des répétitions : "
        "`psutil` (`peak_wset`) sous Windows, `VmHWM` de `/proc/self/status` sous Linux "
        "(`ru_maxrss` y garderait le pic du processus parent), `resource` sous macOS.\n"
        "- **Mêmes résultats vérifiés avant le chronomètre** (section précédente).\n"
        "- **pandas lit seulement les colonnes utiles** à chaque requête, comme DuckDB.\n"
        "- **PostgreSQL garde ses index existants** (rayon, marque, grade), aucun n'est ajouté pour l'occasion.\n"
        "- Limite : pour PostgreSQL, le pic mémoire est celui du **client** Python ; le serveur calcule dans ses "
        "propres processus, non mesurés ici.\n"
        "- Limite : les caches du système de fichiers et de PostgreSQL restent chauds d'une mesure à l'autre "
        "(une passe de vérification précède les mesures) ; tous les moteurs en profitent de la même façon."
    )

    sections.append("## Machine et versions\n\n" + markdown_table(
        ["", "Valeur"], [[key, value] for key, value in context["machine"].items()]
    ))
    return "\n\n".join(sections) + "\n"


def run(
    clean_path: Path = config.CLEAN_PATH,
    parquet_dir: Path = config.PRODUCTS_PARQUET_DIR,
    output: Path = DEFAULT_OUTPUT,
    conf: dict | None = None,
    use_db: bool = True,
    repeat: int = 3,
    engines: list[str] | None = None,
    durations_path: Path | None = None,
) -> dict:
    """Vérifie, mesure, écrit le rapport ; renvoie le contexte du rapport (mesures résumées comprises)."""
    import duckdb

    from src.storage.convert_parquet import SUCCESS_MARKER
    from src.utils import display_path, sql_literal

    clean_path, parquet_dir = Path(clean_path), Path(parquet_dir)
    if not clean_path.exists():
        raise FileNotFoundError(f"Nettoyé introuvable : {clean_path} (lancer python -m src.pipeline)")
    if not (parquet_dir / SUCCESS_MARKER).exists():
        raise FileNotFoundError(f"{parquet_dir} incomplet (lancer python -m src.storage.convert_parquet)")

    engines = list(engines or ENGINES)
    if not use_db and "postgres" in engines:
        engines.remove("postgres")
    if REFERENCE_ENGINE not in engines:
        engines.insert(0, REFERENCE_ENGINE)

    env = os.environ.copy()
    machine = machine_info()
    if "postgres" in engines:
        from src import load_db

        params = load_db.connection_params(conf)
        env[DB_ENV] = json.dumps(params)
        with load_db.connect(conf) as conn:
            machine["Serveur PostgreSQL"] = conn.execute("SHOW server_version").fetchone()[0]

    checks = {query: {engine: spawn(engine, query, clean_path, parquet_dir, env) for engine in engines}
              for query in QUERIES}
    verify(checks)

    baseline = {engine: summarize([spawn(engine, BASELINE, clean_path, parquet_dir, env) for _ in range(repeat)])
                for engine in engines}
    results = {
        query: {engine: summarize([spawn(engine, query, clean_path, parquet_dir, env) for _ in range(repeat)])
                for engine in engines}
        for query in QUERIES
    }

    rows = duckdb.sql(f"SELECT count(*) FROM read_parquet({sql_literal(clean_path.as_posix())})").fetchone()[0]
    context = {
        "clean": display_path(clean_path), "parquet": display_path(parquet_dir), "rows": rows,
        "repeat": repeat, "machine": machine,
        "durations": display_path(config.DURATIONS_LOG_PATH if durations_path is None else durations_path),
        "costs": build_costs(read_durations(durations_path)),
        "checks": checks, "baseline": baseline, "results": results,
    }
    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(context), encoding="utf-8", newline="\n")
    context["output"] = output
    return context


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Benchmark : trois requêtes, trois moteurs, temps et mémoire.")
    parser.add_argument("--one", nargs=2, metavar=("MOTEUR", "REQUÊTE"), help="une seule mesure (sous-processus)")
    parser.add_argument("--clean", type=Path, default=config.CLEAN_PATH, help="Parquet nettoyé")
    parser.add_argument("--parquet", type=Path, default=config.PRODUCTS_PARQUET_DIR, help="Parquet partitionné")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="rapport Markdown des mesures")
    parser.add_argument("--repeat", type=int, default=3, help="répétitions par mesure")
    parser.add_argument("--engines", nargs="+", choices=list(ENGINES), help="moteurs à mesurer (défaut : tous)")
    parser.add_argument("--no-db", action="store_true", help="sans PostgreSQL")
    args = parser.parse_args(argv)

    if args.one:
        engine, query = args.one
        print(json.dumps(measure(engine, query, args.clean, args.parquet), ensure_ascii=False))
        return

    context = run(args.clean, args.parquet, args.out, use_db=not args.no_db, repeat=args.repeat, engines=args.engines)
    for query, by_engine in context["results"].items():
        for engine, result in by_engine.items():
            print(f"{query:<20} {engine_label(engine):<45} {result['seconds'] * 1000:8.0f} ms")
    print(f"Rapport : {context['output']}")


if __name__ == "__main__":
    main()