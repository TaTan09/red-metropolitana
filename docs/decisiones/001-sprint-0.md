# ADR 001 — Decisiones del Sprint 0

Estado: Aceptado

## Decisiones

1. `fact_abordajes` para Transmetro, Transurbano y Aerómetro.
2. `fact_viajes_metroriel` para MetroRiel.
3. Resolución de identidad TM/TU/MR mediante patrón numérico como aproximación académica; Aerómetro queda independiente.
4. CDC preservado como registro ambiguo en entrada; se deriva padrón Transmetro usando `TC-*`.
5. Transurbano se ingiere por Batch.
6. Bronze vive en un Data Lake local con Parquet y partición por fecha de ingesta.
7. PostgreSQL será el warehouse para Staging, Silver y Gold.
8. Kafka se utilizará para streaming de Transmetro y Aerómetro.
9. Prefect se utilizará para orquestación.
10. Tableau consume únicamente Gold.

## Limitaciones

- La multimodalidad es observable/inferida, no identidad real demostrada.
- Aerómetro no puede relacionarse de forma confiable con los otros operadores con los datos entregados.
