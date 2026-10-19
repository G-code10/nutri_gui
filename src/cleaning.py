"""Nettoyage de products_nutrition : une règle = une fonction pure, appelées dans l'ordre numéroté.

Contrat commun : def rule(df) -> tuple[pd.DataFrame, RuleReport]

Aucune imputation statistique ici (médiane, KNN, mode) : elle appartient au pipeline ML, après le split.
"""

import re
from dataclasses import dataclass, field

import pandas as pd

pd.options.mode.copy_on_write = True

# --- Constantes métier ---
KJ_PER_KCAL = 4.184
SALT_PER_SODIUM = 2.5
KCAL_MAX = 900.0                    # 100 g de lipides purs = 900 kcal
KJ_MAX = KCAL_MAX * KJ_PER_KCAL
SODIUM_MAX = 40.0                   # le sodium représente environ 40 % de la masse du sel
KJ_KCAL_RATIO_MIN = 3.9             # rapport kJ / kcal plausible
KJ_KCAL_RATIO_MAX = 4.5
SUGARS_TOLERANCE = 0.5
SATURATED_TOLERANCE = 0.5
SALT_SODIUM_TOLERANCE = 0.1
ENERGY_RELATIVE_TOLERANCE = 0.5
ENERGY_MIN_REFERENCE = 50.0         # le calcul 4/4/9 doit valoir au moins 50 kcal pour servir de référence
LOW_FAT_THRESHOLD = 0.5             # sous ce seuil, les saturées sont nulles (arrondi d'étiquetage)
UPPERCASE_MIN_LETTERS = 4           # en dessous, on garde les sigles tels quels
ALCOHOL_GROUP = "en:alcoholic-beverages"

# Composantes du Nutri-Score : une ligne sans aucune d'elles est inutilisable
KEY_NUTRIENTS = [
    "energy_kcal_100g", "energy_kj_100g", "saturated_fat_100g",
    "sugars_100g", "proteins_100g", "salt_100g", "sodium_100g",
]

# Colonnes converties en float64 / string par type_columns
NUTRIENT_COLUMNS = [
    "energy_kcal_100g", "energy_kj_100g", "fat_100g", "saturated_fat_100g",
    "carbohydrates_100g", "sugars_100g", "fiber_100g", "proteins_100g",
    "salt_100g", "sodium_100g", "fruits_vegetables_legumes_100g", "completeness",
]
STRING_COLUMNS = ["code", "product_name", "brands", "ingredients_text", "allergens", "serving_size"]

# Textes dont une chaîne vide veut dire « manquant » (pas allergens : '' y a un sens)
TEXT_COLUMNS = ["product_name", "brands", "ingredients_text", "serving_size"]

# Bornes (min, max) en g/100 g, ou kcal / kJ pour l'énergie
RANGES = {
    "fat_100g": (0, 100),
    "saturated_fat_100g": (0, 100),
    "carbohydrates_100g": (0, 100),
    "sugars_100g": (0, 100),
    "fiber_100g": (0, 100),
    "proteins_100g": (0, 100),
    "salt_100g": (0, 100),
    "sodium_100g": (0, SODIUM_MAX),
    "fruits_vegetables_legumes_100g": (0, 100),
    "energy_kcal_100g": (0, KCAL_MAX),
    "energy_kj_100g": (0, KJ_MAX),
}

# Vocabulaire fermé de missing_strategy : décisions combinables avec « + » (ex. "flag+median_by_group")
# et "constant:<valeur>". median_by_group et mode sont reconnues mais appliquées dans le pipeline ML.
MISSING_VOCABULARY = {"keep", "flag", "median_by_group", "mode", "drop_column"}

