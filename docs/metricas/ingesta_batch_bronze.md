# Evidencia de ingesta Batch a Bronze

- **Fecha:** `2026-09-22T11:06:34-06:00`

| Archivo | Fuente | Estado | Registros | Salida Bronze |
|---|---|---|---:|---|
| `tm_estaciones.csv` | `tm_estaciones` | **INGESTED** | 104 | `data/bronze/tm_estaciones/fecha_ingesta=2026-09-22/part-4d53a95abb4f.parquet` |
| `tu_paradas.csv` | `tu_paradas` | **INGESTED** | 328 | `data/bronze/tu_paradas/fecha_ingesta=2026-09-22/part-a888a09c4518.parquet` |
| `mr_estaciones.csv` | `mr_estaciones` | **INGESTED** | 22 | `data/bronze/mr_estaciones/fecha_ingesta=2026-09-22/part-c302ffbc6f0b.parquet` |
| `am_estaciones.csv` | `am_estaciones` | **INGESTED** | 14 | `data/bronze/am_estaciones/fecha_ingesta=2026-09-22/part-e3acbeed8608.parquet` |
| `transurbano_transacciones.csv` | `transurbano_transacciones` | **INGESTED** | 832,791 | `data/bronze/transurbano_transacciones/fecha_ingesta=2026-09-22/part-8ce5028499b7.parquet` |
| `metroriel_viajes.jsonl` | `metroriel_viajes` | **INGESTED** | 299,100 | `data/bronze/metroriel_viajes/fecha_ingesta=2026-09-22/part-23feb4a3a55c.parquet` |

## Interpretación

- `INGESTED`: el archivo fue escrito en Bronze.
- `SKIPPED`: el SHA-256 ya había sido ingerido y el Parquet seguía presente.
- `ERROR`: la fuente no pudo procesarse.

La idempotencia Batch se controla por SHA-256 del archivo Raw.
Una segunda ejecución con los mismos archivos debe producir `SKIPPED` y no crear filas nuevas.
