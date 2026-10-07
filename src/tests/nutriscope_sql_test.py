import sys
sys.path.append(".")

import nutriscope_sql
from conf import sql_conf_dict as conf

# ceci est notre référence et ne dois pas bouger sans accord de l'équipe
result = []

# Sortie après création des tables
result.append([('id', 'bigint', 'NO', None)
               , ('name', 'text', 'NO', None)])
result.append([('id', 'bigint', 'NO', None)
               , ('name', 'text', 'NO', None)])
result.append([('code', 'bigint', 'NO', None)
               , ('brand_id', 'bigint', 'NO', None)
               , ('brand', 'text', 'NO', None)
               , ('name', 'text', 'NO', None)
               , ('lang', 'character varying', 'NO', None)
               ,  ('nutriscore', 'double precision', 'YES', None)
               , ('fiber', 'double precision', 'YES', None)
               , ('proteins', 'double precision', 'YES', None)
               , ('energy', 'double precision', 'YES', None)
               , ('saturated_fat', 'double precision', 'YES', None)
               , ('sugars', 'double precision', 'YES', None)
               , ('salt', 'double precision', 'YES', None)])
result.append([('id', 'bigint', 'NO', None)
               , ('category_id', 'bigint', 'NO', None)
               , ('product_id', 'bigint', 'NO', None)])

# Sortie après inser/select d'un produit
result.append([(598745298751, 1, 'Carrouf', 'THE Produit', 'fr', 12.0, 0.5, 1.25, 3350.0, 0.5, 10.0, 42.0)])

# Sortie après inser/select de brands
result.append([(1, 'Sup-per U')
               , (2, 'Carrouf')
               , (3, 'E Lepretre')])

# Sortie de brands après delete des tables
result.append([])

# Sortie de products après delete des tables
result.append([])

tables = ["brands", "categories", "products", "products_categories"]

def check_output(output, test_id):
    reference = result[test_id]
    assert reference == output
    return test_id + 1

"""
    if reference == output:
        print(f"Validation du test {test_id}")
    else:
        print(f"Erreur lors du test {test_id}")
        print(reference)
        print(output)
"""

sql_db_struct = "../sql/postgre_creation.sql"

values = ["Sup-per U", "Carrouf", "E Lepretre", "E Lepretre"]

def test_dsl():
    NSQL = nutriscope_sql.NutriscopeSQL(conf, "simirblaiti")
    NSQL.send_file(sql_db_struct)

    current_test = 0
    for table in tables:
        NSQL.send_query("""SELECT
        column_name,
        data_type,
        is_nullable,
        column_default
    FROM information_schema.columns
    WHERE table_name = %s
    ORDER BY ordinal_position;""", (table,))
        
        current_test = check_output(NSQL.fetch(), current_test)

    for brand in values:
        NSQL.send_query("INSERT INTO brands (name) VALUES (%s);", (brand,))

    NSQL.send_query("INSERT INTO products (code, brand_id, brand, name, lang, nutriscore, fiber, proteins, energy, saturated_fat, sugars, salt) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s);"
                    ,(598745298751, 1, "Carrouf", "THE Produit", "fr", 12.0, 0.5, 1.25, 3350, 0.5, 10, 42,))

    NSQL.send_query("SELECT * from products;")
    current_test = check_output(NSQL.fetch(), current_test)

    NSQL.send_query("SELECT * from brands;")
    current_test = check_output(NSQL.fetch(), current_test)

    NSQL.send_query("DELETE FROM products;")

    for brand in values:
        NSQL.send_query("DELETE FROM brands WHERE name = %s;", (brand,))

    NSQL.send_query("SELECT * from brands;")
    current_test = check_output(NSQL.fetch(), current_test)

    NSQL.send_query("SELECT * from products;")
    current_test = check_output(NSQL.fetch(), current_test)
