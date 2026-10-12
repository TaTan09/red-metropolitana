-- Ejecutar con el propietario de las relaciones Gold (red_user en este entorno).
-- Transacción gestionada por scripts/configurar_tableau_ro.py; ninguna contraseña.
DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tableau_ro') THEN
        CREATE ROLE tableau_ro NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOREPLICATION NOBYPASSRLS;
    END IF;
    IF EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'tableau_ro'
               AND (rolsuper OR rolcreatedb OR rolcreaterole OR rolreplication OR rolbypassrls))
       OR EXISTS (SELECT 1 FROM pg_auth_members m JOIN pg_roles r ON r.oid = m.member
                  WHERE r.rolname = 'tableau_ro') THEN
        RAISE EXCEPTION 'tableau_ro existente tiene privilegios elevados/membresías; no se modifica automáticamente';
    END IF;
    IF current_database() <> 'red_metropolitana' THEN
        RAISE EXCEPTION 'Ejecutar sólo en red_metropolitana';
    END IF;
    IF EXISTS (SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
               WHERE n.nspname = 'gold' AND c.relkind IN ('r','v','m','p','f')
                 AND c.relowner <> (SELECT oid FROM pg_roles WHERE rolname = current_user)) THEN
        RAISE EXCEPTION 'Ejecutar como propietario de todas las relaciones Gold para cubrir sus default privileges';
    END IF;
END $$;

GRANT CONNECT ON DATABASE red_metropolitana TO tableau_ro;
GRANT USAGE ON SCHEMA gold TO tableau_ro;
GRANT SELECT ON ALL TABLES IN SCHEMA gold TO tableau_ro;
ALTER DEFAULT PRIVILEGES IN SCHEMA gold GRANT SELECT ON TABLES TO tableau_ro;

-- No cambiar PUBLIC ni roles de otros usuarios. Si hay accesos heredados que
-- vulneran la política, abortar y revertir la transacción completa.
DO $$
BEGIN
    IF has_schema_privilege('tableau_ro', 'staging', 'USAGE')
       OR has_schema_privilege('tableau_ro', 'silver', 'USAGE')
       OR has_schema_privilege('tableau_ro', 'control', 'USAGE') THEN
        RAISE EXCEPTION 'tableau_ro hereda acceso a otra capa; revisar ACL sin afectar usuarios existentes';
    END IF;
    IF EXISTS (
        SELECT 1 FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
        WHERE n.nspname IN ('staging','silver','control') AND c.relkind IN ('r','v','m','p','f')
          AND has_table_privilege('tableau_ro', c.oid, 'SELECT')
    ) THEN
        RAISE EXCEPTION 'tableau_ro hereda SELECT fuera de Gold';
    END IF;
END $$;