# Stratégie par défaut : reflet du tableau de décisions, colonne par colonne
DEFAULT_MISSING_STRATEGY = {
    "brands": "flag",
    "product_name": "flag",
    "ingredients_text": "flag",
    "nova_group": "flag",
    "fat_100g": "flag+median_by_group",
    "proteins_100g": "flag+median_by_group",
    "fiber_100g": "flag",
    "fruits_vegetables_legumes_100g": "flag",
    "carbohydrates_100g": "flag",
    "sugars_100g": "flag",
    "saturated_fat_100g": "flag",
    "energy_kcal_100g": "median_by_group",  # drapeau posé après les dérivations par derive_missing_energy
    "salt_100g": "keep",                    # dérivé du sodium (relation exacte)
    "sodium_100g": "keep",
    "allergens": "keep",                    # drapeau posé par handle_allergens_unknown
    "serving_size": "keep",
    "completeness": "keep",
    "nutriscore_score": "keep",
    "nutriscore_grade": "keep",
    "food_groups_tag_1": "keep",
    "categories_tags": "keep",
}


@dataclass
class RuleReport:
    """Compte rendu d'une règle : lignes comptées (une ligne touchée par plusieurs sous-règles compte une fois)."""

    rule: str
    rows_before: int
    rows_after: int
    rows_touched: int
    details: dict[str, int] = field(default_factory=dict)


def _report(
    rule: str,
    before: pd.DataFrame,
    after: pd.DataFrame,
    touched: pd.Series | None = None,
    **details: int,
) -> RuleReport:
    """Construit un compte rendu ; `touched` est le masque des lignes dont une valeur a changé."""
    n_touched = 0 if touched is None else int(touched.fillna(False).astype(bool).sum())
    return RuleReport(
        rule=rule,
        rows_before=len(before),
        rows_after=len(after),
        rows_touched=n_touched,
        details={key: int(value) for key, value in details.items()},
    )


# --- Fonctions utilitaires (pas des règles) ---
def _grade(df: pd.DataFrame) -> pd.Series:
    """Grade Nutri-Score en minuscules, sans espaces autour."""
    return df["nutriscore_grade"].astype("string").str.strip().str.lower()


def _atwater_kcal(df: pd.DataFrame) -> pd.Series:
    """Énergie reconstituée par les facteurs d'Atwater 4/4/9 (NA si un macronutriment manque)."""
    return 4 * df["carbohydrates_100g"] + 4 * df["proteins_100g"] + 9 * df["fat_100g"]


def _is_alcohol(df: pd.DataFrame) -> pd.Series:
    """Boissons alcoolisées : l'alcool apporte de l'énergie que les macronutriments n'expliquent pas."""
    return df["food_groups_tag_1"].astype("string").eq(ALCOHOL_GROUP).fillna(False).astype(bool)


def _recompute_energy(res: pd.DataFrame, mask: pd.Series) -> None:
    """Remplace les kcal par le 4/4/9 et réaligne les kJ sur les lignes du masque (modifie `res`, une copie)."""
    new_kcal = _atwater_kcal(res).round(1)
    res["energy_kcal_100g"] = res["energy_kcal_100g"].mask(mask, new_kcal)
    res["energy_kj_100g"] = res["energy_kj_100g"].mask(mask, (new_kcal * KJ_PER_KCAL).round(1))


def _invalidate_energy(res: pd.DataFrame, mask: pd.Series) -> None:
    """Passe kcal ET kJ à NA sur les lignes du masque (modifie `res`, une copie).

    Les deux valeurs sont suspectes : garder les kJ laisserait derive_missing_energy refaire les kcal
    depuis eux, et la règle se déclencherait de nouveau à chaque passage (idempotence).
    """
    res["energy_kcal_100g"] = res["energy_kcal_100g"].mask(mask)
    res["energy_kj_100g"] = res["energy_kj_100g"].mask(mask)


def _capitalize_first_letter(text: str) -> str:
    """Minuscules, puis majuscule sur la première lettre (pas le premier caractère : « 1664 Blanc »)."""
    return re.sub(r"[^\W\d_]", lambda match: match.group().upper(), text.lower(), count=1)


