## mart_demanda_hora

**Pregunta que responde:** demanda por modo, zona y hora (enunciado 2.1, tablero).

**Grano:** una fila por fecha × hora × modo × zona.

**Fuentes:** `fact_abordajes` (Transmetro, Transurbano, Aerómetro) y
`fact_viajes_metroriel`, unidos con `union all` y enlazados a `dim_tiempo`
y `dim_zona`.

| Columna | Descripción |
|---|---|
| fecha, hora | Desde `dim_tiempo` |
| es_dia_habil, es_hora_pico | Desde `dim_tiempo` (regla en modelo_dimensional_gold.md) |
| modo, zona | Nombre del modo y zona conformada |
| tipo_evento | `abordaje` (TM/TU/AM) o `viaje` (MR) |
| cantidad_eventos | Aditiva. Abordajes válidos o viajes iniciados |
| tarifa_total_gtq | Aditiva. Suma de importes registrados |

**Regla de MetroRiel:** cada viaje cuenta una vez, por su ingreso, y se asigna
a la zona de origen. La salida y la zona destino no se cuentan aquí.

**Advertencia:** `cantidad_eventos` mezcla dos unidades (abordaje y viaje).
Para comparar modos con rigor, filtrar o desglosar por `tipo_evento`.

**Fuera del mart:** usuarios distintos (no es aditivo; sumarlo entre filas
duplicaría personas).

**Reconciliación:** `sum(cantidad_eventos)` = filas de `fact_abordajes` +
filas de `fact_viajes_metroriel` (1,688,959 hoy).


## mart_cobertura

**Pregunta que responde:** dónde hay servicio y cuánta demanda se observa en
cada zona (enunciado 2.1, cobertura).

**Grano:** una fila por zona del universo de `dim_zona` (16 hoy), con o sin servicio.

**Fuentes:** `dim_zona` (oferta: puntos y modos con servicio) y
`mart_demanda_hora` (uso observado), unidos por nombre de zona.

| Columna | Descripción |
|---|---|
| zona_sk, nombre_zona, tipo_area | Desde `dim_zona` |
| tiene_servicio, modos_con_servicio, puntos_transporte | Oferta según los catálogos de los operadores |
| eventos_totales | Suma de `cantidad_eventos` de la zona |
| eventos_transmetro, eventos_transurbano, eventos_metroriel, eventos_aerometro | Desglose por modo; la suma de los cuatro es `eventos_totales` |
| eventos_por_punto | `eventos_totales` / `puntos_transporte`; NULL si la zona no tiene puntos |
| pct_demanda_red | Participación de la zona en el total de eventos de la red |
| ranking_demanda | Posición por `eventos_totales` (empates comparten posición) |
| inconsistencia_cobertura | true si la zona tiene servicio y cero eventos, o no tiene servicio y tiene eventos |

**Reglas heredadas:** MetroRiel cuenta una vez por viaje, en el ingreso y en
la zona de origen. La zona destino no se cuenta aquí.

**Advertencias:**
- `eventos_totales` mezcla abordajes (TM/TU/AM) con viajes (MR). No es una
  cantidad de personas ni de viajes. `pct_demanda_red` hereda la misma mezcla.
- `tiene_servicio` sale de los catálogos, no de la actividad. Una zona sin
  servicio tiene cero eventos por construcción, así que el mart muestra dónde
  NO hay servicio, pero no mide demanda potencial ni dónde hace falta
  servicio. Esa pregunta no se puede responder con estas fuentes.
- El universo de 16 zonas viene del generador entregado (`silver_universo_zonas`),
  no de un catálogo oficial externo.

**Reconciliación:** `sum(eventos_totales)` = `sum(cantidad_eventos)` de
`mart_demanda_hora` (1,688,959 hoy), en total y por modo.

**Pruebas:** `mart_cobertura_grano`, `mart_cobertura_reconciliacion`,
`mart_cobertura_consistencia` y pruebas de unicidad y no nulos en `schema.yml`.