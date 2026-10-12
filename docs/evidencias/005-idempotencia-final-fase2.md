# Idempotencia final del proyecto — Fase 2

Se ejecutÃ³ dos veces el mismo flujo Prefect con los mismos archivos Raw,
sin borrar Bronze, el estado SQLite de deduplicaciÃ³n ni los volÃºmenes Docker.
Idempotencia significa que reprocesar las mismas fuentes no cambia el estado analÃ­tico final.

- Corrida 1: 780.23 s; terminÃ³ 2026-10-12T13:56:34-06:00.
- Corrida 2: 785.70 s; terminÃ³ 2026-10-12T14:09:40-06:00.
- ComparaciÃ³n completa de SHA-256 Raw, Parquet Bronze y conteos SQL: **IGUALES**.
- Referencia Gold medida en PostgreSQL: **OK**.
- Cada corrida ejecutÃ³ `python scripts/run_dbt.py build` con sus pruebas.

## Conteos de ambas corridas

### Bronze (filas por fuente)

| Tabla/fuente | Corrida 1 | Corrida 2 | ComparaciÃ³n |
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

| Tabla/fuente | Corrida 1 | Corrida 2 | ComparaciÃ³n |
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

| Tabla/fuente | Corrida 1 | Corrida 2 | ComparaciÃ³n |
|---|---:|---:|---|
| `silver_transmetro_validaciones` | 362,106 | 362,106 | IGUALES |
| `silver_transurbano_transacciones` | 827,788 | 827,788 | IGUALES |
| `silver_metroriel_viajes` | 295,511 | 295,511 | IGUALES |
| `silver_aerometro_boardings` | 203,554 | 203,554 | IGUALES |
| `silver_cuarentena` | 9,710 | 9,710 | IGUALES |
| `silver_padron_transmetro_scd2` | 22,326 | 22,326 | IGUALES |

### Gold dbt

| Tabla/fuente | Corrida 1 | Corrida 2 | ComparaciÃ³n |
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

| Tabla/fuente | Corrida 1 | Corrida 2 | ComparaciÃ³n |
|---|---:|---:|---|
| `Aerometro` | 203,554 | 203,554 | IGUALES |
| `Transmetro` | 362,106 | 362,106 | IGUALES |
| `Transurbano` | 827,788 | 827,788 | IGUALES |

## Streaming y deduplicaciÃ³n

| Fuente | Corrida | Mensajes consumidos | Nuevos Bronze | Omitidos por `_event_id` |
|---|---:|---:|---:|---:|
| transmetro | 1 | 363,221 | 0 | 363,221 |
| aerometro | 1 | 203,554 | 0 | 203,554 |
| transmetro | 2 | 363,221 | 0 | 363,221 |
| aerometro | 2 | 203,554 | 0 | 203,554 |

## DuraciÃ³n de etapas

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

## Hallazgo y correcciÃ³n

Antes de la orquestaciÃ³n, los productores podÃ­an informar entregas Kafka fallidas
en el callback y aun asÃ­ terminar con cÃ³digo cero. Ahora contabilizan esas fallas
y devuelven cÃ³digo distinto de cero para detener Prefect.

Los consumidores esperan la asignaciÃ³n de particiÃ³n antes de medir inactividad.
Los productores aplican espera acotada ante presiÃ³n de la cola Kafka.
La cantidad consumida puede superar las filas Raw si existen publicaciones
anteriores; la deduplicaciÃ³n por `_event_id` impide agregar copias a Bronze.

En este Docker, `dbt test` con cuatro hilos llegÃ³ a agotar `/dev/shm`.
`python scripts/run_dbt.py test --threads 1` completÃ³ las 39 pruebas
y el hook con `PASS=40`, `WARN=0`, `ERROR=0`.

Los archivos `003-corrida-1.json` y `003-corrida-2.json` contienen los SHA-256
Raw y las filas de cada archivo Parquet, ademÃ¡s de estos conteos y duraciones.


## Validación final de dbt

La corrida final del proyecto ejecutó el build completo de dbt y terminó correctamente:

- PASS: 189
- WARN: 0
- ERROR: 0
- Comparación entre corridas: IGUALES
- Referencia Gold: OK
