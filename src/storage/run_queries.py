"""Les cinq contrôles du TP 12 (étape 2) : sql/controles.sql rejoué en DuckDB sur le Parquet partitionné,
puis sur la base PostgreSQL, pour vérifier que les deux donnent le même résultat.

Le fichier SQL est découpé sur ses marqueurs « -- @nom: <nom> ». Ses requêtes visent une vue `produits`, créée
ici dans chaque moteur avec les mêmes colonnes : le même texte SQL tourne sur les deux. Les $paramètres (tolérances,
bornes) sont remplacés par les constantes de cleaning.py, celles que le nettoyage applique.

Résultat : docs/data/controle.md, avec les vérifications du TP, la concordance Parquet / base et un tableau
par contrôle. Le fichier se régénère à l'identique : la date n'apparaît qu'en en-tête.

Deux fonctions pour le pipeline (nutriscope/pipeline.py), chacune appelée par son étape :
- check_database() : les cinq contrôles sur la base seule, juste après son chargement (étape load_db) ;
- check_parquet_against_database() : les contrôles sur le Parquet, comparés à la base, rapport écrit
  (étape parquet) ; lève RuntimeError si les deux diffèrent.

Usage (depuis la racine du dépôt) :
    python -m src.storage.run_queries            # Parquet le plus récent + base -> docs/data/controle.md
    python -m src.storage.run_queries --no-db    # Parquet seulement (PostgreSQL non lancé)

Données : © Open Food Facts contributors — ODbL.
"""

import argparse
import math
import re
from dataclasses import dataclass
from decimal import Decimal
from pathlib import Path
from string import Template

import duckdb
import psycopg

from src import cleaning, config, load_db
from src.utils import (
    aisle_slug_sql,
    display_path,
    format_int,
    markdown_table,
    require_input,
    sql_literal,
    today,
)

DEFAULT_SQL = config.ROOT / "sql" / "controles.sql"
DEFAULT_OUTPUT = config.CONTROLS_REPORT_PATH
SUCCESS_MARKER = config.SUCCESS_MARKER
CREDIT = f"Données : {config.LICENSE}."

MARKER = re.compile(r"^--\s*@nom:\s*(\w+)\s*$", re.MULTILINE)
SQL_COMMENT = re.compile(r"--[^\n]*")

# Valeurs des $paramètres de controles.sql : les constantes du nettoyage, jamais recopiées
PARAMETERS = {
    "kcal_max": cleaning.KCAL_MAX,
    "sugars_tolerance": cleaning.SUGARS_TOLERANCE,
    "saturated_tolerance": cleaning.SATURATED_TOLERANCE,
    "salt_per_sodium": cleaning.SALT_PER_SODIUM,
    "salt_sodium_tolerance": cleaning.SALT_SODIUM_TOLERANCE,
    "alcohol_group": cleaning.ALCOHOL_GROUP,
}

# Colonnes nutritionnelles de la vue, identiques dans les deux moteurs
_NUTRIENTS = (
    "energy_kcal_100g, fat_100g, saturated_fat_100g, carbohydrates_100g, sugars_100g, fiber_100g, "
    "proteins_100g, salt_100g, sodium_100g, fruits_vegetables_legumes_100g"
)

# Vue `produits` sur le Parquet partitionné (aisle vient du nom des dossiers aisle=<slug>)
DUCKDB_VIEW = f"""
    CREATE OR REPLACE VIEW produits AS
    SELECT code, product_name, brands, food_groups_tag_1 AS aisle_tag, aisle,
           nutriscore_grade, nutriscore_score, grade_not_applicable,
           {_NUTRIENTS},
           coalesce(len(categories_tags), 0) > 0 AS has_categories
    FROM read_parquet({{pattern}}, hive_partitioning = true)
"""

# Même vue sur la base : jointures du schéma normalisé, slug recalculé depuis aisle_code
POSTGRES_VIEW = f"""
    CREATE OR REPLACE TEMP VIEW produits AS
    SELECT p.code, p.product_name, b.name AS brands, p.aisle_code AS aisle_tag,
           {aisle_slug_sql("p.aisle_code")} AS aisle,
           CAST(p.nutriscore_grade AS VARCHAR) AS nutriscore_grade, p.nutriscore_score, p.grade_not_applicable,
           {", ".join(f"n.{column.strip()}" for column in _NUTRIENTS.split(","))},
           EXISTS (SELECT 1 FROM product_categories pc WHERE pc.code = p.code) AS has_categories
    FROM products p
    JOIN nutrients n ON n.code = p.code
    LEFT JOIN brands b ON b.brand_id = p.brand_id
"""

