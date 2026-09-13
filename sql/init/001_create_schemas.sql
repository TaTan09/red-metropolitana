-- Se ejecuta automáticamente SOLO cuando PostgreSQL crea el volumen por primera vez.
-- Bronze no vive aquí: Bronze está en el data lake local (data/bronze).

CREATE SCHEMA IF NOT EXISTS staging;
CREATE SCHEMA IF NOT EXISTS silver;
CREATE SCHEMA IF NOT EXISTS gold;
CREATE SCHEMA IF NOT EXISTS control;

COMMENT ON SCHEMA staging IS 'Datos temporales/cercanos a la fuente para el pipeline.';
COMMENT ON SCHEMA silver  IS 'Datos integrados, normalizados, historizados y con calidad aplicada.';
COMMENT ON SCHEMA gold    IS 'Modelo dimensional y objetos para Tableau.';
COMMENT ON SCHEMA control IS 'Metadatos de ingesta, idempotencia, auditoría y métricas del pipeline.';
