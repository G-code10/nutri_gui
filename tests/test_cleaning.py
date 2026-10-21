"""Tests de cleaning.py : un cas nominal et un cas tordu par règle, pureté et idempotence sur toutes."""

from functools import partial
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
from pandas.testing import assert_frame_equal

from src import cleaning

NA = np.nan

# --- Données de test : chaque ligne piège une règle ---
COLUMNS = [
    "code", "product_name", "brands", "ingredients_text", "allergens",
    "energy_kcal_100g", "energy_kj_100g", "fat_100g", "saturated_fat_100g",
    "carbohydrates_100g", "sugars_100g", "fiber_100g", "proteins_100g",
    "salt_100g", "sodium_100g", "categories_tags", "food_groups_tag_1",
    "nutriscore_grade", "completeness",
]

ROWS = [
    # 0 : produit sain, témoin : rien ne doit changer
    ("1000", "Yaourt nature", "Danone", "lait", "en:milk", 60, 251, 3.0, 2.0, 5.0, 5.0, 0.0, 4.0, 0.1, 0.04, ["en:dairies"], "en:milk-and-dairy-products", "a", 0.9),
    # 1 : code avec espaces autour
    (" 1001 ", "Pâtes complètes", "Panzani", "blé", "en:gluten", 350, 1464, 2.0, 0.5, 70.0, 3.0, 8.0, 12.0, 0.01, 0.004, ["en:pastas"], "en:cereals-and-potatoes", "b", 0.8),
    # 2 : nom tout en majuscules
    ("1002", "BISCUIT CHOCOLAT", "Lu", "farine", "en:gluten", 480, 2008, 20.0, 10.0, 65.0, 30.0, 3.0, 6.0, 0.5, 0.2, ["en:biscuits"], "en:sugary-snacks", "d", 0.7),
    # 3 : même marque que la ligne 2, autre casse
    ("1003", "Gaufrettes", "LU", "farine", "en:gluten", 500, 2092, 22.0, 11.0, 66.0, 32.0, 2.0, 5.0, 0.4, 0.16, ["en:biscuits"], "en:sugary-snacks", "d", 0.7),
    # 4 et 5 : même code, deux complétudes : la fiche à 0,9 doit rester
    ("1004", "Soupe", "Liebig", "eau", "", 40, 167, 1.0, 0.2, 6.0, 2.0, 1.0, 1.0, 0.8, 0.32, ["en:soups"], "en:composite-foods", "b", 0.4),
    ("1004", "Soupe légumes", "Liebig", "eau, légumes", "", 42, 176, 1.0, 0.2, 6.0, 2.0, 1.5, 1.0, 0.8, 0.32, ["en:soups"], "en:composite-foods", "b", 0.9),
    # 6 : grade "unknown" -> NA ; 7 : grade "not-applicable" -> NA + drapeau
    ("1005", "Sauce", "Heinz", "tomate", "", 80, 335, 2.0, 0.3, 14.0, 10.0, 1.0, 1.0, 1.0, 0.4, ["en:sauces"], "en:fat-and-sauces", "unknown", 0.6),
    ("1006", "Eau minérale", "Evian", "eau", "", 0, 0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, 0.0, ["en:waters"], "en:beverages", "not-applicable", 0.5),
    # 8 : aucune catégorie (liste vide) -> ligne supprimée
    ("1007", "Mystère", "Inconnu", "?", "", 100, 418, 5.0, 1.0, 10.0, 5.0, 1.0, 3.0, 0.2, 0.08, [], None, "c", 0.3),
    # 9 : valeurs impossibles : sucres 74 000 g, sel 5 000 g, énergie 24 000 kcal
    ("1008", "Bonbons", "Haribo", "sucre", "", 24000, 100416, 0.0, 0.0, 80.0, 74000.0, 0.0, 0.0, 5000.0, 2000.0, ["en:candies"], "en:sugary-snacks", "e", 0.6),
    # 10 : sucres > glucides ET saturées > lipides
    ("1009", "Céréales", "Kelloggs", "blé", "en:gluten", 300, 1255, 3.0, 8.0, 60.0, 65.0, 4.0, 8.0, 0.3, 0.12, ["en:cereals"], "en:cereals-and-potatoes", "c", 0.7),
    # 11 : lipides < 0,5 g et saturées absentes -> saturées = 0
    ("1010", "Thé glacé", "Lipton", "eau, thé", "", 20, 84, 0.2, NA, 4.5, 4.0, 0.0, 0.0, 0.0, 0.0, ["en:beverages"], "en:beverages", "b", 0.5),
    # 12 : aucun nutriment clé -> ligne supprimée
    ("1011", "Fiche vide", "Inconnu", "x", "", NA, NA, NA, NA, NA, NA, NA, NA, NA, NA, ["en:snacks"], "en:sugary-snacks", "c", 0.1),
    # 13 : sodium présent, sel absent -> sel = sodium x 2,5
    ("1012", "Chips", "Lays", "pomme de terre", "", 540, 2259, 33.0, 3.0, 50.0, 1.0, 4.0, 6.0, NA, 0.5, ["en:chips"], "en:salty-snacks", "d", 0.8),
    # 14 : rapport kJ/kcal incohérent (1000 kJ pour 400 kcal) -> kcal recalculées depuis les kJ
    ("1013", "Pain", "Harrys", "farine", "en:gluten", 400, 1000, 5.0, 1.0, 70.0, 5.0, 3.0, 10.0, 1.0, 0.4, ["en:breads"], "en:cereals-and-potatoes", "b", 0.8),
    # 15 : énergie à 0 alors que les macros sont positives -> recalcul 4/4/9
    ("1014", "Beurre", "Président", "crème", "en:milk", 0, 0, 82.0, 52.0, 0.5, 0.5, 0.0, 0.8, 0.0, 0.0, ["en:fats"], "en:fat-and-sauces", "e", 0.8),
    # 16 : boisson alcoolisée : énergie au-dessus du 4/4/9 mais légitime (exception)
    ("1015", "Vin rouge", "Bordeaux", "raisin", "en:sulphites", 85, 356, 0.0, 0.0, 2.6, 0.6, 0.0, 0.1, 0.0, 0.0, ["en:wines"], "en:alcoholic-beverages", "e", 0.6),
    # 17 : kcal absentes, kJ présents -> kcal = kJ / 4,184
    ("1016", "Jus d'orange", "Tropicana", "orange", "", NA, 188, 0.2, 0.0, 10.0, 9.0, 0.5, 0.7, 0.0, 0.0, ["en:juices"], "en:beverages", "c", 0.7),
]


