-- JOIN statements allow you to grow your SQL query results HORIZONTALLY, by attaching extra columns to the returned data.
-- INNER JOIN (or simply JOIN) only selects rows when data exists in *both* tables.
-- LEFT JOIN fetches every row from the first (left) table, regardless of finding a match in the second (right) table. Missing match data columns will be set to NULL.
-- RIGHT JOIN is the same but with data from the second (right) table, with potential NULL (missing data) from the first (left) table.

-- The SQL clause order for JOINs is:
-- SELECT
-- FROM
-- (LEFT|RIGHT|INNER) JOIN
-- WHERE
-- ORDER BY

-- For Example:
SELECT
    obj1.*,
    obj2.extraField,
FROM schema_name.table1 AS obj1
LEFT JOIN schema_name.table2 as obj2
    ON obj1.some_id = obj2.id_even_if_named_differently
WHERE obj1.field_a = 100
    AND COALESCE(obj1.some_name, '') NOT LIKE "MISSING%"
    AND NULLIF(TRIM(obj1.other_name), '') IS NOT NULL
ORDER BY
    obj1.some_id,
    obj1.some_name,
    obj2.color;
