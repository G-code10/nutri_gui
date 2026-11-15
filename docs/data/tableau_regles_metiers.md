<style>
  table.regles {
    border-collapse: collapse;
    width: 100%;
    min-width: 1100px;
    font-size: 14px;
    line-height: 1.45;
  }
  table.regles th,
  table.regles td {
    border: 1px solid rgba(127, 127, 127, 0.35);
    padding: 8px 12px;
    vertical-align: top;
    text-align: left;
  }
  table.regles thead th {
    background: rgba(127, 127, 127, 0.18);
  }
  table.regles tbody tr { background: transparent; }
  table.regles tbody tr:nth-child(even) { background: rgba(127, 127, 127, 0.07); }
  table.regles td:first-child { text-align: center; white-space: nowrap; }
  table.regles td:nth-child(3) { white-space: nowrap; }
  table.regles td:last-child code { white-space: nowrap; }
  table.regles code {
    font-size: 12.5px;
    background: rgba(127, 127, 127, 0.15);
    padding: 1px 4px;
    border-radius: 3px;
  }
</style>

<table class="regles">
  <colgroup>
    <col style="width: 3%">
    <col style="width: 19%">
    <col style="width: 11%">
    <col style="width: 25%">
    <col style="width: 26%">
    <col style="width: 16%">
  </colgroup>
  <thead>
    <tr>
      <th width="3%">#</th>
      <th width="19%">Règle</th>
      <th width="11%">Source / Type</th>
      <th width="25%">Colonne visée</th>
      <th width="26%">Traitement</th>
      <th width="16%">Méthode</th>
    </tr>
  </thead>
  <tbody>
    <tr>
      <td>1</td>
      <td>Types de colonnes (float, string)</td>
      <td>TP9 · typage</td>
      <td>nutriments (float64), <code>code</code>, <code>product_name</code>, <code>brands</code>, <code>ingredients_text</code>, <code>allergens</code>, <code>serving_size</code> (string)</td>
      <td>conversion vers dtypes nullables ; non convertible → NA</td>
      <td><code>type_columns</code></td>
    </tr>
    <tr>
      <td>2</td>
      <td>Textes vides, noms en MAJUSCULES, marques de graphies variées, espaces dans le code</td>
      <td>TP9 · texte</td>
      <td><code>product_name</code>, <code>brands</code>, <code>ingredients_text</code>, <code>serving_size</code>, <code>code</code></td>
      <td>vides → NA ; noms corrigés (≥ 4 lettres) ; graphie de marque unifiée ; code sans espaces</td>
      <td><code>normalize_texts</code></td>
    </tr>
    <tr>
      <td>3</td>
      <td>Code absent ou en double</td>
      <td>TP9 · identifiant</td>
      <td><code>code</code> (départage : <code>completeness</code>, <code>last_modified_t</code>)</td>
      <td>lignes sans code supprimées ; une seule fiche par code : la plus complète, puis la plus récente</td>
      <td><code>enforce_unique_code</code></td>
    </tr>
    <tr>
      <td>4</td>
      <td>Nutri-Score « unknown » ou « not-applicable »</td>
      <td>métier · manquant + drapeau</td>
      <td><code>nutriscore_grade</code> (drapeau <code>grade_not_applicable</code>)</td>
      <td>drapeau posé avant l'effacement ; les deux grades → NA</td>
      <td><code>normalize_grade</code></td>
    </tr>
    <tr>
      <td>5</td>
      <td>Produit inclassable (catégories NULL ou liste vide)</td>
      <td>TP9 · suppression</td>
      <td><code>categories_tags</code></td>
      <td>suppression de la ligne</td>
      <td><code>drop_unclassifiable</code></td>
    </tr>
    <tr>
      <td>6</td>
      <td>Valeurs hors plage (0–100 g ; énergie 0–900 kcal / 3765,6 kJ ; sodium 0–40)</td>
      <td>métier · borne</td>
      <td><code>fat_100g</code>, <code>saturated_fat_100g</code>, <code>carbohydrates_100g</code>, <code>sugars_100g</code>, <code>fiber_100g</code>, <code>proteins_100g</code>, <code>salt_100g</code>, <code>sodium_100g</code>, <code>fruits_vegetables_legumes_100g</code>, <code>energy_kcal_100g</code>, <code>energy_kj_100g</code></td>
      <td>→ NA, sans drapeau</td>
      <td><code>neutralize_range</code> (boucle sur <code>RANGES</code>)</td>
    </tr>
    <tr>
      <td>7</td>
      <td>sucres &gt; glucides + 0,5 ; saturées &gt; lipides + 0,5</td>
      <td>métier · cohérence</td>
      <td><code>sugars_100g</code> (borne : <code>carbohydrates_100g</code>), <code>saturated_fat_100g</code> (borne : <code>fat_100g</code>)</td>
      <td>sous-partie → NA, total inchangé</td>
      <td><code>neutralize_subpart_above_total</code></td>
    </tr>
    <tr>
      <td>8</td>
      <td>Allergènes NULL ou vide sans ingrédients</td>
      <td>métier · manquant + drapeau</td>
      <td><code>allergens</code> (drapeau <code>allergens_missing</code>, lit <code>ingredients_text</code>)</td>
      <td>drapeau ; vide sans ingrédients → NA ; vide avec ingrédients = « aucun déclaré »</td>
      <td><code>handle_allergens_unknown</code></td>
    </tr>
    <tr>
      <td>9</td>
      <td>Stratégie de valeurs manquantes (jamais imputer)</td>
      <td>TP9 · stratégie</td>
      <td>toutes les colonnes de <code>DEFAULT_MISSING_STRATEGY</code> (drapeaux <code>&lt;col&gt;_missing</code>)</td>
      <td>drapeaux, constantes, <code>drop_column</code> ; médiane et mode différés</td>
      <td><code>missing_strategy</code></td>
    </tr>
    <tr>
      <td>10</td>
      <td>lipides &lt; 0,5 g</td>
      <td>métier · dérivation</td>
      <td><code>saturated_fat_100g</code> (lit <code>fat_100g</code>)</td>
      <td>saturées = 0</td>
      <td><code>fill_saturated_zero_if_low_fat</code></td>
    </tr>
    <tr>
      <td>11</td>
      <td>Aucun nutriment clé</td>
      <td>métier · suppression</td>
      <td><code>energy_kcal_100g</code>, <code>energy_kj_100g</code>, <code>saturated_fat_100g</code>, <code>sugars_100g</code>, <code>proteins_100g</code>, <code>salt_100g</code>, <code>sodium_100g</code></td>
      <td>suppression de la ligne</td>
      <td><code>drop_rows_without_key_nutrient</code></td>
    </tr>
    <tr>
      <td>12</td>
      <td>Sel et sodium incohérents ou manquants</td>
      <td>métier · cohérence + dérivation</td>
      <td><code>salt_100g</code>, <code>sodium_100g</code></td>
      <td>écart &gt; 0,1 : sodium recalculé depuis le sel ; manquant : sel = sodium × 2,5 ou sodium = sel / 2,5</td>
      <td><code>reconcile_salt_sodium</code></td>
    </tr>
    <tr>
      <td>13</td>
      <td>rapport kJ/kcal hors [3,9 ; 4,5]</td>
      <td>TP9 · cohérence</td>
      <td><code>energy_kcal_100g</code> (lit <code>energy_kj_100g</code>)</td>
      <td>kcal recalculé depuis le kJ</td>
      <td><code>reconcile_kcal_kj</code></td>
    </tr>
    <tr>
      <td>14</td>
      <td>énergie nulle avec macros non nulles, ou écart &gt; 50 % avec 4/4/9 (calc ≥ 50 kcal)</td>
      <td>TP9 + métier · cohérence</td>
      <td><code>energy_kcal_100g</code>, <code>energy_kj_100g</code> (lit <code>fat_100g</code>, <code>carbohydrates_100g</code>, <code>proteins_100g</code>, <code>food_groups_tag_1</code>)</td>
      <td>recalcul 4/4/9 et kJ réalignés ; recalcul impossible → kcal en NA ; boissons alcoolisées exclues</td>
      <td><code>fix_inconsistent_energy</code></td>
    </tr>
    <tr>
      <td>15</td>
      <td>kcal absent</td>
      <td>métier · dérivation + drapeau</td>
      <td><code>energy_kcal_100g</code> (drapeau <code>energy_kcal_100g_missing</code>)</td>
      <td>kcal = kJ / 4,184, sinon 4/4/9 ; reste → drapeau</td>
      <td><code>derive_missing_energy</code></td>
    </tr>
    <tr>
      <td>—</td>
      <td>Médiane par <code>food_groups_tag_1</code> (énergie, lipides, protéines)</td>
      <td>métier · imputation</td>
      <td><code>energy_kcal_100g</code>, <code>fat_100g</code>, <code>proteins_100g</code></td>
      <td>calculée sur le train après le split (hors <code>cleaning.py</code>)</td>
      <td><code>median_by_food_group_after_split</code></td>
    </tr>
    <tr>
      <td>—</td>
      <td>Orchestration de toutes les règles</td>
      <td>TP9 · orchestrateur</td>
      <td>—</td>
      <td>exécution dans l'ordre 1 → 15, liste de <code>RuleReport</code></td>
      <td><code>clean</code></td>
    </tr>
  </tbody>
</table>