@pytest.fixture
def raw():
    """DataFrame tordu neuf pour chaque test (aucun test ne peut fausser le suivant)."""
    df = pd.DataFrame(ROWS, columns=COLUMNS)
    # Colonnes lues par missing_strategy, absentes des cas ci-dessus
    df["serving_size"] = None
    df["fruits_vegetables_legumes_100g"] = NA
    df["nutriscore_score"] = 5
    df["nova_group"] = 3
    return df


def by_code(df, code):
    """Renvoie la ligne dont le code (espaces retirés) vaut `code`."""
    selected = df.loc[df["code"].astype("string").str.strip() == code]
    assert len(selected) == 1, f"{len(selected)} ligne(s) pour le code {code}"
    return selected.iloc[0]


def small(**columns):
    """Petit DataFrame construit à la main pour un cas tordu isolé."""
    return pd.DataFrame(columns)


# --- Liste des règles, pour les tests de pureté et d'idempotence ---
SIMPLE_RULES = [
    cleaning.type_columns,
    cleaning.normalize_texts,
    cleaning.enforce_unique_code,
    cleaning.normalize_grade,
    cleaning.drop_unclassifiable,
    cleaning.neutralize_subpart_above_total,
    cleaning.handle_allergens_unknown,
    cleaning.missing_strategy,
    cleaning.fill_saturated_zero_if_low_fat,
    cleaning.drop_rows_without_key_nutrient,
    cleaning.reconcile_salt_sodium,
    cleaning.reconcile_kcal_kj,
    cleaning.fix_inconsistent_energy,
    cleaning.derive_missing_energy,
]
RANGE_RULES = [
    partial(cleaning.neutralize_range, column=column, low=low, high=high)
    for column, (low, high) in cleaning.RANGES.items()
]
RULES = SIMPLE_RULES + RANGE_RULES
RULE_IDS = [rule.__name__ for rule in SIMPLE_RULES] + [
    f"neutralize_range:{column}" for column in cleaning.RANGES
]


