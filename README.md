# Red Metropolitana — Proyecto 1 de Ciencia de Datos

Repositorio del proyecto de integración de datos de Transmetro, Transurbano, MetroRiel y Aerómetro.

Para ejecutar el proyecto desde cero en otra computadora, ver [docs/GUIA_EJECUCION_EQUIPO.md](docs/GUIA_EJECUCION_EQUIPO.md).

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

Edita `.env` y cambia `POSTGRES_PASSWORD` y `GOLD_PSEUDONYM_KEY`. Para habilitar el rol BI, sustituye también la plantilla `TABLEAU_RO_PASSWORD` por un valor privado de al menos 16 caracteres; si todavía no vas a habilitar LOGIN, elimina esa línea de tu `.env` local. El script rechaza la contraseña de plantilla.

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
- Tableau se conecta a las vistas `v_tableau_*` de Gold, no a los marts ni a otras capas.

## Métricas de la Capa Silver (Fase 1)

- **Volumen Procesado en Silver:**
  - `silver_transmetro_validaciones`: 362,106 registros
  - `silver_transurbano_transacciones`: 827,788 registros
  - `silver_metroriel_viajes`: 295,511 registros
  - `silver_aerometro_boardings`: 203,554 registros
- **Cuarentena:** 9,710 violaciones de reglas correspondientes a 9,707 registros únicos; tres registros infringen dos reglas.
- **Identidades Únicas en Bridge:** 117,203 llaves resueltas en `silver.bridge_identidad_usuario`.
- **Padrón Transmetro:** 17,432 tarjetas totales; 15,096 activas y 2,336 inactivas. `silver.silver_padron_transmetro_scd2` conserva una versión por evento CDC.

## Reconstrucción manual hasta Silver (opcional)

Esta ruta sirve para depurar manualmente las capas previas. Para reproducir y demostrar todo el proyecto, use el flujo Prefect de **Ejecución completa del proyecto**.

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

### Marts y vistas para Tableau

Sobre los hechos y dimensiones hay cuatro marts y seis vistas finales:

- `gold.mart_demanda_hora`: demanda por fecha × hora × modo × zona.
- `gold.mart_cobertura`: una fila por zona de `dim_zona` (16), con la oferta (puntos totales y por modo) y la actividad observada.
- `gold.mart_metroriel_zonas`: demanda y oferta en el trazado MR, con ranking frente al universo de la red.
- `gold.mart_multimodalidad`: pares consecutivos de eventos en distintos modos, separados por >0 y <=90 minutos; transbordos inferidos, no físicamente confirmados.
- Vistas Tableau: `gold.v_tableau_demanda_abordajes`, `gold.v_tableau_demanda_viajes_mr`, `gold.v_tableau_cobertura`, `gold.v_tableau_metroriel`, `gold.v_tableau_multimodalidad` y `gold.v_tableau_transbordos`.

El workbook final está versionado en [tableau/workbook/Red_Metropolitana_Fase2.twbx](tableau/workbook/Red_Metropolitana_Fase2.twbx). El TWBX referencia cinco vistas (las de demanda, cobertura, MetroRiel y multimodalidad); `v_tableau_transbordos` está disponible como análisis adicional. Sus cinco conexiones PostgreSQL usan `tableau_ro`: la migración manual fue validada en Tableau y el archivo se guardó y reabrió correctamente. La inspección del XML confirma ese usuario sin contraseñas ni tokens guardados; PostgreSQL confirma LOGIN y lectura Gold, con denegación Staging/Silver. Ver [estado y procedimiento reproducible](docs/seguridad/tableau_ro.md).

**Tableau se conecta a las vistas, no a los marts.** `mart_demanda_hora` mezcla abordajes (Transmetro, Transurbano, Aerómetro) y viajes (MetroRiel) en `cantidad_eventos`; las vistas los separan para que no se sumen por error. MetroRiel cuenta una vez por viaje, en la zona de origen, y las vistas lo nombran así (`zona_origen`, `viajes_iniciados`).

