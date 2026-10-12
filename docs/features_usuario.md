# Features de usuario (2.3)

**Resultado posterior al build:** 70,380 filas y 70,380 identidades unicas; 0 nulos en las 25 columnas; 36,827 identidades multimodales. Estos son resultados consultados, no una cifra asumida del modelo anterior.

Grano: una fila por `usuario_canonico_id` con eventos disponibles al corte. Tabla materializada en `silver.silver_features_usuario`, construida exclusivamente desde las cuatro operaciones Silver, `bridge_identidad_usuario` y `silver_catalogo_puntos`; no lee Gold ni Staging directamente.

Cutoff real verificado en PostgreSQL: **2026-07-15 23:44:33**, hora local Guatemala (UTC-6, timestamp sin huso). Minimo global: **2026-06-01 04:00:00**. Se consideran los timestamps TM/TU/AM y tanto ingreso como salida MR. El SQL calcula el maximo al construir, lo guarda en `fecha_corte` y filtra `fecha_hora <= fecha_corte`. MR exige ademas `fecha_hora_salida <= fecha_corte`: su tarifa y trayecto cerrado no se usan antes del cierre. Para repetir un snapshot ante nuevas fuentes, fijar `--vars '{features_cutoff: "2026-07-15 23:44:33"}'`.

Las ventanas son intervalos de tiempo `(cutoff - N dias, cutoff]`, no fechas calendario completas. `dias_desde_ultimo_evento` y `span_dias_uso` son dias completos transcurridos. Hora pico: lunes a viernes, horas 06, 07, 08, 17, 18 y 19, sin calendario de feriados. Empates de modo/zona: conteo DESC y nombre ASC. No se afirma que un snapshot retrospectivo resuelva por si solo la validacion temporal de un modelo: etiquetas y particiones futuras tambien deben evitar fuga de informacion.

TM/TU/AM representan abordajes; MR representa viajes completos, fechados por ingreso y contados una sola vez. Su suma se llama eventos de movilidad registrados, no viajes puerta-a-puerta comparables. La zona MR es la del origen; los demas modos usan el catalogo Silver del punto.

## Diccionario

| Columna | Tipo PostgreSQL | Definicion exacta |
|---|---|---|
| `usuario_canonico_id` | text | Identidad Silver USR- o AM- del puente; una fila por identidad con eventos disponibles al corte, no persona confirmada. |
| `metodo_match` | text | MIN del metodo del puente para eventos incluidos; AM HASH_AISLADO; TM/TU/MR PATRON_NUMERICO_INFERIDO. |
| `nivel_confianza` | text | MIN de la etiqueta del puente; ALTO_LOCAL o INFERENCIA_ACADEMICA_MEDIA, no probabilidad calibrada. |
| `fecha_corte` | timestamp | Maximo timestamp local real de las cuatro fuentes Silver, incluyendo salida MR; override features_cutoff opcional. |
| `total_eventos` | bigint | COUNT(*) de abordajes TM/TU/AM y viajes completos MR disponibles al corte. |
| `modos_utilizados` | integer | COUNT(DISTINCT modo) de eventos incluidos. |
| `es_multimodal` | boolean | modos_utilizados >1; AM permanece aislado. |
| `dias_activos` | bigint | COUNT(DISTINCT fecha_hora::date) de eventos incluidos. |
| `primer_evento` | timestamp | MIN(fecha_hora); MR usa ingreso. |
| `ultimo_evento` | timestamp | MAX(fecha_hora); MR usa ingreso. |
| `span_dias_uso` | integer | FLOOR de segundos entre ultimo y primer evento /86400; dias completos transcurridos. |
| `eventos_ultimos_7_dias` | bigint | COUNT de eventos en (fecha_corte -7 dias, fecha_corte]. |
| `eventos_ultimos_30_dias` | bigint | COUNT de eventos en (fecha_corte -30 dias, fecha_corte]. |
| `eventos_ultimos_90_dias` | bigint | COUNT de eventos en (fecha_corte -90 dias, fecha_corte]. |
| `modo_mas_usado` | text | Modo con mayor COUNT; desempate por nombre ASC. |
| `dias_desde_ultimo_evento` | integer | FLOOR de segundos entre fecha_corte y ultimo_evento /86400; dias completos. |
| `proporcion_eventos_hora_pico` | numeric | Eventos lunes-viernes en horas 06,07,08,17,18,19 /total; proporcion [0,1] sin redondeo. |
| `zona_origen_frecuente` | text | Zona del punto Silver TM/TU/AM o estacion origen MR mas frecuente; COUNT DESC, zona ASC. Ausencia de catalogo: ZONA_DESCONOCIDA. |
| `gasto_total_gtq` | numeric | ROUND(SUM(tarifa_quetzales),2) de eventos disponibles. |
| `tarifa_promedio_gtq` | numeric | ROUND(AVG(tarifa_quetzales),2) por evento; no tarifa integrada. |
| `eventos_transmetro` | bigint | COUNT filtrado a Transmetro; abordajes. |
| `eventos_transurbano` | bigint | COUNT filtrado a Transurbano; abordajes. |
| `eventos_aerometro` | bigint | COUNT filtrado a Aerometro; abordajes. |
| `eventos_metroriel` | bigint | COUNT filtrado a MetroRiel; viajes completos disponibles, fechados en ingreso. |
| `usa_aerometro` | boolean | eventos_aerometro >0; no demuestra adopcion por usuarios de TM/TU/MR. |

## Limite de identidad y uso predictivo

Aerometro conserva identidades `AM-<hash>`; TM/TU/MR usan `USR-<numero inferido>`. No existe enlace persona-a-persona de AM con otros sistemas. Sus identidades aparecen unimodales por construccion; esto no demuestra uso exclusivo real. El patron numerico de los otros modos tambien es una inferencia academica, no identidad comprobada.

Posible uso: predecir inactividad futura por identidad dentro de los sistemas enlazables usando recencia, frecuencia y regularidad, para orientar acciones de retencion de la Agencia; requiere etiquetas posteriores al corte y validacion temporal. No permite predecir adopcion personal cruzada de Aerometro con estas llaves.

Los conteos finales y las pruebas de reconciliacion se registran en `docs/metricas/validacion_fase2.json` y `docs/metricas/validacion_fase2.md`, tras el build real.
