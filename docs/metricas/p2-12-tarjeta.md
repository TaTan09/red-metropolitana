# Proyecto 2 — Requisito 1.2: TARJETA

Verificado contra PostgreSQL: 2026-10-29 00:55:46.200300 (America/Guatemala).

Grano: tarjeta operacional `(operador, llave_operacional)` por corte. El ID no es usuario_canonico_id.
Cada fila conserva unidad_id, operador, llave_operacional, corte, fecha_corte y etiqueta en silver.silver_p2_poblacion_tarjeta.

## Ventanas y reglas

| Corte | fecha_corte | Población: intervalo previo | Etiqueta: intervalo futuro |
|---|---|---|---|
| A | 2026-07-01 00:00:00 | [2026-06-03 00:00:00, 2026-07-01 00:00:00) | [2026-07-01 00:00:00, 2026-07-31 00:00:00) |
| B | 2026-07-31 00:00:00 | [2026-07-03 00:00:00, 2026-07-31 00:00:00) | [2026-07-31 00:00:00, 2026-08-30 00:00:00) |

Población: al menos 2 usos válidos disponibles antes del corte en los 28 días previos. No se usan usos futuros ni la etiqueta para incluir tarjetas.
Etiqueta: 1 si hay 0 usos válidos de esa tarjeta en los siguientes 30 días; 0 si hay uno o más. El extremo superior de ambas ventanas es exclusivo.
Cualquier DELETE Transmetro con valid_from < fecha_corte excluye; reactivación no anula exclusión.
Un uso por viaje cerrado, fechado por ingreso y disponible desde salida; cierre anterior al límite de cada ventana.
Sólo Silver; los IDs presentes en silver_cuarentena se excluyen por operador y registro Bronze. No se usa el estado vigente actual del padrón.

## Población y etiqueta

| Corte | Población | Positivos | Cuenta completa | Tasa positiva |
|---|---:|---:|---|---:|
| A | 77411 | 11211 | 11211 / 77411 | 14.482438 % |
| B | 76378 | 10312 | 10312 / 76378 | 13.501270 % |

## Costo observable de elegir TARJETA

Costo por patrón numérico inferido P1; no identidad personal verificada. Aerómetro aislado; cero enlaces detectables no significa cero actividad real cruzada.
Se cuenta cada positivo una sola vez si otra llave de la identidad inferida tiene uso futuro válido en un operador distinto, aunque esa otra llave no pertenezca a la población.
Esta métrica no modifica etiquetas. B se reporta exclusivamente como entregable; no se usa para decisiones de modelado ni se entrenó un modelo.

| Corte | Positivos totales | Con actividad en otro operador | Cuenta completa | Proporción | Positivos Aerómetro sin enlace medible |
|---|---:|---:|---|---:|---:|
| A | 11211 | 2394 | 2394 / 11211 | 21.354027 % | 1460 |
| B | 10312 | 2394 | 2394 / 10312 | 23.215671 % | 1360 |

## Desglose por operador

| Corte | Operador | Población | Positivos |
|---|---|---:|---:|
| A | Aerometro | 10429 | 1460 |
| A | MetroRiel | 15746 | 2261 |
| A | Transmetro | 18918 | 3196 |
| A | Transurbano | 32318 | 4294 |
| B | Aerometro | 10284 | 1360 |
| B | MetroRiel | 15687 | 2102 |
| B | Transmetro | 18786 | 2967 |
| B | Transurbano | 31621 | 3883 |

## Verificación y cobertura

Diferencias contra recálculo independiente del universo completo: 0.
Cortes con diferencias contra recálculo independiente del costo: 0.
28/30 fechas con usos por operador: True.
La cobertura diaria constata datos en cada fecha; no certifica exhaustividad de registros ni continuidad de identidad personal.

| Corte | Operador | Días previos con usos | Días futuros con usos | Primer uso observado | Último uso observado |
|---|---|---:|---:|---|---|
| A | Aerometro | 28 | 30 | 2026-06-01 04:00:29 | 2026-08-29 22:53:16 |
| A | MetroRiel | 28 | 30 | 2026-06-01 04:00:15 | 2026-08-29 22:57:48 |
| A | Transmetro | 28 | 30 | 2026-06-01 04:00:34 | 2026-08-29 22:56:47 |
| A | Transurbano | 28 | 30 | 2026-06-01 04:00:24 | 2026-08-29 22:57:03 |
| B | Aerometro | 28 | 30 | 2026-06-01 04:00:29 | 2026-08-29 22:53:16 |
| B | MetroRiel | 28 | 30 | 2026-06-01 04:00:15 | 2026-08-29 22:57:48 |
| B | Transmetro | 28 | 30 | 2026-06-01 04:00:34 | 2026-08-29 22:56:47 |
| B | Transurbano | 28 | 30 | 2026-06-01 04:00:24 | 2026-08-29 22:57:03 |