# =====================================================================
# 1. type_columns
# =====================================================================
def test_type_columns_nominal():
    df = small(code=[1, 2], energy_kcal_100g=["12", "abc"])
    res, report = cleaning.type_columns(df)
    assert str(res["code"].dtype) == "string"
    assert res["energy_kcal_100g"].dtype == "float64"
    assert res["energy_kcal_100g"].iloc[0] == 12.0
    assert report.details["values_coerced"] == 1


def test_type_columns_tordu_valeur_non_numerique_devient_na():
    df = small(code=["1"], fat_100g=["beaucoup"])
    res, _ = cleaning.type_columns(df)
    assert pd.isna(res["fat_100g"].iloc[0])


# =====================================================================
# 2. normalize_texts
# =====================================================================
def test_normalize_texts_nominal(raw):
    res, report = cleaning.normalize_texts(raw)
    assert by_code(res, "1001")["code"] == "1001"
    assert by_code(res, "1002")["product_name"] == "Biscuit chocolat"
    assert by_code(res, "1002")["brands"] == by_code(res, "1003")["brands"] == "LU"
    assert report.details["codes_stripped"] == 1
    assert report.details["names_fixed"] == 1
    assert report.details["brands_unified"] == 1
    assert report.rows_touched == 2  # 1001 (code) et 1002 (nom, marque) ; 1003 a déjà la graphie retenue


def test_normalize_texts_tordu():
    df = small(
        code=["1", "2", "3"],
        product_name=["BIO", "1664 BLANC", "   "],
        brands=["a", "a", "a"],
        ingredients_text=["x", "x", "x"],
        serving_size=["x", "x", "x"],
    )
    res, _ = cleaning.normalize_texts(df)
    assert res["product_name"].iloc[0] == "BIO"           # sigle court conservé
    assert res["product_name"].iloc[1] == "1664 Blanc"    # première lettre, pas premier caractère
    assert pd.isna(res["product_name"].iloc[2])           # espaces seuls -> NA


def test_normalize_texts_tordu_octets_nuls():
    # PostgreSQL refuse 0x00 dans un texte : retiré ; un texte réduit à cet octet devient vide, donc NA
    df = small(
        code=["1", "2"],
        product_name=["Pain", "\x00"],
        brands=["Mar\x00que", "Autre"],
        ingredients_text=["x", "x"],
        serving_size=["x", "x"],
    )
    res, report = cleaning.normalize_texts(df)
    assert res["brands"].iloc[0] == "Marque"
    assert pd.isna(res["product_name"].iloc[1])
    assert report.details["nul_removed"] == 2
    assert not any("\x00" in str(value) for column in res.columns for value in res[column])
    again, second = cleaning.normalize_texts(res)
    assert second.rows_touched == 0   # seconde passe : rien à faire


# =====================================================================
# 3. enforce_unique_code
# =====================================================================
def test_enforce_unique_code_nominal(raw):
    res, report = cleaning.enforce_unique_code(raw)
    soups = res.loc[res["code"] == "1004"]
    assert len(soups) == 1
    assert soups.iloc[0]["product_name"] == "Soupe légumes"  # la plus complète
    assert report.rows_before - report.rows_after == 1
    assert report.details["duplicates_removed"] == 1
    assert report.rows_touched == 1


def test_enforce_unique_code_tordu_sans_code_et_egalite():
    df = small(
        code=["1", "", None, "  ", "2", "2"],
        product_name=["a", "b", "c", "d", "premier", "second"],
        completeness=[0.5, 0.5, 0.5, 0.5, 0.7, 0.7],
    )
    res, report = cleaning.enforce_unique_code(df)
    assert set(res["code"]) == {"1", "2"}
    assert res.loc[res["code"] == "2", "product_name"].iloc[0] == "premier"  # à égalité, la première
    assert report.details["rows_without_code"] == 3


