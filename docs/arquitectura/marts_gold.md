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