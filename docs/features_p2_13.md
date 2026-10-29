# Requisito 1.3: features por tarjeta y auditoría temporal

## Estado y dependencias

Implementación disponible en `p2/hector`, basada en `origin/p2/jonatan`
(`32838d0`). Se conservan sus commits y autoría; no se modifica `main` ni
la rama de Jonatán. No se encontró un pull request del Proyecto 2 en GitHub
durante la consulta del 29 de octubre de 2026.

**1.3 está materializado y auditado sobre los datos oficiales del Proyecto 2.**
El ZIP se verificó fila por fila antes de reemplazar Raw, y Silver se reconstruyó
con el reinicio del pipeline de Jonatán. El Raw previo se conserva localmente en
`datos_red/respaldo-p1-20261029`, fuera de Git. Los conteos comprobados son:

| Fuente Raw | Filas P1 respaldadas | Filas P2 verificadas |
|---|---:|---:|
| Transmetro | 363221 | 713786 |
| Transurbano | 832791 | 1635788 |
| Aerómetro | 203554 | 387053 |
| MetroRiel | 299100 | 590844 |
| CDC | 31050 | 77636 |

Antes del reemplazo, Silver Transmetro tenía 362106 filas y terminaba el 15 de
julio de 2026. Esa discrepancia se detectó y se corrigió reemplazando íntegramente
el dataset, sin mezclarlo con P2. La evidencia diagnóstica P1 se conserva como
histórico separado de la auditoría oficial.
El PDF oficial se recibió y revisó completo el 29 de octubre de 2026, después
de la implementación inicial. Se inspeccionaron también las páginas renderizadas
5, 8 y 11. Sus reglas de 1.3 coinciden con el contrato implementado. El ZIP
suministrado contiene los nueve nombres y su LEEME coincide con los conteos
verificados. Los catálogos tienen 104/328/22/14 filas para TM/TU/MR/AM.

### Contraste con el enunciado oficial

| Regla del PDF | Implementación / estado |
|---|---|
| Cortes A 1/jul, B 31/jul y C 30/ago, a medianoche local (p. 5) | Parámetro `p2_cortes`, con las tres fechas predeterminadas |
| Tarjeta es una unidad permitida, midiendo su costo (pp. 6–7) | Se conserva la unidad acordada en 1.2 y su tabla de costo descriptivo |
| Una tabla con filas por unidad/corte, ventanas iguales entre cortes y de máximo 28 días (pp. 7–8) | Modelo `silver_p2_features_tarjeta`; fórmulas idénticas con ventanas 7/14/28 |
| Sólo registros válidos y fuera de cuarentena (p. 7) | Vista de usos Silver con exclusión por operador e ID Bronze |
| Etiqueta A para entrenar, B reservada a 2.2 y C vacía (p. 8) | Se conserva A/B, C NULL; no se ejecutó evaluación de modelos en B |
| Recorte antes de julio y comparación idéntica con lista de features que fallaron (p. 8) | Auditoría P2: 77411 filas, 11 predictores, 0 diferencias; ninguna feature falló con el SQL final |
| Diccionario con significado, ventana y fuente Silver (p. 8) | Tablas del diccionario de este documento |
| KMeans escalado sólo en A, codo, silueta, PCA, medianas y acciones (p. 11) | Siguiente entrega, separada de 1.3 |

El PDF menciona `datos_red/` como entrada genérica (p. 4). Se conserva
`data/raw/`, entrada real del pipeline P1, según el pedido y la guía del equipo;
no se reestructura la arquitectura. Los nombres, formatos y reemplazo íntegro
del dataset se mantienen.

### Resultado materializado de 1.3

| Corte | Filas | Etiquetas nulas | Predictores nulos | Claves duplicadas |
|---|---:|---:|---:|---:|
| A | 77411 | 0 | 0 | 0 |
| B | 76378 | 0 | 0 | 0 |
| C | 76420 | 76420 | 0 | 0 |

Total: 230209 filas. La primera materialización de las features tardó 35.14 s
según el log dbt; el cálculo de población es una etapa separada. Ver
[`metricas/p2-13-features.json`](metricas/p2-13-features.json) para el resumen
y SHA-256 de las filas ordenadas de cada corte, incluyendo etiquetas. El
generador falla ante duplicados, predictores nulos, cortes vacíos o etiqueta C.