# =====================================================================
# 4. normalize_grade
# =====================================================================
def test_normalize_grade_nominal(raw):
    res, report = cleaning.normalize_grade(raw)
    assert pd.isna(by_code(res, "1005")["nutriscore_grade"])
    assert pd.isna(by_code(res, "1006")["nutriscore_grade"])
    assert by_code(res, "1000")["nutriscore_grade"] == "a"
    assert bool(by_code(res, "1006")["grade_not_applicable"]) is True
    assert bool(by_code(res, "1005")["grade_not_applicable"]) is False
    assert report.details == {"not_applicable": 1, "unknown": 1}


def test_normalize_grade_tordu_casse_et_espaces():
    df = small(nutriscore_grade=[" Not-Applicable ", "UNKNOWN", None, "b"])
    res, _ = cleaning.normalize_grade(df)
    assert list(res["grade_not_applicable"]) == [True, False, False, False]
    assert res["nutriscore_grade"].isna().tolist() == [True, True, True, False]


# =====================================================================
# 5. drop_unclassifiable
# =====================================================================
def test_drop_unclassifiable_nominal(raw):
    res, report = cleaning.drop_unclassifiable(raw)
    assert "1007" not in set(res["code"])
    assert report.details["unclassifiable_dropped"] == 1
    assert len(res) == len(raw) - 1


def test_drop_unclassifiable_tordu_null_et_liste_vide():
    df = small(code=["1", "2", "3"], categories_tags=[None, [], ["en:x"]])
    res, _ = cleaning.drop_unclassifiable(df)
    assert list(res["code"]) == ["3"]


# =====================================================================
# 6. reconcile_salt_sodium
# =====================================================================
def test_reconcile_salt_sodium_nominal(raw):
    res, report = cleaning.reconcile_salt_sodium(raw)
    assert by_code(res, "1012")["salt_100g"] == pytest.approx(1.25)
    assert report.details["salt_derived"] == 1


def test_reconcile_salt_sodium_tordu():
    df = small(
        salt_100g=[1.0, 1.0, NA, 2.5],
        sodium_100g=[0.1, 0.38, 0.0, NA],  # incohérent / dans la tolérance / zéro / manquant
    )
    res, _ = cleaning.reconcile_salt_sodium(df)
    assert res["sodium_100g"].iloc[0] == pytest.approx(0.4)    # recalculé depuis le sel
    assert res["sodium_100g"].iloc[1] == 0.38                  # écart de 0,05 : toléré
    assert res["salt_100g"].iloc[2] == 0.0                     # sodium nul -> sel nul
    assert res["sodium_100g"].iloc[3] == pytest.approx(1.0)    # sodium dérivé du sel


# =====================================================================
# 7. reconcile_kcal_kj
# =====================================================================
def test_reconcile_kcal_kj_nominal(raw):
    res, report = cleaning.reconcile_kcal_kj(raw)
    assert by_code(res, "1013")["energy_kcal_100g"] == pytest.approx(239.0)
    assert by_code(res, "1000")["energy_kcal_100g"] == 60.0
    assert report.details["kcal_recomputed"] == 1


def test_reconcile_kcal_kj_tordu():
    df = small(
        energy_kcal_100g=[100.0, 0.0, NA, 100.0],
        energy_kj_100g=[418.4, 100.0, 100.0, 390.0],  # cohérent / kcal nulles / kcal absentes / ratio 3,9 à la borne
    )
    res, _ = cleaning.reconcile_kcal_kj(df)
    assert list(res["energy_kcal_100g"].iloc[:2]) == [100.0, 0.0]
    assert pd.isna(res["energy_kcal_100g"].iloc[2])  # laissée à derive_missing_energy
    assert res["energy_kcal_100g"].iloc[3] == 100.0  # ratio 3,9 : dans la plage


