# Evidencia de consumo Streaming — Aerómetro

- **Fecha:** `2026-09-13T22:00:19-06:00`
- **Topic:** `aerometro-boardings`
- **Consumer group:** `bronze-aerometro-v1`
- **Mensajes consumidos:** 100
- **Eventos nuevos escritos a Bronze:** 0
- **Repeticiones técnicas omitidas:** 100
- **Mensajes inválidos:** 0
- **Archivos Parquet creados:** 0

## Interpretación

Bronze conserva el mensaje Kafka completo en `raw_json`.

El campo `timestamp_utc` permanece en UTC en Bronze. Su conversión a hora local de Guatemala corresponde a Silver.

La deduplicación mediante `_event_id` elimina únicamente repeticiones técnicas del pipeline.