TITLES = {
    "comptage_par_rayon": "1. Comptage par rayon",
    "completude": "2. Complétude par rayon (%)",
    "doublons": "3. Doublons",
    "bornes_coherences": "4. Bornes et cohérences",
    "distribution_nutriscore": "5. Distribution du Nutri-Score",
}
NOTES = {
    "completude": "Catégories : 100 % attendu partout, le nettoyage supprime les produits sans catégorie.",
    "bornes_coherences": (
        "Bornes : 0 attendu. Cohérences : mêmes tolérances que le nettoyage ; les lignes restantes sont listées "
        "ici, pas filtrées : une valeur à corriger revient au nettoyage sous forme de règle."
    ),
    "distribution_nutriscore": (
        "« unknown » et « not-applicable » sont effacés au nettoyage : not-applicable reste visible par le drapeau "
        "grade_not_applicable, unknown est compté dans null. La part d'« unknown » dans le brut figure dans "
        "docs/data/rapport_nettoyage.md (règle normalize_grade)."
    ),
}
GRADES = ["a", "b", "c", "d", "e"]


@dataclass
class QueryResult:
    """Résultat d'une requête : noms de colonnes et lignes."""

    columns: list[str]
    rows: list[tuple]


@dataclass
class ControlRun:
    """Les cinq contrôles exécutés par un moteur, plus la volumétrie totale de la vue."""

    engine: str
    total: int
    results: dict[str, QueryResult]


# --- Lecture du fichier SQL ---
def _sql_value(value) -> str:
    """Valeur d'un $paramètre telle qu'écrite dans le SQL : 0.5 -> « 0.5 », 900.0 -> « 900 »."""
    return f"{value:g}" if isinstance(value, (int, float)) else str(value)


def _label_value(value) -> str:
    """Valeur d'un paramètre dans un texte affiché : virgule décimale, 0.5 -> « 0,5 »."""
    return _sql_value(value).replace(".", ",") if isinstance(value, (int, float)) else str(value)


def _template_values(parameters: dict) -> dict[str, str]:
    """Valeurs de substitution : $<nom> (syntaxe SQL) et, pour les nombres, $<nom>_label (libellés affichés)."""
    values = {name: _sql_value(value) for name, value in parameters.items()}
    values.update({f"{name}_label": _label_value(value) for name, value in parameters.items()
                   if isinstance(value, (int, float))})
    return values


def load_queries(path: Path = DEFAULT_SQL, parameters: dict | None = None) -> dict[str, str]:
    """Requêtes du fichier SQL, {nom: requête}, dans l'ordre du fichier, $paramètres remplacés.

    Un nombre s'écrit $<nom> dans une condition (point décimal) et $<nom>_label dans un libellé (virgule).
    Lève ValueError si du SQL précède le premier marqueur, si aucun marqueur n'existe, si un nom est en double
    ou si une requête est vide ; KeyError si un $paramètre n'a pas de valeur.
    """
    values = _template_values(PARAMETERS if parameters is None else parameters)
    parts = MARKER.split(Path(path).read_text(encoding="utf-8"))
    preamble, pairs = parts[0], parts[1:]
    if SQL_COMMENT.sub("", preamble).strip():
        raise ValueError("Du SQL précède le premier marqueur « -- @nom: » : il ne serait jamais exécuté")
    if not pairs:
        raise ValueError(f"Aucun marqueur « -- @nom: » dans {path}")

    queries: dict[str, str] = {}
    for name, body in zip(pairs[0::2], pairs[1::2]):
        if name in queries:
            raise ValueError(f"Nom de requête en double : {name}")
        query = Template(body).substitute(values).strip()
        if not SQL_COMMENT.sub("", query).strip(" ;\n"):
            raise ValueError(f"Requête vide : {name}")
        queries[name] = query
    return queries


# --- Exécution ---
def _execute(connection, query: str) -> QueryResult:
    """Exécute une requête (connexion DuckDB ou psycopg) et renvoie colonnes et lignes."""
    cursor = connection.execute(query)
    rows = cursor.fetchall()
    return QueryResult([description[0] for description in cursor.description], rows)


def _run_all(engine: str, connection, queries: dict[str, str]) -> ControlRun:
    """Volumétrie de la vue puis chaque requête, dans l'ordre du fichier."""
    total = connection.execute("SELECT count(*) FROM produits").fetchone()[0]
    return ControlRun(engine, int(total), {name: _execute(connection, query) for name, query in queries.items()})