# --- Règles, dans l'ordre d'exécution ---
def type_columns(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """1. Types : code et textes en string, nutriments en float64 (valeur non convertible -> NA)."""
    res = df.copy()
    coerced = pd.Series(False, index=res.index)
    columns_cast = 0

    for column in NUTRIENT_COLUMNS:
        if column not in res.columns:
            continue
        original = res[column]
        converted = pd.to_numeric(original, errors="coerce").astype("float64")
        coerced |= original.notna() & converted.isna()
        columns_cast += int(converted.dtype != original.dtype)
        res[column] = converted

    for column in STRING_COLUMNS:
        if column not in res.columns:
            continue
        original = res[column]
        converted = original.astype("string")
        columns_cast += int(converted.dtype != original.dtype)
        res[column] = converted

    return res, _report("type_columns", df, res, coerced, columns_cast=columns_cast, values_coerced=coerced.sum())


def _blank_texts_to_na(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, int]:
    """Sous-règle : chaîne vide ou d'espaces -> NA (sauf allergens, où '' a un sens)."""
    res = df.copy()
    touched = pd.Series(False, index=res.index)
    blanks = 0
    for column in TEXT_COLUMNS:
        if column not in res.columns:
            continue
        text = res[column].astype("string")
        blank = (text.str.strip() == "").fillna(False).astype(bool)
        res[column] = text.mask(blank)
        touched |= blank
        blanks += int(blank.sum())
    return res, touched, blanks


def _fix_uppercase_names(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, int]:
    """Sous-règle : noms tout en majuscules -> minuscules avec majuscule initiale (sigles courts conservés)."""
    res = df.copy()
    name = res["product_name"].astype("string")
    letters = name.str.count(r"[^\W\d_]")
    shouting = (
        name.eq(name.str.upper()) & ~name.eq(name.str.lower()) & (letters >= UPPERCASE_MIN_LETTERS)
    ).fillna(False).astype(bool)
    fixed = name.copy()
    fixed[shouting] = name[shouting].map(_capitalize_first_letter)
    res["product_name"] = fixed
    return res, shouting, int(shouting.sum())


def _unify_brand_spelling(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, int]:
    """Sous-règle : chaque variante de casse d'une marque ramenée à la graphie la plus fréquente."""
    res = df.copy()
    brands = res["brands"].astype("string")
    key = brands.str.strip().str.casefold()
    counts = pd.DataFrame({"key": key, "brand": brands}).dropna().groupby(["key", "brand"]).size().rename("n")
    best = counts.reset_index().sort_values(["key", "n", "brand"], ascending=[True, False, True])
    canonical = best.drop_duplicates("key").set_index("key")["brand"]
    unified = key.map(canonical)
    changed = (unified.notna() & (unified != brands)).fillna(False).astype(bool)
    res["brands"] = brands.mask(changed, unified)
    return res, changed, int(changed.sum())


def _strip_codes(df: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, int]:
    """Sous-règle : espaces retirés autour du code-barres."""
    res = df.copy()
    original = res["code"].astype("string")
    stripped = original.str.strip()
    changed = (stripped != original).fillna(False).astype(bool)
    res["code"] = stripped
    return res, changed, int(changed.sum())


def normalize_texts(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """2. Normalisation des textes : vides -> NA, noms en majuscules corrigés, marques unifiées, codes sans espaces.

    Quatre sous-règles enchaînées ; le détail du compte rendu donne le nombre de valeurs corrigées par sous-règle.
    """
    res = df
    touched = pd.Series(False, index=df.index)
    details: dict[str, int] = {}
    for name, step in (
        ("blank_to_na", _blank_texts_to_na),
        ("names_fixed", _fix_uppercase_names),
        ("brands_unified", _unify_brand_spelling),
        ("codes_stripped", _strip_codes),
    ):
        res, mask, count = step(res)
        touched |= mask
        details[name] = count
    return res, _report("normalize_texts", df, res, touched, **details)


def enforce_unique_code(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """3. Identifiant : lignes sans code (NULL ou vide) écartées, puis une seule fiche par code.

    Parmi les doublons, la fiche la plus complète (completeness) est gardée, puis la plus récente
    (last_modified_t si présente). À égalité, la première ligne rencontrée est gardée.
    L'ordre d'origine des lignes est conservé.
    """
    code = df["code"].astype("string")
    missing = (code.isna() | (code.str.strip() == "")).fillna(True).astype(bool)
    res = df.loc[~missing].reset_index(drop=True)

    sort_keys = [column for column in ("completeness", "last_modified_t") if column in res.columns]
    ranked = res.sort_values(sort_keys, ascending=False, kind="stable") if sort_keys else res
    kept = ranked.drop_duplicates(subset="code", keep="first")
    is_kept = res.index.isin(kept.index)
    counts = res["code"].value_counts()
    out = res.loc[is_kept].reset_index(drop=True)

    dropped = len(df) - len(out)
    report = _report(
        "enforce_unique_code", df, out, None,
        rows_without_code=missing.sum(), duplicates_removed=(~is_kept).sum(),
        codes_concerned=(counts > 1).sum(),
    )
    report.rows_touched = dropped  # lignes touchées = lignes supprimées
    return out, report


def normalize_grade(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """4. Nutri-Score : « unknown » et « not-applicable » deviennent NA ; on ne remplit jamais la cible.

    Le drapeau grade_not_applicable est posé avant l'effacement, pour distinguer « non noté par
    construction » d'un manquant ordinaire. Un drapeau déjà posé est conservé (idempotence).
    """
    res = df.copy()
    grade = _grade(res)
    not_applicable = grade.eq("not-applicable").fillna(False).astype(bool)
    unknown = grade.eq("unknown").fillna(False).astype(bool)

    previous = res["grade_not_applicable"].fillna(False) if "grade_not_applicable" in res.columns else False
    res["grade_not_applicable"] = (not_applicable | previous).astype("boolean")
    res["nutriscore_grade"] = res["nutriscore_grade"].mask(not_applicable | unknown, pd.NA)
    return res, _report(
        "normalize_grade", df, res, not_applicable | unknown,
        not_applicable=not_applicable.sum(), unknown=unknown.sum(),
    )


def drop_unclassifiable(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """5. Produits inclassables supprimés : catégories vides (NULL ou liste vide), comme le TP.

    Le TP vise « sans catégorie et de rayon unknown ». Sur nos données, tout produit sans catégorie
    a aussi un food_groups_tag_1 NULL (équivalent du rayon unknown), donc la condition sur les
    catégories suffit.
    """
    categories = df["categories_tags"]

    # NULL ou liste vide (isna() ne voit pas les listes vides)
    empty_list = categories.map(lambda x: hasattr(x, "__len__") and len(x) == 0)
    unclassifiable = (categories.isna() | empty_list).astype(bool)

    res = df.loc[~unclassifiable].reset_index(drop=True)
    return res, _report(
        "drop_unclassifiable", df, res, unclassifiable,  # lignes touchées = lignes supprimées
        unclassifiable_dropped=unclassifiable.sum(),
    )


def neutralize_range(
    df: pd.DataFrame, column: str, low: float, high: float
) -> tuple[pd.DataFrame, RuleReport]:
    """6. Garde-fou : valeurs de `column` hors de [low, high] neutralisées en NA, jamais imputées."""
    res = df.copy()
    values = res[column]
    invalid = values.notna() & ~values.between(low, high)
    res[column] = values.mask(invalid)
    return res, _report(f"neutralize_range:{column}", df, res, invalid, invalid_to_na=invalid.sum())


def neutralize_subpart_above_total(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """7. Sous-partie supérieure à son total (+ tolérance de 0,5) -> NA, jamais imputée.

    Sucres > glucides, et saturées > lipides : les sucres sont une sous-partie des glucides,
    les saturées une sous-partie du fat. Le total reste inchangé.
    """
    res = df.copy()
    sugars, carbs = res["sugars_100g"], res["carbohydrates_100g"]
    sat, fat = res["saturated_fat_100g"], res["fat_100g"]

    sugars_above = sugars.notna() & carbs.notna() & (sugars > carbs + SUGARS_TOLERANCE)
    saturated_above = sat.notna() & fat.notna() & (sat > fat + SATURATED_TOLERANCE)

    res["sugars_100g"] = sugars.mask(sugars_above)
    res["saturated_fat_100g"] = sat.mask(saturated_above)
    return res, _report(
        "neutralize_subpart_above_total", df, res, sugars_above | saturated_above,
        sugars_above_carbs=sugars_above.sum(), saturated_above_fat=saturated_above.sum(),
    )


def handle_allergens_unknown(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """8. Allergènes : NULL, ou chaîne vide sans ingrédients = inconnu (drapeau allergens_missing, chaîne vide -> NA).

    Une chaîne vide avec ingrédients connus veut dire « aucun allergène déclaré » : elle est conservée.
    Le drapeau est calculé avant l'effacement des chaînes vides.
    """
    res = df.copy()
    allergens = res["allergens"].astype("string")
    is_empty = allergens.eq("").fillna(False).astype(bool)
    no_ingredients = res["ingredients_text"].isna()
    empty_no_ingredients = (is_empty & no_ingredients).astype(bool)

    unknown = (allergens.isna() | empty_no_ingredients).astype(bool)
    res["allergens_missing"] = unknown.astype("boolean")
    res["allergens"] = allergens.mask(empty_no_ingredients)
    return res, _report(
        "handle_allergens_unknown", df, res, empty_no_ingredients,
        flagged=unknown.sum(), empty_to_na=empty_no_ingredients.sum(),
        none_declared=(is_empty & ~no_ingredients).sum(),
    )


def missing_strategy(
    df: pd.DataFrame, strategy: dict[str, str] = DEFAULT_MISSING_STRATEGY
) -> tuple[pd.DataFrame, RuleReport]:
    """9. Stratégie de manquants : applique la décision de chaque colonne (dictionnaire, vocabulaire fermé).

    Décisions : keep, flag (colonne <col>_missing), constant:<valeur>, drop_column, et median_by_group / mode
    (reconnues mais non appliquées ici : imputation statistique, réservée au pipeline ML après le split).
    Plusieurs décisions se combinent avec « + ». Une décision inconnue lève ValueError, une colonne absente KeyError.
    """
    parsed = {}
    for column, decision in strategy.items():
        if column not in df.columns:
            raise KeyError(f"Colonne absente du DataFrame : {column}")
        tokens = decision.split("+")
        for token in tokens:
            if token not in MISSING_VOCABULARY and not token.startswith("constant:"):
                raise ValueError(f"Décision inconnue pour {column} : {token}")
        parsed[column] = sorted(tokens, key=lambda token: token == "drop_column")  # suppression en dernier

    res = df.copy()
    touched = pd.Series(False, index=res.index)
    counts = {"flags_set": 0, "constants_filled": 0, "deferred": 0, "columns_dropped": 0}

    for column, tokens in parsed.items():
        for token in tokens:
            if token == "flag":
                # Un drapeau déjà posé est conservé : une règle ultérieure a pu remplir la valeur (idempotence)
                flag_name = f"{column}_missing"
                previous = res[flag_name].fillna(False).astype(bool) if flag_name in res.columns else False
                res[flag_name] = (res[column].isna() | previous).astype("boolean")
                counts["flags_set"] += 1
            elif token.startswith("constant:"):
                value = token.split(":", 1)[1]
                if pd.api.types.is_numeric_dtype(res[column]):
                    value = float(value)
                missing = res[column].isna()
                res[column] = res[column].fillna(value)
                touched |= missing
                counts["constants_filled"] += int(missing.sum())
            elif token in ("median_by_group", "mode"):
                counts["deferred"] += 1
            elif token == "drop_column":
                res = res.drop(columns=[column])
                counts["columns_dropped"] += 1

    return res, _report("missing_strategy", df, res, touched, **counts)


def fill_saturated_zero_if_low_fat(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """10. Saturées manquantes = 0 si fat < 0,5 g : déduction exacte (les saturées sont une sous-partie du fat).

    Le drapeau saturated_fat_100g_missing, posé à l'étape 9, garde la trace du manque d'origine.
    Les saturées neutralisées aux étapes 6 et 7 sont aussi concernées : fat < 0,5 g borne les saturées.
    """
    res = df.copy()
    sat, fat = res["saturated_fat_100g"], res["fat_100g"]
    to_zero = sat.isna() & (fat < LOW_FAT_THRESHOLD)
    res["saturated_fat_100g"] = sat.mask(to_zero, 0)
    return res, _report("fill_saturated_zero_if_low_fat", df, res, to_zero, set_to_zero=to_zero.sum())


def reconcile_salt_sodium(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """11. Sel et sodium : relation exacte sel = sodium × 2,5 (valeurs déjà bornées par l'étape 6).

    1) Écart > 0,1 entre les deux : le sodium est recalculé depuis le sel, qui fait référence.
    2) Un des deux manquant : il est dérivé de l'autre.
    """
    res = df.copy()
    salt, sodium = res["salt_100g"], res["sodium_100g"]

    inconsistent = (
        salt.notna() & sodium.notna()
        & ((salt - SALT_PER_SODIUM * sodium).abs() > SALT_SODIUM_TOLERANCE)
    )
    sodium = sodium.mask(inconsistent, salt / SALT_PER_SODIUM)

    salt_derived = salt.isna() & sodium.notna()
    sodium_derived = sodium.isna() & salt.notna()
    res["salt_100g"] = salt.mask(salt_derived, sodium * SALT_PER_SODIUM)
    res["sodium_100g"] = sodium.mask(sodium_derived, salt / SALT_PER_SODIUM)
    return res, _report(
        "reconcile_salt_sodium", df, res, inconsistent | salt_derived | sodium_derived,
        sodium_recomputed=inconsistent.sum(), salt_derived=salt_derived.sum(), sodium_derived=sodium_derived.sum(),
    )


def reconcile_kcal_kj(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """12. Unités d'énergie : si kJ / kcal sort de [3,9 ; 4,5], les kcal sont recalculées depuis les kJ.

    Ne touche que les lignes où kcal et kJ sont présentes et strictement positives. Les kcal nulles
    sont laissées à fix_inconsistent_energy, et les kcal absentes à derive_missing_energy.
    """
    res = df.copy()
    kcal, kj = res["energy_kcal_100g"], res["energy_kj_100g"]

    ratio = kj / kcal
    inconsistent = (
        kcal.notna() & kj.notna() & (kcal > 0) & (kj > 0)
        & ~ratio.between(KJ_KCAL_RATIO_MIN, KJ_KCAL_RATIO_MAX)
    )

    new_kcal = (kj / KJ_PER_KCAL).round(1)
    # Compté seulement si la valeur change (l'arrondi peut laisser un rapport hors plage sur de très petites valeurs)
    changed = (inconsistent & (new_kcal != kcal)).fillna(False).astype(bool)

    res["energy_kcal_100g"] = kcal.mask(changed, new_kcal)
    return res, _report(
        "reconcile_kcal_kj", df, res, changed,
        ratio_inconsistent=inconsistent.sum(), kcal_recomputed=changed.sum(),
    )


def fix_inconsistent_energy(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """13. Énergie incohérente avec le calcul 4/4/9 : recalcul, kJ réalignés ; recalcul impossible -> kcal et kJ en NA.

    1) Énergie nulle alors qu'un macronutriment est positif.
    2) Énergie non nulle à plus de 50 % du calcul 4/4/9 (calcul >= 50 kcal).
    Exception : boissons alcoolisées, laissées intactes. Une valeur déclarée est remplacée par une
    approximation (Atwater ignore fibres et polyols), ce que le TP demande ; si le calcul est impossible
    (macronutriment manquant, calcul hors de [0, 900]), les kcal et les kJ deviennent NA ; les kcal pourront être redérivées
    plus tard par derive_missing_energy, à partir des macronutriments seulement.
    """
    res = df.copy()
    carbs, proteins, fat = res["carbohydrates_100g"], res["proteins_100g"], res["fat_100g"]
    not_alcohol = ~_is_alcohol(res)

    calc = _atwater_kcal(res)
    computable = calc.between(0, KCAL_MAX).fillna(False).astype(bool)

    zero_with_macros = (res["energy_kcal_100g"] == 0) & ((carbs > 0) | (proteins > 0) | (fat > 0))
    zero_flagged = (zero_with_macros & not_alcohol).fillna(False).astype(bool)
    zero_fix, zero_invalid = zero_flagged & computable, zero_flagged & ~computable
    _recompute_energy(res, zero_fix)
    _invalidate_energy(res, zero_invalid)

    kcal = res["energy_kcal_100g"]
    deviating = (
        kcal.notna() & (kcal > 0) & (calc >= ENERGY_MIN_REFERENCE)
        & ((kcal - calc).abs() / calc > ENERGY_RELATIVE_TOLERANCE)
    )
    deviation_flagged = (deviating & not_alcohol).fillna(False).astype(bool)
    deviation_fix, deviation_invalid = deviation_flagged & computable, deviation_flagged & ~computable
    _recompute_energy(res, deviation_fix)
    _invalidate_energy(res, deviation_invalid)

    touched = zero_fix | zero_invalid | deviation_fix | deviation_invalid
    return res, _report(
        "fix_inconsistent_energy", df, res, touched,
        zero_recomputed=zero_fix.sum(), zero_invalidated=zero_invalid.sum(),
        deviation_recomputed=deviation_fix.sum(), deviation_invalidated=deviation_invalid.sum(),
    )


def drop_rows_without_key_nutrient(
    df: pd.DataFrame, columns: list[str] = KEY_NUTRIENTS
) -> tuple[pd.DataFrame, RuleReport]:
    """14. Supprime les lignes dont toutes les composantes du score sont manquantes.

    Placée après fix_inconsistent_energy, qui peut invalider les dernières valeurs d'une ligne (idempotence),
    et avant derive_missing_energy, qui ne doit pas faire revivre une ligne sans nutriment clé.
    """
    mask = df[columns].isna().all(axis=1)
    res = df.loc[~mask].reset_index(drop=True)
    return res, _report(
        "drop_rows_without_key_nutrient", df, res, mask,  # lignes touchées = lignes supprimées
        rows_dropped=mask.sum(),
    )


def derive_missing_energy(df: pd.DataFrame) -> tuple[pd.DataFrame, RuleReport]:
    """15. Kcal manquantes : dérivées des kJ (kJ / 4,184, exact), sinon du 4/4/9 (approximation) ; le reste est signalé.

    Le 4/4/9 n'est utilisé que si les trois macronutriments sont présents. Le drapeau energy_kcal_100g_missing
    veut dire « manquante après dérivation » ; la médiane par groupe est appliquée plus tard, dans le pipeline ML.
    """
    res = df.copy()
    kcal, kj = res["energy_kcal_100g"], res["energy_kj_100g"]

    from_kj = kcal.isna() & kj.notna()
    kcal = kcal.mask(from_kj, (kj / KJ_PER_KCAL).round(1))

    calc = _atwater_kcal(res)
    from_macros = kcal.isna() & calc.between(0, KCAL_MAX)
    kcal = kcal.mask(from_macros, calc.round(1))

    res["energy_kcal_100g"] = kcal
    res["energy_kcal_100g_missing"] = kcal.isna().astype("boolean")
    return res, _report(
        "derive_missing_energy", df, res, from_kj | from_macros,
        kcal_from_kj=from_kj.sum(), kcal_from_macros=from_macros.sum(),
        flagged=res["energy_kcal_100g_missing"].sum(),
    )


def clean(df: pd.DataFrame) -> tuple[pd.DataFrame, list[RuleReport]]:
    """Enchaîne les règles dans l'ordre numéroté ; renvoie le DataFrame nettoyé et les comptes rendus."""
    reports: list[RuleReport] = []

    def run(rule, *args):
        nonlocal df
        df, report = rule(df, *args)
        reports.append(report)

    run(type_columns)
    run(normalize_texts)
    run(enforce_unique_code)
    run(normalize_grade)
    run(drop_unclassifiable)
    for column, (low, high) in RANGES.items():
        run(neutralize_range, column, low, high)
    run(neutralize_subpart_above_total)
    run(handle_allergens_unknown)
    run(missing_strategy)
    run(fill_saturated_zero_if_low_fat)
    run(reconcile_salt_sodium)
    run(reconcile_kcal_kj)
    run(fix_inconsistent_energy)
    run(drop_rows_without_key_nutrient)
    run(derive_missing_energy)
    return df, reports