# =====================================================================
# 8. neutralize_range
# =====================================================================
def test_neutralize_range_nominal(raw):
    res, report = cleaning.neutralize_range(raw, "sugars_100g", 0, 100)
    assert pd.isna(by_code(res, "1008")["sugars_100g"])
    assert by_code(res, "1000")["sugars_100g"] == 5.0
    assert report.details["invalid_to_na"] == 1


def test_neutralize_range_tordu_borne_exacte():
    df = small(energy_kcal_100g=[900.0, 900.1, -1.0, 0.0, NA])
    res, _ = cleaning.neutralize_range(df, "energy_kcal_100g", 0, cleaning.KCAL_MAX)
    assert res["energy_kcal_100g"].iloc[0] == 900.0   # à la borne : conservé
    assert pd.isna(res["energy_kcal_100g"].iloc[1])   # au-delà : NA
    assert pd.isna(res["energy_kcal_100g"].iloc[2])   # négatif : NA
    assert res["energy_kcal_100g"].iloc[3] == 0.0     # zéro légitime


# =====================================================================
# 9. neutralize_subpart_above_total
# =====================================================================
def test_neutralize_subpart_above_total_nominal(raw):
    res, report = cleaning.neutralize_subpart_above_total(raw)
    row = by_code(res, "1009")
    assert pd.isna(row["sugars_100g"]) and pd.isna(row["saturated_fat_100g"])
    assert row["carbohydrates_100g"] == 60.0 and row["fat_100g"] == 3.0  # les totaux restent
    # Règle isolée : les bonbons à 74 000 g de sucres comptent aussi (la borne 0-100 g n'est pas passée avant)
    assert report.details == {"sugars_above_carbs": 2, "saturated_above_fat": 1}


def test_neutralize_subpart_above_total_tordu_tolerance():
    df = small(
        sugars_100g=[10.5, 10.6], carbohydrates_100g=[10.0, 10.0],
        saturated_fat_100g=[5.5, 5.6], fat_100g=[5.0, 5.0],
    )
    res, _ = cleaning.neutralize_subpart_above_total(df)
    assert res["sugars_100g"].iloc[0] == 10.5 and pd.isna(res["sugars_100g"].iloc[1])
    assert res["saturated_fat_100g"].iloc[0] == 5.5 and pd.isna(res["saturated_fat_100g"].iloc[1])


# =====================================================================
# 10. handle_allergens_unknown
# =====================================================================
def test_handle_allergens_unknown_nominal(raw):
    res, report = cleaning.handle_allergens_unknown(raw)
    assert bool(by_code(res, "1000")["allergens_missing"]) is False
    assert by_code(res, "1005")["allergens"] == ""  # vide avec ingrédients : « aucun déclaré »
    assert report.details["none_declared"] > 0


def test_handle_allergens_unknown_tordu():
    df = small(
        allergens=[None, "", "", "en:milk"],
        ingredients_text=["eau", None, "eau", None],
    )
    res, report = cleaning.handle_allergens_unknown(df)
    assert list(res["allergens_missing"]) == [True, True, False, False]
    assert pd.isna(res["allergens"].iloc[1])      # vide sans ingrédients -> NA
    assert res["allergens"].iloc[2] == ""         # vide avec ingrédients : conservé
    assert report.details["empty_to_na"] == 1


# =====================================================================
# 11. missing_strategy
# =====================================================================
def test_missing_strategy_nominal(raw):
    res, report = cleaning.missing_strategy(raw)
    assert "fiber_100g_missing" in res.columns
    assert res["fiber_100g_missing"].dtype == "boolean"
    assert report.details["flags_set"] > 0
    # jamais d'imputation : les valeurs sont inchangées
    assert_frame_equal(res[raw.columns], raw, check_dtype=False)


def test_missing_strategy_constante_et_suppression():
    df = small(a=[1.0, NA], b=["x", "y"])
    res, report = cleaning.missing_strategy(df, {"a": "constant:0", "b": "drop_column"})
    assert list(res["a"]) == [1.0, 0.0]
    assert "b" not in res.columns
    assert report.rows_touched == 1


def test_missing_strategy_decision_inconnue_leve_valueerror():
    with pytest.raises(ValueError):
        cleaning.missing_strategy(small(a=[1.0]), {"a": "inventer"})