def run_parquet(parquet_dir: Path, queries: dict[str, str]) -> ControlRun:
    """Contrôles en DuckDB sur le Parquet partitionné. Lève FileNotFoundError si la conversion n'est pas terminée."""
    parquet_dir = Path(parquet_dir)
    if not (parquet_dir / SUCCESS_MARKER).exists():
        raise FileNotFoundError(
            f"{parquet_dir} absent ou incomplet (pas de {SUCCESS_MARKER}) : "
            "lancer python -m nutriscope.pipeline parquet (convert_parquet)"
        )
    with duckdb.connect() as con:
        con.execute(DUCKDB_VIEW.format(pattern=sql_literal((parquet_dir / "**" / "*.parquet").as_posix())))
        return _run_all("Parquet (DuckDB)", con, queries)


def run_postgres(conn: psycopg.Connection, queries: dict[str, str]) -> ControlRun:
    """Contrôles sur la base PostgreSQL, via une vue temporaire (disparaît avec la connexion, base non modifiée)."""
    conn.execute(POSTGRES_VIEW)
    return _run_all("Base (PostgreSQL)", conn, queries)


# --- Comparaison et vérifications ---
def _same_value(left, right) -> bool:
    """Même valeur dans les deux moteurs : entiers exacts, décimaux à 1e-9 près (calcul flottant)."""
    if left is None or right is None:
        return left is right
    if isinstance(left, (int, float, Decimal)) and isinstance(right, (int, float, Decimal)):
        return math.isclose(float(left), float(right), rel_tol=1e-9, abs_tol=1e-9)
    return left == right


def compare(first: ControlRun, second: ControlRun) -> dict[str, bool]:
    """{contrôle: identique ?} pour chaque contrôle, plus « volumétrie » (nombre total de produits)."""
    same = {"volumétrie": first.total == second.total}
    for name, result in first.results.items():
        other = second.results.get(name)
        same[name] = (
            other is not None
            and result.columns == other.columns
            and len(result.rows) == len(other.rows)
            and all(
                len(row) == len(other_row) and all(map(_same_value, row, other_row))
                for row, other_row in zip(result.rows, other.rows)
            )
        )
    return same


def _column(result: QueryResult, name: str) -> list:
    """Valeurs d'une colonne du résultat."""
    index = result.columns.index(name)
    return [row[index] for row in result.rows]


def checks(control_run: ControlRun) -> list[tuple[str, bool]]:
    """Vérifications attendues par le TP : (libellé, réussie ?)."""
    by_aisle = control_run.results["comptage_par_rayon"]
    duplicates = control_run.results["doublons"]
    anomalies = control_run.results["bornes_coherences"]
    grades = set(_column(control_run.results["distribution_nutriscore"], "grade"))

    duplicate_codes = dict(zip(_column(duplicates, "controle"), _column(duplicates, "groupes")))["codes en double"]
    bounds = [count for nature, count in zip(_column(anomalies, "nature"), _column(anomalies, "produits"))
              if nature == "borne"]
    aisles = _column(by_aisle, "rayon")
    return [
        ("la somme du comptage par rayon égale la volumétrie totale", sum(_column(by_aisle, "produits")) == control_run.total),
        ("une ligne par rayon (aucun rayon en double)", len(aisles) == len(set(aisles))),
        ("0 code en double", duplicate_codes == 0),
        ("0 valeur hors bornes", all(count == 0 for count in bounds)),
        ("les cinq grades a-e sont présents", set(GRADES) <= grades),
    ]


# --- Rapport Markdown ---
def _cell(value) -> str:
    """Mise en forme d'une cellule : entiers groupés par milliers, décimaux à une décimale avec virgule."""
    if value is None:
        return "—"
    if isinstance(value, bool):
        return "oui" if value else "non"
    if isinstance(value, int):
        return format_int(value)
    if isinstance(value, (float, Decimal)):
        return f"{float(value):.1f}".replace(".", ",")
    return str(value)


def _result_table(result: QueryResult) -> str:
    """Tableau Markdown d'un résultat de requête."""
    return markdown_table(result.columns, [[_cell(value) for value in row] for row in result.rows])


