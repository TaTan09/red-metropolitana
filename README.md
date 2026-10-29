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

### Proyecto 2: reconstrucción explícita desde las nuevas fuentes

Con Docker Desktop en ejecución, `.env` configurado y las dependencias instaladas en el entorno virtual, coloca los **nueve archivos nuevos** en `data/raw/` y ejecuta desde la raíz:

```powershell
python orchestration/flows/fase1_pipeline.py --fresh-start --evidence-prefix p2-jonatan-001
```

Este comando es **destructivo para los datos generados del proyecto**. La opción es explícita: el comando normal sin `--fresh-start` sigue ejecutando sus dos corridas sin limpiar estado ni levantar/recrear servicios.

Antes de borrar nada, comprueba los destinos de evidencia y valida que Raw contenga exactamente estos archivos (se permite `.gitkeep`): `tm_estaciones.csv`, `tu_paradas.csv`, `mr_estaciones.csv`, `am_estaciones.csv`, `transmetro_validaciones.csv`, `transurbano_transacciones.csv`, `metroriel_viajes.jsonl`, `aerometro_boardings.csv` y `cdc_padron_usuarios.csv`. Reutiliza el contrato de `scripts/validar_raw.py`: verifica encabezados CSV, llaves/JSON válido en todas las filas JSONL y al menos un registro por fuente. Los conteos históricos de Proyecto 1 no se exigen para las fuentes nuevas. Calcula SHA-256 y registra filas sin modificar Raw.

También valida rutas locales sin enlaces simbólicos/junctions, archivos versionados y la configuración resuelta de Compose. Sólo admite los dos servicios actuales, el volumen local del proyecto `postgres_data`, el montaje de inicialización SQL de sólo lectura, endpoints locales y un daemon Docker local mediante npipe/unix. Si hay archivos versionados distintos de `.gitkeep` en las rutas generadas, archivos no reconocidos como datos/estado en Bronze o cuarentena, montajes adicionales, volúmenes externos/compartidos o servicios adicionales, aborta antes de limpiar. La configuración con contraseñas no se imprime.

La preparación elimina únicamente:

- El contenido generado de `data/bronze/`, incluidos los Parquet, `batch_manifest.json`, `cdc_manifest.json` y `data/bronze/_control/streaming_state.sqlite` con sus archivos auxiliares WAL/SHM.
- El contenido generado de `data/quarantine/`, si existe.
- Los artefactos y cachés de `dbt/red_metropolitana/target/` y los logs de `dbt/red_metropolitana/logs/`, incluido el estado auxiliar `revision_fase2_estado.json`. Conserva las raíces y los `.gitkeep`.
- Los contenedores y volúmenes del Compose de este repositorio mediante `docker compose --file <ruta-del-repositorio>/docker-compose.yml down --volumes`. Se elimina el volumen PostgreSQL `<proyecto-compose>_postgres_data`: **todo el clúster local de ese volumen**, con bases, tablas, esquemas, roles, snapshots e incrementales. Se descartan también los mensajes, topics y offsets del broker Kafka y cualquier volumen anónimo de esos contenedores. No se ejecuta `docker system prune` ni se eliminan imágenes o volúmenes de otros proyectos.

Conserva **todo `data/raw/`**, `datos_red/`, `.env`, código, modelos y definiciones dbt (incluida la carpeta fuente `snapshots/`), SQL de inicialización, documentación, evidencias históricas y archivos Tableau. La limpieza no toca `docs/`. Como en el flujo existente, las ingestas posteriores actualizan sus reportes auxiliares de `docs/metricas/`; esas métricas no son snapshots inmutables.

Después de `down`, comprueba que no queden contenedores del proyecto ni el volumen PostgreSQL anterior; si Docker no pudo retirarlos, aborta para evitar reutilizar datos. Levanta PostgreSQL y Kafka con el mismo Compose, espera su disponibilidad y crea los dos topics existentes con una partición. PostgreSQL ejecuta automáticamente `sql/init/` sobre su volumen nuevo. Luego corre **dos veces el pipeline completo existente**, sin volver a limpiar entre corridas. Los servicios quedan disponibles al finalizar. No se necesita ejecutar manualmente `docker compose up`, crear topics ni reconstruir Staging/dbt por separado.

La primera evidencia JSON incluye `preparacion_fresh_start`, con inventario Raw, volumen PostgreSQL y tiempos de validación, reinicio Docker, limpieza local, arranque, espera y creación de topics. Ambas corridas conservan las mediciones existentes de ingesta, carga Staging, dbt y métricas. El reporte incluye los tiempos de preparación. Para Proyecto 2, Gold se reconcilia contra los conteos Silver del dataset nuevo, además de las pruebas dbt y de la comparación de hashes/conteos/fingerprints entre corridas. La ejecución normal conserva su referencia histórica de Proyecto 1.