def test_missing_strategy_colonne_absente_leve_keyerror():
    with pytest.raises(KeyError):
        cleaning.missing_strategy(small(a=[1.0]), {"zzz": "keep"})


def test_missing_strategy_mediane_differee():
    df = small(a=[1.0, NA])
    res, report = cleaning.missing_strategy(df, {"a": "flag+median_by_group"})
    assert pd.isna(res["a"].iloc[1])  # la médiane est appliquée dans le pipeline ML
    assert list(res["a_missing"]) == [False, True]
    assert report.details["deferred"] == 1


# =====================================================================
# 12. fill_saturated_zero_if_low_fat
# =====================================================================
def test_fill_saturated_zero_if_low_fat_nominal(raw):
    res, report = cleaning.fill_saturated_zero_if_low_fat(raw)
    assert by_code(res, "1010")["saturated_fat_100g"] == 0.0
    assert report.details["set_to_zero"] == 1


def test_fill_saturated_zero_if_low_fat_tordu_seuil():
    df = small(fat_100g=[0.49, 0.5, NA], saturated_fat_100g=[NA, NA, NA])
    res, _ = cleaning.fill_saturated_zero_if_low_fat(df)
    assert res["saturated_fat_100g"].iloc[0] == 0.0
    assert pd.isna(res["saturated_fat_100g"].iloc[1])  # 0,5 exactement : pas en dessous du seuil
    assert pd.isna(res["saturated_fat_100g"].iloc[2])  # lipides inconnus : rien à déduire


# =====================================================================
# 13. fix_inconsistent_energy
# =====================================================================
def test_fix_inconsistent_energy_nominal(raw):
    res, report = cleaning.fix_inconsistent_energy(raw)
    butter = by_code(res, "1014")
    assert butter["energy_kcal_100g"] == pytest.approx(743.2)
    assert butter["energy_kj_100g"] == pytest.approx(743.2 * cleaning.KJ_PER_KCAL, abs=0.1)
    assert report.details["zero_recomputed"] == 1


def test_fix_inconsistent_energy_tordu_alcool_exception(raw):
    res, _ = cleaning.fix_inconsistent_energy(raw)
    assert by_code(res, "1015")["energy_kcal_100g"] == 85.0  # le vin garde son énergie


def test_fix_inconsistent_energy_tordu_recalcul_impossible():
    df = small(
        energy_kcal_100g=[0.0], energy_kj_100g=[0.0], fat_100g=[10.0],
        carbohydrates_100g=[NA], proteins_100g=[NA], food_groups_tag_1=["en:x"],
    )
    res, report = cleaning.fix_inconsistent_energy(df)
    assert pd.isna(res["energy_kcal_100g"].iloc[0])  # 0 kcal avec 10 g de lipides : impossible
    assert pd.isna(res["energy_kj_100g"].iloc[0])    # les kJ, aussi suspects, sont invalidés avec elles
    assert report.details["zero_invalidated"] == 1


def test_fix_inconsistent_energy_tordu_seuil_50_pourcent():
    # calcul 4/4/9 = 100 kcal ; 150 est à 50 % pile (toléré), 151 au-delà
    df = small(
        energy_kcal_100g=[150.0, 151.0], energy_kj_100g=[627.6, 631.8], fat_100g=[0.0, 0.0],
        carbohydrates_100g=[25.0, 25.0], proteins_100g=[0.0, 0.0], food_groups_tag_1=["en:x", "en:x"],
    )
    res, _ = cleaning.fix_inconsistent_energy(df)
    assert res["energy_kcal_100g"].iloc[0] == 150.0
    assert res["energy_kcal_100g"].iloc[1] == 100.0