def build_markdown(
    parquet: ControlRun, source: str, database: ControlRun | None = None, date: str | None = None
) -> str:
    """Texte de docs/data/controle.md. La date (aujourd'hui par défaut) est la seule donnée variable."""
    date = date or today().isoformat()
    tolerances = ", ".join(f"{name} = {_label_value(value)}" for name, value in PARAMETERS.items())
    header = (
        "# Contrôles du stockage analytique\n\n"
        f"- Date : {date}\n- Source : `{source}` ({format_int(parquet.total)} produits)\n- {CREDIT}\n"
        f"- Requêtes : `sql/controles.sql` ; paramètres tirés de `src/cleaning.py` : {tolerances}\n"
        "- Généré par `python -m src.storage.run_queries` : ne pas modifier à la main."
    )
    sections = [header]

    rows = [[label, "✓" if ok else "✗"] for label, ok in checks(parquet)]
    sections.append("## Vérifications\n\n" + markdown_table(["Vérification", "Résultat"], rows))

    if database is None:
        sections.append("## Parquet / base\n\nBase non interrogée (`--no-db`).")
    else:
        same = compare(parquet, database)
        rows = [[TITLES.get(name, name), "oui" if ok else "**non**"] for name, ok in same.items()]
        verdict = "identiques" if all(same.values()) else "**différents** : la base et le Parquet ne partent pas du même nettoyé"
        sections.append(
            f"## Parquet / base\n\nMêmes requêtes sur les deux moteurs ; résultats {verdict}.\n\n"
            + markdown_table(["Contrôle", "Identique"], rows)
        )

    for name, result in parquet.results.items():
        parts = [f"## {TITLES.get(name, name)}", _result_table(result)]
        if name in NOTES:
            parts.append(NOTES[name])
        if database is not None and not compare(parquet, database)[name]:
            parts.append("Résultat de la base, différent :\n\n" + _result_table(database.results[name]))
        sections.append("\n\n".join(parts))
    return "\n\n".join(sections) + "\n"


def run(
    parquet_dir: Path,
    sql_path: Path = DEFAULT_SQL,
    output: Path = DEFAULT_OUTPUT,
    conf: dict | None = None,
    use_db: bool = True,
) -> dict:
    """Exécute les contrôles, écrit le Markdown et renvoie {parquet, database, identical, checks, output}."""
    queries = load_queries(sql_path)
    parquet = run_parquet(parquet_dir, queries)
    database = None
    if use_db:
        with load_db.connect(conf) as conn:
            database = run_postgres(conn, queries)

    output = Path(output)
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(build_markdown(parquet, display_path(parquet_dir), database), encoding="utf-8", newline="\n")
    return {
        "parquet": parquet,
        "database": database,
        "identical": None if database is None else compare(parquet, database),
        "checks": checks(parquet),
        "output": output,
    }


def check_database(conf: dict | None = None, sql_path: Path = DEFAULT_SQL) -> dict:
    """Les cinq contrôles sur la base seule (étape load_db) : {database: ControlRun, checks: [(libellé, réussie ?)]}."""
    queries = load_queries(sql_path)
    with load_db.connect(conf) as conn:
        database = run_postgres(conn, queries)
    return {"database": database, "checks": checks(database)}


def check_parquet_against_database(
    parquet_dir: Path, output: Path, conf: dict | None = None, sql_path: Path = DEFAULT_SQL
) -> dict:
    """Contrôles sur le Parquet, comparés à la base, rapport écrit dans `output` (étape parquet) ; renvoie le résumé de run().

    Lève RuntimeError si le Parquet et la base diffèrent, après avoir écrit le rapport (qui montre les écarts) :
    ils ne partent pas du même nettoyé, c'est la chaîne qu'il faut corriger.
    """
    summary = run(parquet_dir, sql_path, output, conf, use_db=True)
    different = [name for name, same in summary["identical"].items() if not same]
    if different:
        raise RuntimeError(
            f"Parquet et base différents ({', '.join(different)}) : ils ne partent pas du même nettoyé ; "
            f"relancer load_db puis parquet (détail : {display_path(summary['output'])})"
        )
    return summary


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Rejoue les cinq contrôles sur le Parquet (et la base).")
    parser.add_argument("--parquet", type=Path, help="dossier partitionné (défaut : le plus récent)")
    parser.add_argument("--sql", type=Path, default=DEFAULT_SQL, help="fichier des requêtes de contrôle")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="fichier Markdown à écrire")
    parser.add_argument("--no-db", action="store_true", help="ne pas interroger la base PostgreSQL")
    args = parser.parse_args(argv)

    parquet = args.parquet or require_input(
        config.PARQUET_DIR, config.PRODUCTS_PREFIX, "", None, "python -m nutriscope.pipeline parquet", require_success=True
    )
    summary = run(parquet, args.sql, args.out, use_db=not args.no_db)
    for label, ok in summary["checks"]:
        print(f"[{'ok' if ok else 'ÉCHEC'}] {label}")
    if summary["identical"] is not None:
        print("Parquet / base :", "identiques" if all(summary["identical"].values()) else "DIFFÉRENTS")
    print(f"Rapport : {display_path(summary['output'])}")


if __name__ == "__main__":
    main()