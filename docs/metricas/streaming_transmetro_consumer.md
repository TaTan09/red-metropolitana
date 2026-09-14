# Evidencia de consumo Streaming — Transmetro

- **Fecha:** `2026-09-13T21:56:27-06:00`
- **Topic:** `transmetro-validaciones`
- **Consumer group:** `bronze-transmetro-v1`
- **Mensajes consumidos:** 100
- **Eventos nuevos escritos a Bronze:** 0
- **Repeticiones técnicas omitidas:** 100
- **Mensajes inválidos:** 0
- **Archivos Parquet creados:** 0

## Interpretación

La deduplicación del consumidor usa `_event_id`, generado de forma determinística por el productor.

Esto evita duplicación técnica del pipeline, pero **no elimina** duplicados reales del torniquete presentes en el archivo fuente. Esos registros deben llegar a Bronze y serán tratados como calidad de negocio posteriormente en Silver.