def test_fix_inconsistent_energy_tordu_kcal_absentes_controlees_via_les_kj():
    # kcal absentes : la règle contrôle les kcal qui seraient tirées des kJ (215 kJ = 51,4 kcal)
    df = small(
        energy_kcal_100g=[NA, NA], energy_kj_100g=[215.0, 0.0], fat_100g=[3.2, 1.0],
        carbohydrates_100g=[40.0, 10.0], proteins_100g=[10.0, 2.0], food_groups_tag_1=["en:x", "en:x"],
    )
    res, report = cleaning.fix_inconsistent_energy(df)
    assert list(res["energy_kcal_100g"]) == [228.8, 57.0]   # 4/4/9 : 160 + 40 + 28.8, puis 40 + 8 + 9
    assert list(res["energy_kj_100g"]) == [957.3, 238.5]
    assert report.rows_touched == 2


def test_fix_inconsistent_energy_tordu_macros_minuscules_rien_ne_change():
    # énergie à 0 et macronutriments minuscules : le 4/4/9 arrondi donne 0,0 kcal, donc aucune valeur ne change
    # (si la ligne était comptée, la seconde passe la compterait encore : idempotence)
    df = small(
        energy_kcal_100g=[0.0], energy_kj_100g=[0.0], fat_100g=[0.001],
        carbohydrates_100g=[0.001], proteins_100g=[0.001], food_groups_tag_1=["en:x"],
    )
    first, report_first = cleaning.fix_inconsistent_energy(df)
    _, report_second = cleaning.fix_inconsistent_energy(first)
    assert list(first["energy_kcal_100g"]) == [0.0]
    assert report_first.rows_touched == 0
    assert report_second.rows_touched == 0


# =====================================================================
# 14. drop_rows_without_key_nutrient
# =====================================================================
def test_drop_rows_without_key_nutrient_nominal(raw):
    res, report = cleaning.drop_rows_without_key_nutrient(raw)
    assert "1011" not in set(res["code"])
    assert report.details["rows_dropped"] == 1


def test_drop_rows_without_key_nutrient_tordu_un_seul_suffit():
    df = small(
        energy_kcal_100g=[NA, NA], energy_kj_100g=[NA, NA], saturated_fat_100g=[NA, NA],
        sugars_100g=[NA, NA], proteins_100g=[NA, NA], salt_100g=[NA, 0.0], sodium_100g=[NA, NA],
    )
    res, _ = cleaning.drop_rows_without_key_nutrient(df)
    assert len(res) == 1  # un zéro est une valeur connue


# =====================================================================
# 15. derive_missing_energy
# =====================================================================
def test_derive_missing_energy_nominal(raw):
    res, report = cleaning.derive_missing_energy(raw)
    assert by_code(res, "1016")["energy_kcal_100g"] == pytest.approx(44.9)
    assert bool(by_code(res, "1016")["energy_kcal_100g_missing"]) is False
    assert report.details["kcal_from_kj"] == 1


def test_derive_missing_energy_tordu_macros_et_reste():
    df = small(
        energy_kcal_100g=[NA, NA, NA], energy_kj_100g=[NA, NA, NA],
        fat_100g=[10.0, NA, NA], carbohydrates_100g=[10.0, 10.0, NA], proteins_100g=[10.0, 10.0, NA],
    )
    res, _ = cleaning.derive_missing_energy(df)
    assert res["energy_kcal_100g"].iloc[0] == 170.0           # 4/4/9 avec les trois macros
    assert pd.isna(res["energy_kcal_100g"].iloc[1])           # un macro manque : pas de calcul
    assert list(res["energy_kcal_100g_missing"]) == [False, True, True]


# =====================================================================
# Pureté et idempotence, sur toutes les règles
# =====================================================================
@pytest.mark.parametrize("rule", RULES, ids=RULE_IDS)
def test_purity_input_untouched(rule, raw):
    before = raw.copy(deep=True)
    rule(raw)
    assert_frame_equal(raw, before)


@pytest.mark.parametrize("rule", RULES, ids=RULE_IDS)
def test_idempotence(rule, raw):
    once, _ = rule(raw)
    twice, report = rule(once)
    assert_frame_equal(once, twice)
    assert report.rows_touched == 0


