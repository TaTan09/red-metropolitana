# Idempotencia del flujo completo de Fase 1

Se ejecutó dos veces el mismo flujo Prefect con los mismos archivos Raw,
sin borrar Bronze, el estado SQLite de deduplicación ni los volúmenes Docker.
Idempotencia significa que reprocesar las mismas fuentes no cambia el estado analítico final.

- Corrida 1: 648.23 s; terminó 2026-09-22T22:45:03-06:00.
- Corrida 2: 726.59 s; terminó 2026-09-22T23:00:40-06:00.
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
| `dim_zona` | 13 | 13 | IGUALES |
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
| transmetro | 1 | 726,442 | 0 | 726,442 |
| aerometro | 1 | 203,554 | 0 | 203,554 |
| transmetro | 2 | 918,636 | 0 | 918,636 |
| aerometro | 2 | 203,554 | 0 | 203,554 |

## Duración de etapas

| Etapa | Corrida 1 (s) | Corrida 2 (s) |
|---|---:|---:|
| `validar_servicios` | 0.26 | 0.26 |
| `batch_to_bronze` | 1.40 | 1.12 |
| `cdc_to_bronze` | 8.45 | 8.02 |
| `streaming_transmetro` | 194.51 | 236.79 |
| `streaming_aerometro` | 74.43 | 69.10 |
| `rebuild_staging` | 223.99 | 222.78 |
| `dbt_build` | 143.29 | 186.22 |
| `collect_metrics` | 1.42 | 1.82 |

## Hallazgo y corrección

Antes de la orquestación, los productores podían informar entregas Kafka fallidas
en el callback y aun así terminar con código cero. Ahora contabilizan esas fallas
y devuelven código distinto de cero para detener Prefect.

Un primer intento se detuvo porque el consumidor Transmetro declaró inactividad
antes de recibir la asignación de partición del grupo Kafka. Los consumidores
ahora comienzan a medir inactividad después de la asignación. Durante el intento
posterior, Kafka registró timeouts del controlador y el productor Transmetro salió
con error; se añadió espera acotada cuando la cola local se llena. No se borraron
topics, Bronze ni el estado de deduplicación. Por eso Transmetro consumió 726,442
mensajes en la corrida 1 y 918,636 en la corrida 2: incluyen publicaciones de
intentos intermedios y todos fueron omitidos por `_event_id`. Cada corrida
terminó con los mismos 363,221 eventos Transmetro en Bronze.

Ambos `dbt build` terminaron con `PASS=58`, `WARN=0`, `ERROR=0` (18 modelos,
39 pruebas y un hook). Como validación separada, `dbt test` con cuatro hilos
tuvo una falla de infraestructura: el contenedor PostgreSQL agotó `/dev/shm`
al ampliar un segmento de memoria compartida. `python scripts/run_dbt.py test
--threads 1` terminó con `PASS=40`, `WARN=0`, `ERROR=0` (39 pruebas y un hook).
En este entorno conviene usar un hilo para repetir solo las pruebas.

Los archivos `003-corrida-1.json` y `003-corrida-2.json` contienen los SHA-256
Raw y las filas de cada archivo Parquet, además de estos conteos y duraciones.
