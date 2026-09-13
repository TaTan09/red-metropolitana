SELECT current_database() AS database_name,
       current_user AS database_user,
       version() AS postgres_version;

SELECT schema_name
FROM information_schema.schemata
WHERE schema_name IN ('staging', 'silver', 'gold', 'control')
ORDER BY schema_name;
