# Métricas de rendimiento — Fase 2

**Fecha de medición:** 2026-10-10

## Entorno

Laptop con 16 GB de RAM y CPU AMD Ryzen. PostgreSQL 16 y Kafka corren en Docker
con 7.4 GiB de memoria asignada (`docker info`). Las cifras son de este entorno
y no son comparables con otras máquinas.

## Tamaño por capa

| Capa | Dónde vive | Tablas | Tamaño |
|---|---|---:|---:|
| Raw | Disco (`data/raw`) | — | 130.5 MB |
| Bronze | Disco, Parquet (`data/bronze`) | — | 337.5 MB |
| Staging | PostgreSQL | 14 | 332 MB |
| Silver | PostgreSQL | 10 | 315 MB |
| Gold | PostgreSQL | 10 | 758 MB |

PostgreSQL suma 1,405 MB. Los tamaños de PostgreSQL usan `pg_total_relation_size`
(tabla, índices y TOAST) y no incluyen vistas. Bronze incluye `_control` (estado
SQLite de deduplicación y manifiestos). Las filas por tabla son estimaciones de
`ANALYZE`; los conteos exactos están en `003-idempotencia-flujo-completo.md`.

### Tablas más grandes

| Tabla | Filas (aprox.) | Tamaño |
|---|---:|---:|
| `gold.fact_abordajes` | 1,393,267 | 506 MB |
| `silver.silver_transurbano_transacciones` | 827,788 | 151 MB |
| `staging.transurbano_transacciones` | 832,791 | 145 MB |
| `gold.fact_viajes_metroriel` | 295,511 | 129 MB |
| `gold.dim_tiempo` | 1,379,775 | 112 MB |
| `gold.mart_demanda_hora` | 37,619 | 3.2 MB |

### Lectura

- Gold pesa 2.4 veces más que Silver. La causa principal es `fact_abordajes`: cada
  fila ocupa en promedio 359 bytes (`pg_column_size`), así que 1.39 millones de filas
  son unos 500 MB, casi todo el tamaño de la tabla. Por el tipo de las columnas, las
  siete claves `md5` en texto (33 bytes cada una) y `bronze_record_id` (65 a 72 bytes)
  suman alrededor de 300 de esos 359 bytes; ese reparto es un cálculo, no una medición
  por columna. Claves enteras reducirían el tamaño; se deja como mejora futura.
- Bronze pesa 2.6 veces más que Raw. En streaming cada mensaje se guarda completo
  como JSON con metadatos técnicos. Tampoco se midió por separado.
- `mart_demanda_hora` es unas 160 veces más pequeño que `fact_abordajes`.

## Tiempo de consulta

Misma pregunta (abordajes por modo, zona y hora) resuelta de tres formas.
Cada consulta se ejecutó 5 veces con `EXPLAIN (ANALYZE)`; se reporta `Execution Time`
(tiempo de servidor, sin transferencia al cliente) y la mediana.

| Consulta | Corridas (ms) | Mediana |
|---|---|---:|
| A. `fact_abordajes` + `dim_tiempo`, `dim_zona`, `dim_modo` | 3,456 · 3,353 · 2,828 · 3,493 · 4,408 | 3,456 ms |
| B. `mart_demanda_hora` | 45 · 48 · 43 · 43 · 54 | 45 ms |
| C. `v_tableau_demanda_abordajes` | 33 · 33 · 43 · 35 · 35 | 34.5 ms |

### Lectura

- El mart responde la misma pregunta unas 75 veces más rápido que los hechos.
  La consulta A une 1.4 millones de filas con `dim_tiempo`, que tiene otras 1.4 millones.
- La vista de Tableau no agrega costo medible sobre el mart. La diferencia entre
  B y C (unos 10 ms) está dentro del ruido.
- La consulta A varía bastante entre corridas (2.8 a 4.4 s); debe leerse como
  "alrededor de 3.5 s".
- Ninguna primera corrida fue notablemente más lenta, así que los datos ya estaban
  en la caché de PostgreSQL; no son mediciones en frío.

## Tiempo del pipeline

Los tiempos por etapa de Fase 1 están en `003-idempotencia-flujo-completo.md`
(`dbt_build`: 143 s y 186 s). Los de Fase 2, con marts y vistas, se registrarán
en la corrida final de idempotencia.

## Cómo reproducir

```powershell
docker exec -i red_metropolitana_postgres psql -U red_user -d red_metropolitana -c "analyze"
Get-Content sql/utilities/metricas_tamano.sql | docker exec -i red_metropolitana_postgres psql -U red_user -d red_metropolitana
.\scripts\medir_consultas.ps1
docker exec -i red_metropolitana_postgres psql -U red_user -d red_metropolitana -c "select avg(pg_column_size(f.*)) as bytes_por_fila from gold.fact_abordajes f"
```