# =====================================================================
# clean() de bout en bout
# =====================================================================
def test_clean_end_to_end(raw):
    res, reports = cleaning.clean(raw)
    assert len(res) == 15                              # 18 - sans catégorie - sans nutriment - doublon
    assert res["code"].is_unique
    assert not res["code"].str.contains(" ").any()
    for column, (low, high) in cleaning.RANGES.items():
        values = res[column].dropna()
        assert values.between(low, high).all(), column
    assert len(reports) == len(cleaning.RANGES) + 14   # une ligne de rapport par étape


def test_clean_ordre_the_glace_survit_au_filtre_nutriment(raw):
    # lipides < 0,5 g : les saturées passent à 0 avant le filtre « aucun nutriment clé »
    only_fat = small(
        **{column: [NA] for column in raw.columns if column not in ("code", "categories_tags")},
        code=["9"], categories_tags=[["en:x"]],
    )
    only_fat["fat_100g"] = 0.2
    res, _ = cleaning.clean(only_fat)
    assert len(res) == 1


def test_clean_energie_invalidee_sans_autre_nutriment_est_supprimee_des_la_premiere_passe(raw):
    # 0 kcal / 0 kJ avec 10 g de lipides et aucun autre nutriment clé : l'énergie est invalidée,
    # la ligne n'a plus de nutriment clé, et doit disparaître dès le premier passage (idempotence)
    trap = raw.iloc[[0]].copy()
    trap["code"] = "9999"
    for column in ["energy_kcal_100g", "energy_kj_100g", "saturated_fat_100g", "sugars_100g",
                   "proteins_100g", "salt_100g", "sodium_100g", "carbohydrates_100g"]:
        trap[column] = NA
    trap["energy_kcal_100g"] = 0.0
    trap["energy_kj_100g"] = 0.0
    trap["fat_100g"] = 10.0
    res, _ = cleaning.clean(pd.concat([raw, trap], ignore_index=True))
    assert "9999" not in set(res["code"])
    again, _ = cleaning.clean(res)
    assert_frame_equal(res, again)


def test_clean_idempotent_kcal_absentes_derivees_des_kj(raw):
    # kcal absentes + kJ incohérents avec les macronutriments : le contrôle doit avoir lieu dès la première passe
    trap = raw.iloc[[0, 0]].copy().reset_index(drop=True)
    trap["code"] = ["9998", "9999"]
    trap["energy_kcal_100g"] = NA
    trap["energy_kj_100g"] = [215.0, 0.0]
    trap["carbohydrates_100g"] = [40.0, 10.0]
    trap["proteins_100g"] = [10.0, 2.0]
    trap["fat_100g"] = [3.2, 1.0]
    res, _ = cleaning.clean(pd.concat([raw, trap], ignore_index=True))
    again, _ = cleaning.clean(res)
    assert_frame_equal(res, again)


def test_clean_idempotent(raw):
    once, _ = cleaning.clean(raw)
    twice, reports = cleaning.clean(once)
    assert_frame_equal(once, twice)
    assert all(report.rows_touched == 0 and report.rows_before == report.rows_after for report in reports)


# =====================================================================
# Échantillon réel (facultatif : ignoré si le fichier n'existe pas)
# =====================================================================
SAMPLE_PATH = Path(__file__).resolve().parent.parent / "data" / "sample_raw.parquet"  # dossier data/ de la racine


@pytest.mark.skipif(not SAMPLE_PATH.exists(), reason="échantillon réel absent")
def test_clean_idempotent_on_real_sample():
    sample = pd.read_parquet(SAMPLE_PATH)
    once, _ = cleaning.clean(sample)
    twice, reports = cleaning.clean(once)
    assert_frame_equal(once, twice)
    assert all(report.rows_touched == 0 for report in reports)


@pytest.mark.skipif(not SAMPLE_PATH.exists(), reason="échantillon réel absent")
@pytest.mark.parametrize("rule", RULES, ids=RULE_IDS)
def test_idempotence_per_rule_on_real_sample(rule):
    # Chaque règle, seule, deux fois de suite : le même DataFrame et zéro ligne touchée la seconde fois
    sample, _ = cleaning.type_columns(pd.read_parquet(SAMPLE_PATH))
    once, _ = rule(sample)
    twice, report = rule(once)
    assert_frame_equal(once, twice)
    assert report.rows_touched == 0