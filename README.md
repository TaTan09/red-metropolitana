# Red Metropolitana — Proyecto 1 de Ciencia de Datos

Repositorio del proyecto de integración de datos de Transmetro, Transurbano, MetroRiel y Aerómetro.

## Arquitectura acordada

```text
Fuentes
  ↓
Ingesta
  ↓
Raw
  ↓
Bronze / Data Lake (Parquet)
  ↓
Staging / PostgreSQL
  ↓
Silver / dbt
  ↓
Gold / dbt
  ↓
Tableau

Silver
  ↓
Features
```

## Primer arranque: PostgreSQL

### 1. Copiar el archivo de variables

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

En Git Bash:

```bash
cp .env.example .env
```

Edita `.env` y cambia `POSTGRES_PASSWORD`.

> `.env` está ignorado por Git y nunca debe subirse.

### 2. Levantar PostgreSQL

```bash
docker compose up -d postgres
```

### 3. Verificar el contenedor

```bash
docker compose ps
```

Debe mostrar `red_metropolitana_postgres` como `healthy`.

### 4. Verificar la base y los esquemas

Git Bash / PowerShell:

```bash
docker exec -it red_metropolitana_postgres psql -U red_user -d red_metropolitana
```

Dentro de `psql`:

```sql
\dn
```

Deben existir al menos:

- `staging`
- `silver`
- `gold`
- `control`

Para salir:

```text
\q
```

## Nota sobre los scripts de inicialización

Los archivos de `sql/init/` se ejecutan automáticamente únicamente cuando PostgreSQL crea un volumen vacío.

Si se modifica un script de `sql/init/` después del primer arranque, no se volverá a ejecutar por sí solo.

## Datos

Los archivos grandes NO se suben al repositorio.

Colocar los datos oficiales en:

```text
data/raw/
```

Luego el pipeline de ingesta generará Bronze en:

```text
data/bronze/
```

## Reglas que no se pueden romper

- Gold nunca lee Bronze directamente.
- Los registros inválidos se conservan con trazabilidad/cuarentena.
- Las features salen de Silver.
- El pipeline debe ser idempotente.
- No subir credenciales reales.
- Seudonimizar la identidad antes de Gold.

## Métricas de la Capa Silver (Fase 1)

- **Volumen Procesado en Silver:**
  - `silver_transmetro_validaciones`: 362,106 registros
  - `silver_transurbano_transacciones`: 827,788 registros
  - `silver_metroriel_viajes`: 295,511 registros
  - `silver_aerometro_boardings`: 203,554 registros
- **Cuarentena:** 9,710 violaciones de reglas correspondientes a 9,707 registros únicos; tres registros infringen dos reglas.
- **Identidades Únicas en Bridge:** 117,203 llaves resueltas en `silver.bridge_identidad_usuario`.
- **Padrón Transmetro:** 17,432 tarjetas totales; 15,096 activas y 2,336 inactivas. `silver.silver_padron_transmetro_scd2` conserva una versión por evento CDC.

## Reconstrucción de Fase 1

Desde la raíz del repositorio, con el entorno virtual activo y `.env` configurado:

```powershell
pip install -r requirements.txt
docker compose up -d postgres
python ingestion/batch/ingest_batch_to_bronze.py
python ingestion/cdc/process_cdc.py
# Consumir antes los topics Transmetro y Aerómetro hasta completar Bronze.
python scripts/cargar_tablas_base_pg.py
python scripts/run_dbt.py build --select path:models/silver path:models/staging
```

La carga de Staging lee únicamente Parquet de `data/bronze`, reconstruye las 13 tablas del contrato en una transacción y verifica los conteos. Para reproducir los conteos publicados se necesitan los Parquet completos de las nueve fuentes, incluidos los dos consumidores Kafka. El script de CDC también carga sus dos tablas Staging desde su Parquet Bronze. Repetir la carga con los mismos Parquet produce los mismos registros y conteos.

Silver lee exclusivamente `source('staging')`. `scripts/run_dbt.py` carga las variables de `.env` para el perfil dbt sin guardar credenciales en Git. Las pruebas dbt comprueban que el último estado SCD2 coincide con el padrón actual y que las vigencias por secuencia no se solapan. Gold y Prefect quedan para su fase correspondiente.