**Entregable 1.1: conteos oficiales del Proyecto 2 contra Bronze.** La ejecución de Proyecto 2 no usa los conteos históricos de Proyecto 1, pero sí compara las filas cargadas a Bronze con los valores del LEEME oficial de Proyecto 2:

| archivo | filas_esperadas |
|---|---:|
| aerometro_boardings.csv | 387053 |
| am_estaciones.csv | 14 |
| cdc_padron_usuarios.csv | 77636 |
| metroriel_viajes.jsonl | 590844 |
| mr_estaciones.csv | 22 |
| tm_estaciones.csv | 104 |
| transmetro_validaciones.csv | 713786 |
| transurbano_transacciones.csv | 1635788 |
| tu_paradas.csv | 328 |

Cada JSON `docs/evidencias/<prefijo>-corrida-1.json` y `<prefijo>-corrida-2.json` incorpora `requisito_1_1.tabla`, con exactamente las columnas `archivo`, `filas_esperadas`, `filas_cargadas`, `diferencia`. `filas_cargadas` reutiliza `metricas.bronze[fuente].filas`: la suma de `metadata.num_rows` de todos los Parquet en `data/bronze/<fuente>/fecha_ingesta=*/*.parquet`, medida al final de cada corrida. No equivale a mensajes Kafka consumidos, eventos nuevos de la segunda corrida ni filas aceptadas en Silver. `diferencia = filas_cargadas - filas_esperadas`: un valor negativo indica faltantes y uno positivo indica filas de más.

Los conteos Raw ya disponibles de la validación estructural se guardan aparte en `requisito_1_1.conteos_raw` y en una tabla adicional `archivo`, `filas_raw`; no sustituyen las cuatro columnas obligatorias. Los nueve conteos oficiales constituyen una referencia separada: no se cambia el contrato estructural Raw ni el validador histórico de Proyecto 1.

El reporte `docs/evidencias/<prefijo>-idempotencia.md` incluye las tablas de ambas corridas. También se generan dos Markdown reutilizables para pegar en el informe: `docs/metricas/<prefijo>-requisito-1-1-corrida-1.md` y `docs/metricas/<prefijo>-requisito-1-1-corrida-2.md`. Cada tabla se guarda junto con la evidencia de su corrida, por lo que la primera queda disponible si falla la segunda. Los nuevos Markdown están protegidos por el prefijo y requieren `--overwrite` explícito para reemplazarlos. No se generan en la ejecución normal de Proyecto 1.

Si alguna diferencia no es cero, JSON y Markdown muestran **CON_DIFERENCIAS** y detallan los archivos afectados con su diferencia con signo; también se informa en consola. Las diferencias se conservan para documentar su explicación, sin impedir la segunda corrida. El código de salida sigue comprobando idempotencia y reconciliación Gold/Silver; no debe interpretarse por sí solo como confirmación de que todas las diferencias del requisito 1.1 son cero.

Usa un prefijo nuevo para conservar las evidencias anteriores. `--overwrite` sigue permitiendo reemplazar explícitamente sólo los destinos de evidencia de ese prefijo; por sí solo no limpia datos. Si falla la segunda corrida después de guardar la primera:

```powershell
python orchestration/flows/fase1_pipeline.py --evidence-prefix p2-jonatan-001 --resume-second
```

La reanudación conserva la primera evidencia y su referencia Proyecto 2; verifica que Raw siga teniendo los mismos SHA-256 antes de procesar. Si ya existen la segunda evidencia o el reporte, agrega `--overwrite` para reemplazarlos explícitamente. **`--fresh-start` y `--resume-second` son incompatibles**: limpiar al reanudar invalidaría la demostración de idempotencia. Si falla antes de guardar la primera corrida, vuelve a usar el comando completo con `--fresh-start`.

`--resume-second` también genera la tabla 1.1 de la segunda corrida. Si la primera evidencia es anterior a este entregable, el reporte conjunto deriva su tabla de las métricas Bronze guardadas y del Raw validado, sin sobrescribir el JSON ni el Markdown de la primera corrida.

Ejecuta esta preparación sin otros productores, consumidores o corridas del proyecto en paralelo. No hay respaldo automático del volumen ni rollback de una limpieza interrumpida. Las pruebas de seguridad usan directorios temporales y simulan Docker/Kafka/PostgreSQL:

```powershell
python -m unittest discover -s tests -v
```

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

## Proyecto 2 — requisito 1.2: población y etiqueta por TARJETA