Para reconstruirlos:

```powershell
python scripts/run_dbt.py build --select mart_demanda_hora mart_cobertura mart_metroriel_zonas mart_multimodalidad v_tableau_demanda_abordajes v_tableau_demanda_viajes_mr v_tableau_cobertura v_tableau_metroriel v_tableau_multimodalidad v_tableau_transbordos --threads 1
```

Documentación: [marts y vistas](docs/arquitectura/marts_gold.md), [decisiones de Fase 2](docs/decisiones/002-fase2-marts.md), [corrección de zonas](docs/evidencias/004-correccion-zonas.md) y [métricas de rendimiento](docs/metricas/rendimiento_fase2.md).

## Ejecución completa del proyecto

Desde la raíz del repositorio, coloca los nueve archivos oficiales en `data/raw/` y configura `.env` a partir de `.env.example`: contraseña PostgreSQL, host/puerto y una `GOLD_PSEUDONYM_KEY` privada y estable de al menos 32 bytes. Activa el entorno virtual e instala las dependencias:

```powershell
pip install -r requirements.txt
docker compose up -d
python orchestration/flows/fase1_pipeline.py --evidence-prefix 006-defensa
```

El comando inicia localmente el flujo Prefect **dos veces** para demostrar idempotencia. En cada corrida valida PostgreSQL/Kafka, ingiere Batch y CDC a Bronze Parquet, publica y consume ambos CSV por Kafka, reconstruye las 13 tablas Staging, ejecuta `python scripts/run_dbt.py build` (Silver, Gold y pruebas) y consulta los conteos finales. Los consumidores terminan tras 15 segundos sin mensajes, con un límite de 30 minutos por proceso; una etapa fallida detiene el flujo.

El flujo no borra Bronze, el estado de deduplicación ni volúmenes. Compara SHA-256 Raw, filas por Parquet, 13 tablas Staging, diez relaciones Silver, doce dimensiones/hechos/marts Gold y las seis vistas Tableau. Captura además fingerprints deterministas de contenido de negocio de Silver/Gold/vistas; cada relación conserva su grano. Sólo excluye `bridge_identidad_usuario.fecha_proceso` y `silver_cuarentena.fecha_deteccion`, auditoría dependiente de ejecución. No se afirma igualdad byte a byte de esas tablas. Termina con error si el estado relevante cambia o difiere de la referencia Gold aprobada.

`--evidence-prefix` es obligatorio y no tiene default. El ejemplo produce `docs/evidencias/006-defensa-corrida-1.json`, `006-defensa-corrida-2.json` y `006-defensa-idempotencia.md`. Si algún destino existe, aborta antes del flujo; usa un prefijo nuevo para cada demostración. `--overwrite` permite reemplazar explícitamente destinos, pero no es el uso habitual. Cada build captura su `target/run_results.json` y diferencia pruebas PASS, modelos/hook success, warnings, errores y skips, sin totales fijos.

La [evidencia 003](docs/evidencias/003-idempotencia-flujo-completo.md) es histórica de Fase 1 y se conserva. La [evidencia 005](docs/evidencias/005-idempotencia-final-fase2.md) documenta las dos corridas completas finales del proyecto/Fase 2: IGUALES y referencia Gold OK. El resumen recuperado de la segunda corrida respalda 158 pruebas PASS +30 modelos success +1 hook success (189 resultados). El JSON de la primera no contiene ese desglose; su alcance está explicado en el reporte. La segunda publicación Kafka puede ser duplicado técnico por `_event_id` sin añadir filas a Bronze.

Si falla la segunda ejecución después de guardar la primera, usa `python orchestration/flows/fase1_pipeline.py --evidence-prefix 006-defensa --resume-second`. Conserva la primera del mismo prefijo y repite sólo la segunda. Si ya existen la segunda o el reporte, requiere un prefijo nuevo o `--overwrite` explícito. Evidencias del formato antiguo (003/005, sin la cobertura ampliada) no se reanudan con esta CLI: no rellenar métricas históricas ausentes.