## Contrato

Tabla de salida: `silver.silver_p2_features_tarjeta`.
Una fila por `(unidad_id, fecha_corte)`, con índice único dbt sobre esa pareja.
`unidad_id = md5(operador || ':' || llave_operacional)` conserva la unidad
TARJETA de 1.2. Se reutiliza `silver_p2_poblacion_tarjeta`, ampliada a C,
sin alterar las reglas de población y etiquetas A/B.

Las fechas tienen una única definición en `p2_12_cortes.sql`, configurable
con la variable dbt `p2_cortes`. Valores predeterminados:

| Corte | Fecha de corte | Uso | Etiqueta |
|---|---|---|---|
| A | 2026-07-01 | entrenamiento | 1.2, horizonte de 30 días |
| B | 2026-07-31 | test final | 1.2, horizonte de 30 días |
| C | 2026-08-30 | predicción | NULL, sin consultar su horizonte futuro |

Toda ventana es `[fecha_corte - N días, fecha_corte)`, con N de 7, 14 o 28.
Se exige también `disponible_desde < fecha_corte`. Un viaje cerrado de
MetroRiel cuenta una vez, por ingreso; sólo se conoce al salir. No se toma
un viaje que cierra exactamente en el corte. Las horas Silver ya están en
hora local; Aerómetro reutiliza su conversión UTC a Guatemala del Proyecto 1.

Se conserva la política CDC: cualquier DELETE Transmetro anterior al corte
excluye, incluso si hubo reactivación; un DELETE futuro no decide población.
Los IDs en cuarentena se excluyen con NOT EXISTS por operador y registro
Bronze. La cuarentena no multiplica registros por motivos de rechazo.

## Fuentes y diccionario

`silver_p2_usos_tarjeta` reutiliza las cuatro fuentes operacionales Silver y
ahora expone `tarifa_quetzales` y `punto_origen`, además de fechas y claves:

| Fuente Silver | Llave | Fecha del uso | Disponibilidad | Punto de origen |
|---|---|---|---|---|
| silver_transmetro_validaciones | tarjeta_id | fecha_hora | fecha_hora | estacion_id |
| silver_transurbano_transacciones | id_tarjeta | fecha_hora | fecha_hora | cod_parada |
| silver_aerometro_boardings | user_hash | fecha_hora | fecha_hora | station_code |
| silver_metroriel_viajes | tarjeta_mr | fecha_hora_ingreso | fecha_hora_salida | origen_estacion_id |

Todas las fuentes aportan su tarifa Silver en quetzales. El modelo de features
no agrega imputaciones. Mantiene las tarifas normalizadas por Silver del P1.

| Predictor | Significado | Ventana | Campos de silver_p2_usos_tarjeta |
|---|---|---|---|
| viajes_28d | frecuencia total de usos válidos | 28 días | fecha_uso, disponible_desde |
| viajes_7d | frecuencia reciente | 7 días | fecha_uso, disponible_desde |
| viajes_14d | frecuencia intermedia | 14 días | fecha_uso, disponible_desde |
| dias_activos_28d | fechas locales distintas con uso | 28 días | fecha_uso |
| dias_desde_ultimo_uso | tiempo desde el último ingreso/uso, en días fraccionarios | 28 días | max(fecha_uso) |
| gasto_28d_gtq | suma de tarifas válidas | 28 días | tarifa_quetzales |
| tarifa_media_gtq | promedio de tarifas por uso | 28 días | tarifa_quetzales |
| puntos_origen_28d | estaciones/paradas de origen distintas | 28 días | punto_origen |
| proporcion_hora_pico | usos de lunes a viernes a las 06–08 o 17–19 horas / total | 28 días | fecha_uso |
| proporcion_fin_semana | usos sábado o domingo / total | 28 días | fecha_uso |
| operador | categoría operacional observada de la tarjeta | unidad del corte | operador |

Hora pico conserva la definición del P1: intervalos horarios [06:00,09:00)
y [17:00,20:00) entre semana. No infiere festivos ni usa información externa.
La diversidad de modos sería siempre 1 bajo la unidad `(operador, llave)`;
por eso no se incluye. Unir tarjetas mediante el bridge para calcularla
cambiaría la unidad acordada y asumiría identidad personal no verificada.

