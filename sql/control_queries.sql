SELECT * FROM
    (SELECT COUNT(*) AS products FROM products) p,
    (SELECT COUNT(*) AS brands FROM brands) b,
    (SELECT COUNT(*) AS categories FROM categories) c,
    (SELECT COUNT(*) AS products_categories FROM products_categories) pc;

SELECT count(*) nbre FROM products p
LEFT JOIN products_categories pc ON pc.product_id = p.code
WHERE pc.product_id IS NULL;

SELECT b.name, count(*) nbre FROM brands b
INNER JOIN products p ON p.brand_id = b.id
GROUP BY b.id
ORDER BY nbre DESC
LIMIT 11;

SELECT t1.name, t2.nb, t1.tot, ((t2.nb * 100.0) / (t1.tot * 100.0)) * 100.0 as cpl FROM
(
	SELECT count(*) tot, pc.category_id, c.name FROM categories c
	INNER JOIN products_categories pc ON pc.category_id = c.id
	INNER JOIN products p ON p.code = pc.product_id
	GROUP BY pc.category_id, c.name
) t1
INNER JOIN (
	SELECT count(*) nb, pc.category_id, c.name FROM categories c
	INNER JOIN products_categories pc ON pc.category_id = c.id
	INNER JOIN products p ON p.code = pc.product_id
	WHERE p.nutriscore IS NOT NULL
	GROUP BY pc.category_id, c.name
) t2 ON t1.category_id = t2.category_id
ORDER BY tot DESC;


SELECT t1.name, t2.nb, t1.tot, (t2.nb * 100.0) / t1.tot as cpl FROM
(
	SELECT count(*) tot, pc.category_id, c.name FROM categories c
	INNER JOIN products_categories pc ON pc.category_id = c.id
	INNER JOIN products p ON p.code = pc.product_id
	GROUP BY pc.category_id, c.name
) t1
INNER JOIN (
	SELECT count(*) nb, pc.category_id, c.name FROM categories c
	INNER JOIN products_categories pc ON pc.category_id = c.id
	INNER JOIN products p ON p.code = pc.product_id
	WHERE p.nutriscore IS NOT NULL
	GROUP BY pc.category_id, c.name
) t2 ON t1.category_id = t2.category_id
ORDER BY tot DESC;
