# Evidencia de consumo Streaming — Transmetro

- **Fecha:** `2026-09-12T22:58:24-06:00`
- **Topic:** `transmetro-validaciones`
- **Consumer group:** `bronze-transmetro-v1`
- **Mensajes consumidos:** 363,221
- **Eventos nuevos escritos a Bronze:** 363,211
- **Repeticiones técnicas omitidas:** 10
- **Mensajes inválidos:** 0
- **Archivos Parquet creados:** 73

## Interpretación

La deduplicación del consumidor usa `_event_id`, generado de forma determinística por el productor.

Esto evita duplicación técnica del pipeline, pero **no elimina** duplicados reales del torniquete presentes en el archivo fuente. Esos registros deben llegar a Bronze y serán tratados como calidad de negocio posteriormente en Silver.