`unidad_id`, `corte` y `fecha_corte` son identificadores/metadatos, no
predictores. `etiqueta` es la variable objetivo. `eventos_futuros_30d`, el
costo de falsos abandonos y los atributos del bridge no salen a la tabla
de features. No se consume Gold.

## Regeneración

Primero instalar `requirements.txt`, configurar `.env` y reconstruir el
pipeline con los nueve archivos nuevos usando el procedimiento 1.1 del README.
Verificar que sus conteos y cobertura corresponden al Proyecto 2. Después:

```powershell
python scripts/run_dbt.py build --select tag:p2_12 tag:p2_13 --threads 1
python scripts/generar_evidencia_p2_13.py --output docs/metricas/p2-13-features.json
python scripts/auditar_fuga_p2_13.py --output docs/evidencias/p2-13-auditoria-p2.json --dataset-label proyecto-2-verificado
$env:P2_TEST_POSTGRES='1'
python -m unittest discover -s tests -v
```

La tabla resultante contiene los tres cortes; los datos por tarjeta se
mantienen en PostgreSQL, sin subir datasets a Git. dbt construye y comprueba
los modelos seleccionados. No se antepone `+` al selector: se reutiliza el
Silver operacional ya reconstruido por 1.1 y no se reconstruye Gold.

Para otros cortes, tanto dbt como la auditoría aceptan el mismo JSON:

```json
{"p2_cortes": {"A": "2026-07-01", "B": "2026-07-31", "C": "2026-08-30"}}
```

Pasarlo con `--vars` en ambas órdenes. Los nombres A/B/C conservan su función.
El exportador de 1.2 mantiene su verificación oficial A/B; C no se compara
contra el universo A/B ni se interpreta como abandono observado.

## Auditoría reproducible

`scripts/auditar_fuga_p2_13.py` renderiza y ejecuta los tres modelos SQL reales
(usos, población y features). No implementa otra fórmula de features en Python.
En una transacción REPEATABLE READ:

1. Recalcula población y features A desde Silver completo.
2. Crea copias TEMP de las cuatro fuentes eliminando físicamente usos futuros;
   en MR elimina también viajes sin cierre anterior al corte. Recorta CDC por
   `valid_from`, conservando sólo los eventos anteriores.
3. Recalcula usos, población y features con esas copias.
4. Compara por `(unidad_id, fecha_corte)`, todas las columnas predictoras,
   sin redondear los NUMERIC de PostgreSQL. Detecta filas ausentes y duplicadas.
5. Reporta filas, columnas, diferencias por columna, registros retirados y
   hashes SHA-256 del SQL. Revierte las tablas temporales.

Las etiquetas se excluyen de esta comparación porque requieren los 30 días
posteriores; se comprueban por separado contra la población y con pruebas
conocidas. C siempre tiene etiqueta NULL. Una comparación vacía, un dataset
sin registros futuros o un cambio de esquema sin actualizar las columnas
auditadas provoca error. El archivo se crea exclusivamente y no sobrescribe
evidencia anterior; diferencias generan salida de proceso distinta de cero.

La cuarentena Silver se mantiene como conjunto de exclusiones por ID. El
alcance es la capa Silver operacional y CDC: no certifica invariancia de la
ingesta, deduplicación o reconstrucción de Silver desde Staging ante llegadas
tardías. `disponible_desde` representa la disponibilidad de negocio definida
en 1.2, no el momento de ingesta real ni un historial de snapshots operativos.

Evidencia diagnóstica real en
[`evidencias/p2-13-auditoria-diagnostico-p1.json`](evidencias/p2-13-auditoria-diagnostico-p1.json):
113785 filas, 11 columnas predictoras (10 numéricas y operador), 0 diferencias.
Es Proyecto 1, **no evidencia final del Proyecto 2**.

La evidencia oficial está en
[`evidencias/p2-13-auditoria-p2.json`](evidencias/p2-13-auditoria-p2.json):
77411 filas y 11 predictores comparados, **0 diferencias**. Se retiraron
480816 registros TM, 1092549 TU, 260677 AM, 393884 MR y 36883 eventos CDC de
las copias recortadas. No se detectaron features con fuga en el SQL final.
El control positivo que introduce fuga deliberadamente pertenece a las pruebas;
no se presenta como un defecto encontrado en esos datos reales.

