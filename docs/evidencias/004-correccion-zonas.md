# Evidencia 004 — Corrección del conteo de zonas en Gold (13 → 16)

**Fecha:** 2026-10-08

## Qué se encontró
La evidencia 003 y `gold_metricas.md` reportaban `gold.dim_zona` = 13 filas. El modelo vigente lee `silver_universo_zonas` y produce 16.

## Causa
Un error de normalización en `normalizar_zona`, corregido en `b1d1faa` (1-oct-2026): la rama `else` aplicaba `'Zona ' || regexp_replace(valor, '[^0-9]', '', 'g')` a cualquier valor no numérico, de modo que `Mixco`, `Villa Nueva` y `San Miguel Petapa` se convertían en `'Zona '` y colapsaban en un solo valor. `dim_zona` mostraba así 12 zonas numéricas más 1 valor colapsado = 13. La corrección preserva los tres municipios con `initcap`. Además, `5ee5c0a` agregó `silver_universo_zonas` (universo de 16 áreas del generador, incluido Santa Catarina Pinula, sin servicio) y `8300064` hizo que `dim_zona` lo leyera con `tiene_servicio`, `modos_con_servicio` y `puntos_transporte`: 12 zonas + 3 municipios servidos + 1 sin servicio = 16.

## Medición actual
- `gold.dim_zona`: 16 filas (12 zonas, 4 municipios).
- 15 áreas con servicio; Santa Catarina Pinula sin servicio (0 puntos, 0 eventos).
- `mart_cobertura`: 16 filas; suma de eventos = suma de `mart_demanda_hora` (1,688,959), en total y por modo.
- `dbt build --select mart_cobertura`: PASS=10, WARN=0, ERROR=0.
- Resto de dimensiones y hechos, sin cambios respecto a la validación de Fase 1: `dim_usuario` 70,380; `dim_tiempo` 1,379,775; `dim_punto_transporte` 468; `dim_modo` 4; `dim_servicio` 52; `fact_abordajes` 1,393,448; `fact_viajes_metroriel` 295,511.

## Impacto
Los conteos de hechos no cambiaron (1,393,448 + 295,511 = 1,688,959). Sí cambió la asignación de zona de los eventos y puntos de Mixco, Villa Nueva y San Miguel Petapa, que antes compartían una zona colapsada. Cambió también la dimensión de zona y los documentos que citaban 13.

## Documentos corregidos
`gold_metricas.md`, `modelo_dimensional_gold.md`, `sql/ddl/gold_model.sql`; nota añadida a la evidencia 003.

## Limitación
El universo de 16 áreas viene del generador, no de una fuente geográfica oficial.