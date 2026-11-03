"""Rapport avant / après du nettoyage : généré par ce script, jamais édité à la main.

Lancement : python -m src.report [--source data/raw/france_extract_<AAAAMMJJ>.parquet] [--out docs/data/rapport_nettoyage.md]
Sans --source : le brut de l'extrait France le plus récent.
Essai rapide sur l'échantillon : python -m src.report --source data/raw/sample_raw.parquet --out /tmp/rapport.md

Le rapport ne dépend pas de la base : il compare le DataFrame brut et celui que renvoie cleaning.clean().
Les anomalies sont recomptées avec leurs propres définitions (celles du diagnostic) et non avec le code
des règles : sinon le contrôle validerait les règles avec elles-mêmes.
Il se régénère à l'identique : la date n'apparaît qu'en en-tête, et tous les tris sont explicites.
"""

import argparse
from pathlib import Path

import pandas as pd

from src import cleaning, config
from src.utils import (
    aisle_code,
    display_path,
    format_int,
    markdown_table,
    require_input,
    today,
)

DEFAULT_OUTPUT = config.CLEANING_REPORT_PATH
CREDIT = "Données : Open Food Facts, © Open Food Facts contributors, licence ODbL."

# Colonnes dont on suit les manquants avant / après
KEY_COLUMNS = cleaning.KEY_NUTRIENTS + [
    "fat_100g", "carbohydrates_100g", "fiber_100g", "nutriscore_grade", "brands",
]


# --- Petites fonctions de mise en forme ---
def _fr(number: float) -> str:
    """Nombre avec une virgule décimale : 0.5 devient « 0,5 »."""
    return f"{number:g}".replace(".", ",")


def _percent(part: int, total: int) -> str:
    """Pourcentage avec une décimale (0 % si le total est nul)."""
    return f"{100 * part / total:.1f} %".replace(".", ",") if total else "0 %"


# --- Mesures sur un DataFrame (brut ou nettoyé) ---
def _numeric(df: pd.DataFrame) -> pd.DataFrame:
    """Copie dont les nutriments sont lus comme des nombres décimaux (le brut peut contenir du texte)."""
    res = df.copy()
    for column in cleaning.NUTRIENT_COLUMNS:
        res[column] = pd.to_numeric(res[column], errors="coerce").astype("float64")
    return res


def _missing_count(series: pd.Series) -> int:
    """Valeurs absentes : NA, ou texte vide."""
    blank = series.astype("string").str.strip().eq("").fillna(False)
    return int((series.isna() | blank).sum())


def business_anomalies(df: pd.DataFrame) -> dict[str, int]:
    """Anomalies métier du diagnostic : {libellé: nombre de lignes concernées}."""
    d = _numeric(df)
    kcal, kj = d["energy_kcal_100g"], d["energy_kj_100g"]
    carbs, proteins, fat = d["carbohydrates_100g"], d["proteins_100g"], d["fat_100g"]
    salt, sodium = d["salt_100g"], d["sodium_100g"]
    not_alcohol = ~d["food_groups_tag_1"].astype("string").eq(cleaning.ALCOHOL_GROUP).fillna(False).astype(bool)
    atwater = 4 * carbs + 4 * proteins + 9 * fat

    found = {}
    for column, (low, high) in cleaning.RANGES.items():
        value = d[column]
        found[f"{column} hors de [{_fr(low)} ; {_fr(high)}]"] = (value.notna() & ~value.between(low, high)).sum()

    tolerance = cleaning.SUGARS_TOLERANCE
    found[f"sucres > glucides + {_fr(tolerance)}"] = (d["sugars_100g"] > carbs + tolerance).sum()
    tolerance = cleaning.SATURATED_TOLERANCE
    found[f"saturés > lipides + {_fr(tolerance)}"] = (d["saturated_fat_100g"] > fat + tolerance).sum()

    tolerance = cleaning.SALT_SODIUM_TOLERANCE
    found[f"sel ≠ sodium × {_fr(cleaning.SALT_PER_SODIUM)} (écart > {_fr(tolerance)})"] = (
        salt.notna() & sodium.notna() & ((salt - cleaning.SALT_PER_SODIUM * sodium).abs() > tolerance)
    ).sum()
    found[f"rapport kJ / kcal hors de [{_fr(cleaning.KJ_KCAL_RATIO_MIN)} ; {_fr(cleaning.KJ_KCAL_RATIO_MAX)}]"] = (
        (kcal > 0) & (kj > 0) & ~(kj / kcal).between(cleaning.KJ_KCAL_RATIO_MIN, cleaning.KJ_KCAL_RATIO_MAX)
    ).sum()
    found["kcal nulles avec un macronutriment positif (hors alcool)"] = (
        (kcal == 0) & ((carbs > 0) | (proteins > 0) | (fat > 0)) & not_alcohol
    ).sum()
    found[f"kcal à plus de {_fr(100 * cleaning.ENERGY_RELATIVE_TOLERANCE)} % du calcul 4/4/9 (hors alcool)"] = (
        (kcal > 0) & (atwater >= cleaning.ENERGY_MIN_REFERENCE)
        & ((kcal - atwater).abs() / atwater > cleaning.ENERGY_RELATIVE_TOLERANCE) & not_alcohol
    ).sum()

    code = df["code"].astype("string").str.strip()
    has_code = (code.notna() & code.ne("")).fillna(False).astype(bool)
    found["lignes sans code"] = (~has_code).sum()
    found["codes en double (lignes en trop)"] = code[has_code].duplicated().sum()
    return {label: int(count) for label, count in found.items()}