## Tres revisiones realizadas

| Enfoque | Problema concreto | Corrección y verificación |
|---|---|---|
| Corrección funcional | 1.2 sólo tenía A/B; C habría recibido etiqueta observada | C comparte la selección de población y tiene etiqueta y conteo futuro NULL; prueba PostgreSQL de los tres cortes |
| Corrección funcional | Incorporar C hacía que el verificador A/B de 1.2 reportara filas sobrantes | Su FULL JOIN limita la población a A/B; 21 pruebas previas de 1.2 pasan |
| ML y temporalidad | P1 utiliza persona inferida, ventanas 30/90 y límites inclusivos | Tarjeta de 1.2, ventanas 7/14/28, límites superiores estrictos y disponibilidad de cierre MR; pruebas de fronteras y gasto |
| ML y temporalidad | Comparar etiqueta en el recorte exigiría datos futuros | La auditoría compara sólo predictores y población; A/B se prueban separadamente, C es NULL |
| ML y temporalidad | Un resultado cero podría venir de una auditoría que nunca detecta fugas | Control positivo elimina los filtros temporales del SQL; detecta diferencias en viajes y gasto |
| Ingeniería | Una feature añadida podría quedar fuera de una lista antigua | El comparador exige que el esquema coincida exactamente con todas las columnas declaradas |
| Ingeniería | Una comparación vacía o evidencia sobrescrita podría aparentar éxito | Rechazo de entradas vacías/duplicadas, futuro inexistente y archivo existente; transacción temporal revertida |
| Ingeniería | Datos locales antiguos podrían presentarse como resultados P2 | Se respaldó P1 y se cargó exclusivamente el ZIP P2 verificado; auditoría oficial separada del diagnóstico histórico |

Validación ejecutada el 29 de octubre de 2026:

- Suite completa con `P2_TEST_POSTGRES=1`: 81 pruebas, todas correctas, sin omitidas.
- Incluye 11 nuevas de 1.3: 3 del comparador y 8 contra PostgreSQL real con
  fuentes TEMP controladas. Se ejecuta el SQL de integridad dbt y se verifica
  que detecte una etiqueta C incorrecta. Repetir la transformación da lo mismo.
- `dbt parse`: correcto; advertencias de sintaxis antigua `accepted_values`
  presentes en modelos p2_12 y p2_13, sin errores de parseo. Se mantiene la
  compatibilidad declarada con dbt >=1.9.
- `git diff --check`: correcto.
- `dbt build` materializó la población y las 230209 filas de features sobre P2;
  `p2_12_integridad` y `p2_13_integridad` pasaron contra esas tablas reales.
  La evidencia de las dos corridas completas de 1.1 se registra por separado
  con el prefijo `p2-hector-001` cuando termina la segunda corrida.
- Dos pruebas nuevas comprueban la huella del resumen y sus errores ante
  cortes faltantes, duplicados, nulos y etiqueta C inválida.

## Pendientes y defensa oral

La tabla A/B/C y la auditoría oficial de 1.3 están completas. Continúa 2.3
(KMeans/PCA sobre A), en commits separados después de publicar esta evidencia.
La segunda corrida de 1.1 comprueba además la idempotencia del flujo completo.
No se implementó 2.2: aún no están disponibles modelos y predicciones OOF
de Alejandro. No se entrenaron modelos ni se usaron etiquetas B para elegir
features, hiperparámetros o umbrales.

Para explicarlo: tomo las tarjetas elegibles definidas por Jonatán y miro
únicamente sus últimos 28 días antes de cada corte. Resumo cuánto viajan,
qué tan reciente fue su uso, cuánto gastan y sus horarios/puntos de origen.
Un viaje de MetroRiel sólo cuenta si ya había terminado. La etiqueta A/B
viene de los 30 días posteriores y se conserva separada de los predictores;
en C aún no se conoce. Para demostrar que el futuro no contamina las
features, borro físicamente ese futuro de copias temporales y vuelvo a
calcular: cada tarjeta y cada predictor deben quedar exactamente iguales.
