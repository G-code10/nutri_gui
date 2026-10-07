import pandas as pd
import pytest
from src.cleaning import flattening_column_join_and_drop

# TODO :
# Pour lancer le test $: py -m pytest
# Si vous lancez avec $: pytest // cela risque de ne pas fonctionner.

def test_flattening_column_join_and_drop():
    """Test the flattening, joining, and dropping pipeline step."""
    
    # 1. ARRANGE : Création d'un faux DataFrame minimaliste
    fake_data = {
        'code': [12345],
        'nutriments': ["ancienne_liste_sale"],
        'flat_nutriments': [{'fiber_100g': 5.0, 'proteins_100g': 12.0, 'energy_100g': 200.0, 'saturated-fat_100g': 1.0, 'sugars_100g': 2.0, 'salt_100g': 0.5}]
    }
    df_mock = pd.DataFrame(fake_data)
    
    # 2. ACT : Appelle ta fonction sur df_mock et stocke le résultat dans df_result
    df_result = flattening_column_join_and_drop(df_mock['flat_nutriments'], df_mock, ['nutriments', 'flat_nutriments'])
    
    # 3. ASSERT : Écris tes vérifications
    assert 'nutriments' not in df_result.columns and 'flat_nutriments' not in df_result.columns
    assert 'fiber_100g' in df_result.columns
    assert df_result['fiber_100g'].iloc[0] == 5.0

test_flattening_column_join_and_drop()