# --- Sections du rapport ---
def _volumes_section(before: pd.DataFrame, after: pd.DataFrame) -> str:
    rows = [
        ["Lignes", format_int(len(before)), format_int(len(after))],
        ["Colonnes", format_int(before.shape[1]), format_int(after.shape[1])],
        ["Codes distincts", format_int(before["code"].nunique()), format_int(after["code"].nunique())],
    ]
    return "## 1. Volumétrie\n\n" + markdown_table(["", "Avant", "Après"], rows)


def _rules_section(reports: list[cleaning.RuleReport]) -> str:
    rows = [
        [
            f"`{r.rule}`", format_int(r.rows_before), format_int(r.rows_after), format_int(r.rows_touched),
            ", ".join(f"{key} = {format_int(value)}" for key, value in r.details.items()),
        ]
        for r in reports
    ]
    note = (
        "Une ligne touchée par plusieurs sous-règles compte une fois dans « lignes touchées » "
        "et une fois par sous-règle dans le détail."
    )
    table = markdown_table(["Règle", "Lignes avant", "Lignes après", "Lignes touchées", "Détail"], rows)
    return f"## 2. Lignes touchées par règle\n\n{note}\n\n{table}"


def _anomalies_section(before: pd.DataFrame, after: pd.DataFrame) -> str:
    anomalies_before, anomalies_after = business_anomalies(before), business_anomalies(after)
    rows = [[label, format_int(anomalies_before[label]), format_int(anomalies_after[label])] for label in anomalies_before]
    return "## 3. Anomalies métier avant / après\n\n" + markdown_table(["Anomalie", "Avant", "Après"], rows)


def _missing_section(before: pd.DataFrame, after: pd.DataFrame) -> str:
    rows = []
    for column in KEY_COLUMNS:
        n_before = _missing_count(before[column])
        n_after = _missing_count(after[column]) if column in after.columns else None
        rows.append([
            column,
            format_int(n_before), _percent(n_before, len(before)),
            "—" if n_after is None else format_int(n_after),
            "—" if n_after is None else _percent(n_after, len(after)),
        ])
    table = markdown_table(["Colonne", "Manquants avant", "%", "Manquants après", "%"], rows)
    return "## 4. Manquants sur les colonnes clés\n\n" + table


def _aisles_section(after: pd.DataFrame) -> str:
    aisles = aisle_code(after["food_groups_tag_1"])
    counts = sorted(aisles.value_counts().items(), key=lambda item: (-item[1], item[0]))   # tri total : ex æquo par nom
    rows = [[f"`{aisle}`", format_int(count), _percent(count, len(after))] for aisle, count in counts]
    return "## 5. Produits par rayon après nettoyage\n\n" + markdown_table(["Rayon", "Produits", "Part"], rows)


def _columns_section(before: pd.DataFrame, after: pd.DataFrame) -> str:
    added = sorted(set(after.columns) - set(before.columns))
    removed = sorted(set(before.columns) - set(after.columns))
    show = lambda names: ", ".join(f"`{name}`" for name in names) if names else "aucune"
    return f"## 6. Colonnes ajoutées et retirées\n\n- Ajoutées : {show(added)}\n- Retirées : {show(removed)}"


# --- Assemblage et écriture ---
def build_report(
    before: pd.DataFrame, after: pd.DataFrame, reports: list[cleaning.RuleReport],
    source: str, date: str | None = None,
) -> str:
    """Texte Markdown du rapport. La date (aujourd'hui par défaut) est la seule donnée variable."""
    date = date or today().isoformat()
    header = (
        "# Rapport de nettoyage\n\n"
        f"- Date : {date}\n- Source : `{source}`\n- {CREDIT}\n"
        "- Généré par `python -m src.report` : ne pas modifier à la main."
    )
    sections = [
        header,
        _volumes_section(before, after),
        _rules_section(reports),
        _anomalies_section(before, after),
        _missing_section(before, after),
        _aisles_section(after),
        _columns_section(before, after),
    ]
    return "\n\n".join(sections) + "\n"


def generate_report(
    before: pd.DataFrame, after: pd.DataFrame, reports: list[cleaning.RuleReport],
    path: Path, source: str, date: str | None = None,
) -> Path:
    """Écrit le rapport dans `path` (dossiers créés si besoin). Fins de ligne fixées : même fichier sur toute machine."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(build_report(before, after, reports, source, date), encoding="utf-8", newline="\n")
    return path


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Génère docs/data/rapport_nettoyage.md à partir d'un parquet brut.")
    parser.add_argument("--source", type=Path, help="parquet brut (colonnes de products_nutrition) ; défaut : extrait France le plus récent")
    parser.add_argument("--out", type=Path, default=DEFAULT_OUTPUT, help="fichier Markdown à écrire")
    args = parser.parse_args(argv)

    source = args.source or require_input(
        config.RAW_DIR, config.FRANCE_EXTRACT_PREFIX, ".parquet", None, "python -m nutriscope.pipeline load"
    )
    before = pd.read_parquet(source)
    after, reports = cleaning.clean(before)
    path = generate_report(before, after, reports, args.out, display_path(source))
    print(f"Rapport écrit : {path} ({len(before)} lignes avant, {len(after)} après)")


if __name__ == "__main__":
    main()