La unidad es `(operador, llave_operacional)`, no `usuario_canonico_id`. Se materializa en `silver.silver_p2_poblacion_tarjeta` con `unidad_id` estable (MD5 de operador y llave con namespace), operador, llave original, corte, fecha_corte, eventos_previos_28d, eventos_futuros_30d y etiqueta. La clave lógica de fila es `(unidad_id, fecha_corte)`. `eventos_futuros_30d` es únicamente auditoría de la etiqueta, nunca una feature predictora.

| Corte | Fecha de corte | Ventana previa de población | Ventana futura de etiqueta |
|---|---|---|---|
| A | 2026-07-01 00:00:00 | [2026-06-03 00:00:00, 2026-07-01 00:00:00) | [2026-07-01 00:00:00, 2026-07-31 00:00:00) |
| B | 2026-07-31 00:00:00 | [2026-07-03 00:00:00, 2026-07-31 00:00:00) | [2026-07-31 00:00:00, 2026-08-30 00:00:00) |

`silver.silver_p2_usos_tarjeta` es una vista que unifica exclusivamente las cuatro operaciones Silver. Excluye registros presentes en `silver_cuarentena` por operador e ID Bronze, sin multiplicar filas por motivos de rechazo. Un evento válido TM/TU/AM es un uso en su timestamp Silver local. Un viaje **cerrado** de MetroRiel cuenta una vez, fechado por ingreso y disponible cuando se conoce su salida, siguiendo la convención existente de features. No se inventa un segundo uso al salir.

Para entrar en la población se exigen al menos dos usos en la ventana previa, ambos disponibles **antes** del corte. En MetroRiel el cierre debe ser también anterior al corte: un viaje que ingresa antes y termina después no se incorpora retroactivamente. Se aplica la interpretación literal confirmada del CDC: cualquier `DELETE` Transmetro con `valid_from < fecha_corte` excluye, incluso si después hubo `INSERT`/`UPDATE`; un DELETE exactamente en el corte o posterior no decide la población. Se consulta el historial `silver_padron_transmetro_scd2`, no su estado vigente actual. No se extrapola ese padrón a otros operadores.

La etiqueta es 1 si no hay usos de esa tarjeta en la ventana futura y 0 si hay uno o más. El cierre de MR debe ser anterior al extremo superior de la ventana; no se usan cierres posteriores para conocer un viaje en ese horizonte. Por convención, un viaje que ingresa antes de un límite y cierra después no se desplaza artificialmente al instante de salida. Los extremos superiores son exclusivos: un uso exactamente en el corte pertenece al futuro, y uno exactamente 30 días después queda fuera de la etiqueta de ese corte.

`silver.silver_p2_costo_tarjeta` informa, para A y B, población, positivos, tasa y positivos con actividad futura en otro operador bajo la misma identidad **inferida** del bridge P1. Cuenta cada positivo una vez; la otra llave no necesita formar parte de la población. El bridge sólo participa en este costo descriptivo y nunca decide población, unidad ni etiqueta. Se usa el patrón `USR-*`/`PATRON_NUMERICO_INFERIDO`; no se inventan equivalencias de Aerómetro. Un cero de enlaces AM no demuestra ausencia de actividad real de esa persona en otros modos.

Con Silver ya disponible en PostgreSQL, construir **sólo** este requisito y exportar evidencia agregada:

```powershell
python scripts/run_dbt.py build --select tag:p2_12 --threads 1
python scripts/generar_evidencia_p2_12.py
python -m unittest discover -s tests -p test_p2_12_tarjeta.py -v
```

El exportador usa una transacción PostgreSQL `REPEATABLE READ, READ ONLY`, recalcula el universo completo de candidatos y las etiquetas con agregados condicionales y aborta ante cualquier diferencia con la tabla materializada. Verifica independientemente el costo agrupando los operadores con actividad futura por identidad inferida. Reconcilia también los totales por operador y registra las fechas con usos: 28 previas y 30 futuras por operador/corte. Esa comprobación de cobertura no certifica exhaustividad de registros.

Genera `docs/metricas/p2-12-tarjeta.md`, `.csv` y `.json`, con las cuentas completas `positivos / población` y `positivos_con_actividad_otro_operador / positivos`. Las exportaciones son agregadas: las llaves originales permanecen en la tabla Silver. Para conservar otra ejecución usa `--output-prefix`; para reemplazar esos archivos requiere `--overwrite` explícito. Los resultados verificados están en [la evidencia del requisito 1.2](docs/metricas/p2-12-tarjeta.md).

Este requisito no modifica `silver_features_usuario`, no implementa 1.3 ni entrena modelos. La etiqueta B se reporta exclusivamente como entregable, sin usarla para decisiones de modelado. No requiere ingesta, Docker ni `--fresh-start`.