Si `.env` utiliza otro puerto local de PostgreSQL, `docker compose` lo respeta con `POSTGRES_PORT`. El broker Kafka se configura opcionalmente con `KAFKA_BOOTSTRAP_SERVERS` (predeterminado `localhost:9092`). Prefect arranca su servidor temporal local automáticamente; no hay que levantar manualmente Prefect Server ni usar Prefect Cloud.

Para repetir únicamente las pruebas dbt en un Docker con poca memoria compartida, usa `python scripts/run_dbt.py test --threads 1`.

PostgreSQL declara `shm_size: "1gb"` para evitar el agotamiento histórico de los 64 MB de `/dev/shm` con paralelismo. Esta edición no recrea contenedores ni volúmenes; aplicar la definición requiere posteriormente recrear sólo el contenedor conservando `postgres_data`, nunca `docker compose down -v`.

Antes de futuras demostraciones, se recomienda revisar y crear manualmente un tag como `fase1-validada` en el commit histórico validado. Este cleanup no crea tags ni hace push; la protección principal es el prefijo obligatorio y el rechazo de sobrescritura.


### Multimodalidad y features (revision Fase 2)

- `gold.v_tableau_multimodalidad`: usuarios observados por cantidad de modos y metodo; KPI multimodal = modos_observados >1. Totales globales repetidos: MIN/MAX en Tableau.
- `gold.mart_multimodalidad` y `gold.v_tableau_transbordos`: pares consecutivos inferidos >0 y <=90 minutos; trazabilidad de ambos registros Bronze.
- `silver.silver_features_usuario`: features exclusivamente Silver, cutoff maximo real guardado en cada fila, ventanas 7/30/90 dias, recencia, modo/zona frecuentes, hora pico y tarifas. Ver [diccionario y fecha de corte](docs/features_usuario.md).

Aerómetro permanece aislado: sus enlaces persona-a-persona con los otros modos no son medibles. TM/TU/MR se enlazan por una inferencia académica de patrón numérico, no identidad personal confirmada. Resultado aprobado: 70,380 usuarios observados, 36,827 multimodales (52.33 %); 1,393,448 abordajes TM/TU/AM y, por separado, 295,511 viajes completos MR. Santa Catarina Pinula no tiene puntos de servicio en el catálogo; no demuestra ausencia de transporte fuera del dataset.

```powershell
python scripts/run_dbt.py parse
python scripts/run_dbt.py build --select +silver_features_usuario +mart_multimodalidad v_tableau_transbordos +v_tableau_multimodalidad --threads 1
python scripts/run_dbt.py test --select path:models/silver --threads 1
python scripts/run_dbt.py test --select path:models/gold --threads 1
python scripts/run_dbt.py docs generate
python scripts/validar_raw.py --raw-dir datos_red
python scripts/configurar_tableau_ro.py
```

`datos_red/` está ignorado y se conserva localmente; las ingestas existentes usan `data/raw/`. En un entorno nuevo, el provisionamiento de `tableau_ro` crea NOLOGIN si no recibe una contraseña privada mediante `TABLEAU_RO_PASSWORD`. En el entorno validado ya tiene LOGIN y las cinco conexiones del workbook usan ese rol. No se guardan contraseñas en Git. Ver [seguridad y estado RBAC](docs/seguridad/seguridad_y_datos_personales.md) y [validación histórica de Fase 2](docs/metricas/validacion_fase2.md).

Nota de alcance: el prefijo protege los JSON/reportes de `docs/evidencias`. Los scripts de ingesta todavía actualizan sus reportes auxiliares de `docs/metricas`; esos archivos no son snapshots inmutables. Para una demostración futura, revisar ese diff antes de integrar cambios y no sustituir evidencias históricas aprobadas por métricas recién generadas. Este cleanup no ejecutó ingestas ni cambió esos reportes.
