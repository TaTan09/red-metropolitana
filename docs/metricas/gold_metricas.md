# Métricas medidas de Gold — Fase 1

Consultas realizadas en PostgreSQL después de `python scripts/run_dbt.py build`, con los Parquet completos de las nueve fuentes del proyecto.

## Filas por dimensión

| Dimensión | Filas |
|---|---:|
| `gold.dim_usuario` | 70,380 |
| `gold.dim_tiempo` | 1,379,775 |
| `gold.dim_zona` | 16 |
| `gold.dim_punto_transporte` | 468 |
| `gold.dim_modo` | 4 |
| `gold.dim_servicio` | 52 |

`dim_zona` tiene 16 filas: las 12 zonas y 4 municipios del universo definido por el generador (`silver_universo_zonas`). 15 tienen servicio y Santa Catarina Pinula no. La medición de la evidencia 003 era 13, que refleja el modelo vigente el 22-sep-2026, que colapsaba tres municipios en un solo valor por un error de normalización de zonas; ver `004-correccion-zonas.md`.

Los 468 puntos corresponden a 104 estaciones TM, 328 paradas TU, 22 estaciones MR y 14 estaciones AM. En `dim_usuario`, 33,553 identidades se observan en un modo, 26,831 en dos y 9,996 en tres. La vinculación de TM/TU/MR es inferida; Aerómetro permanece aislado.

## Filas por hecho

| Hecho | Filas | Grano |
|---|---:|---|
| `gold.fact_abordajes` | **1,393,448** | Un acceso/abordaje válido TM, TU o AM |
| `gold.fact_viajes_metroriel` | **295,511** | Un viaje MR completo |

| Modo en `fact_abordajes` | Abordajes | Suma de tarifas registradas (GTQ) |
|---|---:|---:|
| Transmetro | 362,106 | 296,397.00 |
| Transurbano | 827,788 | 979,138.55 |
| Aerómetro | 203,554 | 712,439.00 |
| **Total** | **1,393,448** | **1,987,974.55** |

MetroRiel: **295,511 viajes**; suma de tarifas registradas **Q807,132.00** y duración promedio **21.42 minutos**. La suma de tarifas no debe interpretarse automáticamente como recaudo efectivo; representa el importe disponible en las fuentes operacionales.

## Integridad
> Las cifras de pruebas de esta sección corresponden a la validación de Fase 1 (22-sep-2026). El build vigente se registra en la corrida final de Fase 2.

- `362,106 + 827,788 + 203,554 = 1,393,448`: el hecho de abordajes coincide exactamente con los tres modelos Silver válidos.
- `295,511`: el hecho MR coincide exactamente con `silver_metroriel_viajes`.
- Los tests dbt de claves únicas y no nulas, relaciones hecho-dimensión, conteos de hechos y ausencia de identificadores crudos aprobaron.
- La ejecución completa de la versión final, `python scripts/run_dbt.py build`, terminó con `PASS=58`, `WARN=0`, `ERROR=0` (18 modelos, 39 pruebas y el hook `pgcrypto`).
- La prueba adicional `gold_conteos_modo` confirmó por separado los tres conteos de abordajes de Silver.
- Una segunda construcción de Gold terminó con `PASS=46`, `WARN=0`, `ERROR=0` (8 modelos, 37 pruebas y el hook). Los ocho conteos de dimensiones y hechos permanecieron idénticos.

Consultas de reproducción:

```sql
SELECT fuente_evento, count(*) AS eventos, sum(tarifa_quetzales) AS tarifa_gtq
FROM gold.fact_abordajes GROUP BY fuente_evento ORDER BY fuente_evento;

SELECT count(*) AS viajes, sum(tarifa_quetzales) AS tarifa_gtq,
       round(avg(duracion_minutos), 2) AS duracion_media_min
FROM gold.fact_viajes_metroriel;
```
