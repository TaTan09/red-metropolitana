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

Silver lee exclusivamente `source('staging')`. `scripts/run_dbt.py` carga las variables de `.env` para el perfil dbt sin guardar credenciales en Git. Las pruebas dbt comprueban que el último estado SCD2 coincide con el padrón actual y que las vigencias por secuencia no se solapan.

## Capa Gold dimensional

La rama `feature/gold-dimensional` añade seis dimensiones, `fact_abordajes` para Transmetro/Transurbano/Aerómetro y `fact_viajes_metroriel` para viajes completos. Gold consume únicamente modelos Silver. El [diseño, matriz del bus y reglas](docs/arquitectura/modelo_dimensional_gold.md) y las [métricas medidas](docs/metricas/gold_metricas.md) documentan el resultado.

Configura en `.env` una `GOLD_PSEUDONYM_KEY` aleatoria de al menos 32 bytes y consérvala estable. Se usa para seudonimizar las claves de usuario mediante HMAC-SHA256; **no la subas a Git**. Puedes generar un valor hexadecimal con `python -c "import secrets; print(secrets.token_hex(32))"` y pegarlo en `.env`.

Con PostgreSQL y Staging cargados:

```powershell
python scripts/run_dbt.py build
```

El build crea Silver y Gold y ejecuta pruebas de claves, relaciones y conteos. El [DDL](sql/ddl/gold_model.sql) es el entregable estructural de referencia; dbt materializa las tablas.

## Ejecución completa de Fase 1

Desde la raíz del repositorio, coloca los nueve archivos oficiales en `data/raw/` y configura `.env` a partir de `.env.example`: contraseña PostgreSQL, host/puerto y una `GOLD_PSEUDONYM_KEY` privada y estable de al menos 32 bytes. Activa el entorno virtual e instala las dependencias:

```powershell
pip install -r requirements.txt
docker compose up -d
python orchestration/flows/fase1_pipeline.py
```

El comando inicia localmente el flujo Prefect **dos veces** para demostrar idempotencia. En cada corrida valida PostgreSQL/Kafka, ingiere Batch y CDC a Bronze Parquet, publica y consume ambos CSV por Kafka, reconstruye las 13 tablas Staging, ejecuta `python scripts/run_dbt.py build` (Silver, Gold y pruebas) y consulta los conteos finales. Los consumidores terminan tras 15 segundos sin mensajes, con un límite de 30 minutos por proceso; una etapa fallida detiene el flujo.

El flujo no borra Bronze, el estado de deduplicación ni volúmenes. Compara SHA-256 de Raw, filas por archivo Parquet y los conteos de Staging, Silver y Gold; termina con error si cambian. Repetir las mismas fuentes debe dejar igual el estado analítico final. Los JSON de cada corrida y el resultado legible se guardan en [la evidencia de idempotencia](docs/evidencias/003-idempotencia-flujo-completo.md). La segunda publicación Kafka puede consumirse como duplicado técnico por `_event_id` sin añadir filas a Bronze.

Si falla la segunda ejecución después de guardarse `003-corrida-1.json`, corrige la causa y usa `python orchestration/flows/fase1_pipeline.py --resume-second` para repetir únicamente esa corrida y compararla con la primera.

Si `.env` utiliza otro puerto local de PostgreSQL, `docker compose` lo respeta con `POSTGRES_PORT`. El broker Kafka se configura opcionalmente con `KAFKA_BOOTSTRAP_SERVERS` (predeterminado `localhost:9092`). Prefect arranca su servidor temporal local automáticamente; no hay que levantar manualmente Prefect Server ni usar Prefect Cloud.

Para repetir únicamente las pruebas dbt en un Docker con poca memoria compartida, usa `python scripts/run_dbt.py test --threads 1`.
