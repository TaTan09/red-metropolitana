# Idempotencia final del proyecto — Fase 2

Se ejecutó dos veces el mismo flujo Prefect con los mismos archivos Raw,
sin borrar Bronze, el estado SQLite de deduplicación ni los volúmenes Docker.
Idempotencia significa que reprocesar las mismas fuentes no cambia el estado analítico final.

- Corrida 1: 780.23 s; terminó 2026-10-12T13:56:34-06:00.
- Corrida 2: 785.70 s; terminó 2026-10-12T14:09:40-06:00.
- Comparación completa de SHA-256 Raw, Parquet Bronze y conteos SQL: **IGUALES**.
- Referencia Gold medida en PostgreSQL: **OK**.
- Cada corrida ejecutó `python scripts/run_dbt.py build` con sus pruebas.

## Conteos de ambas corridas

### Bronze (filas por fuente)

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `tm_estaciones` | 104 | 104 | IGUALES |
| `tu_paradas` | 328 | 328 | IGUALES |
| `mr_estaciones` | 22 | 22 | IGUALES |
| `am_estaciones` | 14 | 14 | IGUALES |
| `transurbano_transacciones` | 832,791 | 832,791 | IGUALES |
| `metroriel_viajes` | 299,100 | 299,100 | IGUALES |
| `cdc_padron_usuarios` | 31,050 | 31,050 | IGUALES |
| `transmetro_validaciones` | 363,221 | 363,221 | IGUALES |
| `aerometro_boardings` | 203,554 | 203,554 | IGUALES |

### Staging PostgreSQL

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `tm_estaciones` | 104 | 104 | IGUALES |
| `tu_paradas` | 328 | 328 | IGUALES |
| `mr_estaciones` | 22 | 22 | IGUALES |
| `am_estaciones` | 14 | 14 | IGUALES |
| `transurbano_transacciones` | 832,791 | 832,791 | IGUALES |
| `metroriel_viajes` | 299,100 | 299,100 | IGUALES |
| `cdc_registro_ambiguo` | 31,050 | 31,050 | IGUALES |
| `transmetro_validaciones` | 363,221 | 363,221 | IGUALES |
| `aerometro_boardings` | 203,554 | 203,554 | IGUALES |
| `padron_transmetro_actual` | 17,432 | 17,432 | IGUALES |
| `usuarios_transurbano_min` | 36,567 | 36,567 | IGUALES |
| `usuarios_metroriel_min` | 22,885 | 22,885 | IGUALES |
| `usuarios_aerometro_min` | 14,496 | 14,496 | IGUALES |

### Silver dbt

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `silver_transmetro_validaciones` | 362,106 | 362,106 | IGUALES |
| `silver_transurbano_transacciones` | 827,788 | 827,788 | IGUALES |
| `silver_metroriel_viajes` | 295,511 | 295,511 | IGUALES |
| `silver_aerometro_boardings` | 203,554 | 203,554 | IGUALES |
| `silver_cuarentena` | 9,710 | 9,710 | IGUALES |
| `silver_padron_transmetro_scd2` | 22,326 | 22,326 | IGUALES |

### Gold dbt

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `dim_usuario` | 70,380 | 70,380 | IGUALES |
| `dim_tiempo` | 1,379,775 | 1,379,775 | IGUALES |
| `dim_zona` | 16 | 16 | IGUALES |
| `dim_punto_transporte` | 468 | 468 | IGUALES |
| `dim_modo` | 4 | 4 | IGUALES |
| `dim_servicio` | 52 | 52 | IGUALES |
| `fact_abordajes` | 1,393,448 | 1,393,448 | IGUALES |
| `fact_viajes_metroriel` | 295,511 | 295,511 | IGUALES |

### Gold abordajes por modo

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `Aerometro` | 203,554 | 203,554 | IGUALES |
| `Transmetro` | 362,106 | 362,106 | IGUALES |
| `Transurbano` | 827,788 | 827,788 | IGUALES |

## Streaming y deduplicación

| Fuente | Corrida | Mensajes consumidos | Nuevos Bronze | Omitidos por `_event_id` |
|---|---:|---:|---:|---:|
| transmetro | 1 | 363,221 | 0 | 363,221 |
| aerometro | 1 | 203,554 | 0 | 203,554 |
| transmetro | 2 | 363,221 | 0 | 363,221 |
| aerometro | 2 | 203,554 | 0 | 203,554 |

## Duración de etapas

| Etapa | Corrida 1 (s) | Corrida 2 (s) |
|---|---:|---:|
| `validar_servicios` | 0.24 | 0.14 |
| `batch_to_bronze` | 1.22 | 1.54 |
| `cdc_to_bronze` | 7.34 | 7.81 |
| `streaming_transmetro` | 132.64 | 105.04 |
| `streaming_aerometro` | 65.40 | 65.32 |
| `rebuild_staging` | 201.94 | 206.77 |
| `dbt_build` | 358.13 | 396.73 |
| `collect_metrics` | 12.84 | 2.25 |

## Hallazgo y corrección

Antes de la orquestación, los productores podían informar entregas Kafka fallidas
en el callback y aun así terminar con código cero. Ahora contabilizan esas fallas
y devuelven código distinto de cero para detener Prefect.

Los consumidores esperan la asignación de partición antes de medir inactividad.
Los productores aplican espera acotada ante presión de la cola Kafka.
La cantidad consumida puede superar las filas Raw si existen publicaciones
anteriores; la deduplicación por `_event_id` impide agregar copias a Bronze.

En este Docker, `dbt test` con cuatro hilos llegó a agotar `/dev/shm`.
La limitación histórica de memoria compartida se documenta en 003; ese resultado no corresponde a esta validación final.

Los archivos `005-corrida-final-1.json` y `005-corrida-final-2.json` contienen los SHA-256
Raw y las filas de cada archivo Parquet, además de estos conteos y duraciones.

## Validación final de dbt y alcance de la evidencia

La consola de la ejecución final registró **PASS=189, WARN=0, ERROR=0**. Ese total combina modelos, pruebas y hook; no significa 189 pruebas.

Durante el cleanup se recuperó el `target/run_results.json` local del segundo build, generado el **2026-10-12T20:09:36.953054Z**, invocación **1fa98fbe-5711-426e-aa0a-6cfde5e94aca**. Precede en unos segundos el cierre de la segunda corrida y corresponde a `build`; su duración dbt es **389.05 s**, dentro de los 396.73 s de proceso registrados. El resumen sin SQL compilado se añadió a `005-corrida-final-2.json` como `etapas.dbt_build.resumen_dbt_recuperado`, indicando su procedencia posterior:

- **158 pruebas PASS**.
- **30 modelos success y 1 hook success**.
- **0 warnings, 0 errores y 0 skips**.
- **189 resultados totales**.

No se conserva un `run_results.json` separado de la primera corrida; su JSON original registra código de salida 0 y duración del build, pero no la distribución de estados dbt. No se atribuyen retrospectivamente los 189 resultados a ambos JSON. `005-corrida-final-1.json` se mantiene intacto y ningún conteo histórico de las dos corridas cambió.

La igualdad de 005 cubre hashes Raw, filas por archivo Parquet, los 13 conteos Staging, seis relaciones Silver, ocho dimensiones/hechos Gold y abordajes por modo que capturaba el flow anterior. No demuestra fingerprints de todo Silver/Gold ni de marts/vistas. La nueva CLI amplía esa cobertura para evidencias futuras con prefijo propio; no se rellenaron métricas históricas ausentes. `003` permanece como evidencia histórica de Fase 1.
