# Proyecto 2 — Red Metropolitana de Transporte

## Guía de trabajo y estado del equipo

**Actualización:** 29 de octubre de 2026, hora de Guatemala.

**Curso:** Ciencia de Datos — Universidad Rafael Landívar.

**Equipo:** Jonatán, Héctor y Alejandro.

**Repositorio:** [TaTan09/red-metropolitana](https://github.com/TaTan09/red-metropolitana).

**Rama con la implementación conjunta disponible:** [p2/hector](https://github.com/TaTan09/red-metropolitana/tree/p2/hector).

**Referencia técnica verificada:** `781c758`; incluye el trabajo de Jonatán hasta `32838d0`.

> **Estado para el grupo:** 1.1 y 1.2 de Jonatán están implementados y fueron
> verificados nuevamente con los datos oficiales P2. Héctor terminó y publicó
> 1.3 (features A/B/C y auditoría con cero diferencias) y 2.3 (KMeans/PCA).
> El siguiente paso es publicar/verificar 1.4 y 2.1 de Alejandro. Sus
> predicciones fuera de fold de A permitirán continuar 2.2; el modelo y umbral
> finales permitirán cerrar 2.4 con Jonatán. B sigue reservado para el test único.

## 1. Estado actual y responsables

| Requisito | Responsable | Estado verificado | Próximo paso |
|---|---|---|---|
| 1.1 — Datos nuevos desde cero | Jonatán | Completado; Héctor repitió dos corridas con conteos y fingerprints iguales | Conservar el comando y la evidencia final |
| 1.2 — Unidad, población y etiqueta | Jonatán | Completado; A/B recalculados independientemente sin diferencias | Mantener las definiciones acordadas |
| 1.3 — Features y auditoría de fuga | Héctor | Completado y publicado en `p2/hector` | Usar esta tabla para los modelos |
| 1.4 — Baselines y logística regularizada | Alejandro | Sin entrega remota verificable en esta revisión | Publicar código, folds, métricas y predicciones OOF de A |
| 2.1 — Ensemble y sesgo-varianza | Alejandro | Sin entrega remota verificable en esta revisión | Reutilizar los folds de 1.4 y comparar modelos |
| 2.2 — Umbral por costos y test B | Héctor | Pendiente; no se ejecutó evaluación del clasificador en B | Recibir OOF de A y la selección del modelo |
| 2.3 — KMeans y PCA | Héctor | Completado y publicado en `p2/hector` | Incorporar resultados y acciones al informe |
| 2.4 — MLOps, `predecir.py` y C | Jonatán | Pendiente en el estado publicado revisado | Integrar modelo, preprocesamiento y umbral finales |

**Alcance de la revisión:** se actualizaron las referencias Git y se consultaron
los PR abiertos. Están publicadas `p2/jonatan` y `p2/hector`; no aparece
`origin/p2/alejandro` ni se encontraron PR abiertos. Esto no descarta trabajo
local de Alejandro: debe compartirlo o publicarlo para poder verificarlo.
No se ha fusionado este trabajo a `main`.

## 2. Arquitectura y datos oficiales P2

Se conserva el pipeline del Proyecto 1: Batch, Streaming, CDC, Bronze,
cuarentena, PostgreSQL, Kafka, Staging, dbt, Silver, Gold y Prefect.
Las features nuevas se calculan exclusivamente desde Silver.

Los datos P2 reemplazan completamente a P1. La entrada real del repositorio
es `data/raw/`, aunque el ZIP oficial organiza sus archivos bajo `datos_red/`.
Se verificaron los nueve archivos antes de cargar y se reinició el estado
generado. El Raw P1 quedó respaldado localmente y no se mezcló con P2.

| Archivo | Filas esperadas | Filas Bronze | Diferencia |
|---|---:|---:|---:|
| aerometro_boardings.csv | 387053 | 387053 | 0 |
| am_estaciones.csv | 14 | 14 | 0 |
| cdc_padron_usuarios.csv | 77636 | 77636 | 0 |
| metroriel_viajes.jsonl | 590844 | 590844 | 0 |
| mr_estaciones.csv | 22 | 22 | 0 |
| tm_estaciones.csv | 104 | 104 | 0 |
| transmetro_validaciones.csv | 713786 | 713786 | 0 |
| transurbano_transacciones.csv | 1635788 | 1635788 | 0 |
| tu_paradas.csv | 328 | 328 | 0 |

Comando validado desde cero, con Docker iniciado, `.env` configurado y
exactamente las nueve fuentes en Raw:

```powershell
python orchestration/flows/fase1_pipeline.py --fresh-start --evidence-prefix p2-equipo-002
```

`--fresh-start` reinicia Bronze, cuarentena, deduplicación, manifiestos,
artefactos dbt y los contenedores/volumen locales del proyecto; conserva Raw.
Después ejecuta dos corridas completas sin limpiar entre ellas.
Usar un prefijo nuevo para no sobrescribir evidencias.

La corrección de Jonatán en Transurbano utiliza `bronze_record_id` como
desempate estable al generar `id_transaccion`. Se conserva en `p2/hector`.

## 3. Unidad, población, cortes y etiqueta

**Unidad acordada: TARJETA**, identificada por `(operador, llave_operacional)`.
El identificador técnico es `MD5(operador || ':' || llave_operacional)`.
No se sustituye por `usuario_canonico_id`.

Una tarjeta entra en un corte si tiene al menos dos usos válidos en
`[fecha_corte - 28 días, fecha_corte)`, disponibles antes del corte y fuera
de cuarentena. En Transmetro, cualquier DELETE CDC anterior al corte excluye
la tarjeta, incluso si después hubo reactivación. Un DELETE futuro no decide
la población; no se consulta el estado vigente actual para reconstruir el pasado.

MetroRiel aporta un uso por viaje cerrado: se fecha por ingreso y se conoce
al salir. Un viaje que cierra exactamente en el corte o después no cuenta
para sus features. No se inventa un segundo uso al salir.

| Corte | Fecha local, 00:00 | Ventana máxima de features | Etiqueta / uso |
|---|---|---|---|
| A | 2026-07-01 | 3–30 de junio | 1–30 de julio; entrenamiento y validación |
| B | 2026-07-31 | 3–30 de julio | 31 de julio–29 de agosto; test final único |
| C | 2026-08-30 | 2–29 de agosto | NULL; predicción, septiembre no está observado |

En A/B, la etiqueta es 1 si la tarjeta no tiene usos válidos en los 30 días
que empiezan en el corte, y 0 si tiene alguno. Se conserva la convención de
disponibilidad de MetroRiel también para esa ventana. Los límites superiores
son exclusivos. En C no se calcula ni se inventa la etiqueta.

## 4. Resultados de población y costo de la unidad — 1.2

| Corte | Población | Positivos | Cuenta completa | Tasa positiva |
|---|---:|---:|---|---:|
| A | 77411 | 11211 | 11211 / 77411 | 14.4824 % |
| B | 76378 | 10312 | 10312 / 76378 | 13.5013 % |

El costo observable de elegir tarjeta se mide con el enlace **inferido** P1:
positivos cuya otra llave en otro operador mantiene actividad.

| Corte | Positivos | Con actividad en otro operador | Proporción |
|---|---:|---:|---|
| A | 11211 | 2394 | 2394 / 11211 = 21.3540 % |
| B | 10312 | 2394 | 2394 / 10312 = 23.2157 % |

Aerómetro sigue aislado. El enlace numérico entre los demás operadores no
es una identidad personal verificada; este costo no es una tasa exacta de
falsos abandonos de personas y no modifica las etiquetas.

## 5. Entrega de Héctor — 1.3 completo

Tabla para consumir: **`silver.silver_p2_features_tarjeta`**.
La población base sigue siendo `silver.silver_p2_poblacion_tarjeta`, ampliada
a C. Su clave es `(unidad_id, fecha_corte)`; una tarjeta puede tener tres filas.
El exportador y el costo descriptivo de 1.2 siguen limitados a A/B.

| Corte | Filas de features | Etiquetas nulas | Predictores nulos | Duplicados |
|---|---:|---:|---:|---:|
| A | 77411 | 0 | 0 | 0 |
| B | 76378 | 0 | 0 | 0 |
| C | 76420 | 76420 | 0 | 0 |

**Total: 230209 filas.** Las fechas se reciben por la variable dbt `p2_cortes`;
las mismas fórmulas se reutilizan en los tres cortes.

| Predictor | Qué mide | Ventana |
|---|---|---|
| viajes_28d | frecuencia de usos válidos | 28 días |
| viajes_7d | frecuencia reciente | 7 días |
| viajes_14d | frecuencia intermedia | 14 días |
| dias_activos_28d | fechas locales distintas con uso | 28 días |
| dias_desde_ultimo_uso | recencia en días fraccionarios | hasta 28 días |
| gasto_28d_gtq | suma de tarifas Silver | 28 días |
| tarifa_media_gtq | tarifa media por uso | 28 días |
| puntos_origen_28d | estaciones/paradas de origen distintas | 28 días |
| proporcion_hora_pico | proporción entre semana en [06:00,09:00) o [17:00,20:00) | 28 días |
| proporcion_fin_semana | proporción de usos en sábado/domingo | 28 días |
| operador | categoría operacional de la tarjeta | unidad del corte |

Las fuentes son las cuatro operaciones Silver mediante `silver_p2_usos_tarjeta`.
No se usan Gold, el bridge de identidad ni conteos futuros para predecir.
La diversidad de modos sería siempre 1 al trabajar por operador/tarjeta;
no se inventó una variable transversal que cambiara la unidad acordada.

La tabla contiene `unidad_id`, `corte`, `fecha_corte`, `operador`, las diez
features numéricas y `etiqueta`. Identificadores, fechas y etiqueta no son
predictores. `eventos_futuros_30d` pertenece al control de etiqueta de la
población y no se entrega como feature.

[Diccionario, fuentes, decisiones y tres revisiones de 1.3](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/features_p2_13.md).

## 6. Auditoría y pruebas realmente ejecutadas

- Auditoría oficial P2: **77411 tarjetas × 11 predictores, cero diferencias**
  entre Silver completo y copias físicamente recortadas antes del corte A.
- Se recalculan usos, población y features; se comparan claves y columnas sin
  redondear. La etiqueta se verifica aparte porque necesita el horizonte futuro.
- Un control positivo introduce fuga deliberada y comprueba que la prueba la detecte.
- Dos builds independientes conservaron exactamente las huellas de las
  **230209 filas A/B/C**, incluidas sus etiquetas.
- Suite final: **87 pruebas correctas, sin omitidas**.
- Cada build dbt: **183 pruebas + 34 modelos + 1 hook correctos**;
  `PASS=218`, `WARN=0`, `ERROR=0`, `SKIP=0`.
- Flujo completo: dos corridas **IGUALES**, con nueve diferencias Bronze iguales a cero.
- Verificación independiente de 1.2: cero diferencias de población, etiquetas
  y costo A/B; el desglose excluye C para no presentar su etiqueta NULL como cero positivos.

Tiempos locales medidos: preparación desde cero 44.87 s; corrida 1, 2849.60 s;
corrida 2, 1269.73 s. Las features tardaron 35.14 s y 38.37 s, respectivamente.
Son medidas del equipo utilizado, no tiempos garantizados para otras máquinas.

Evidencia final para citar:

- [Auditoría oficial P2](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/evidencias/p2-13-auditoria-p2.json).
- [Resumen y huellas A/B/C](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/metricas/p2-13-features.json).
- [Idempotencia de features tras dos builds](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/evidencias/p2-13-idempotencia-p2.json).
- [Idempotencia del flujo completo y tiempos](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/evidencias/p2-hector-001-idempotencia.md).

El archivo `p2-13-auditoria-diagnostico-p1.json` es histórico P1: **no usarlo
como evidencia oficial P2**. Tampoco usar reportes antiguos que indiquen
`DIFERENTES` y fueron anteriores a corregir el desempate de Transurbano.

## 7. Entrega de Héctor — 2.3 completo

KMeans y PCA usan las diez features numéricas **sólo de A**, escaladas con
StandardScaler. `operador` se excluye de la distancia euclídea; etiquetas,
identificadores y fechas no participan en el ajuste.

- Se evaluaron k=2..8, con 20 inicializaciones y semilla 2026.
- Se eligió **k=2**, con silueta **0.4929** sobre una muestra uniforme fija de
  3000 tarjetas A, compartida entre todos los candidatos.
- El codo geométrico sugiere **k=4**. Se documentó la discrepancia y se priorizó
  la mayor silueta; no se usaron etiquetas para elegir k.
- PCA: PC1 **50.7014 %**, PC2 **14.6441 %**, total **65.3454 %** de varianza.

| Segmento | Nombre | Tarjetas | Viajes 28d, mediana | Recencia, mediana | Abandono descriptivo A |
|---|---|---:|---:|---:|---|
| S0 | Uso ocasional y con pausa mayor | 69027 | 6 | 3.7669 días | 11055 / 69027 = 16.0155 % |
| S1 | Uso frecuente y reciente | 8384 | 40 | 0.4111 días | 156 / 8384 = 1.8607 % |

Acciones propuestas: para S0, recarga de retorno limitada y recordatorio tras
una pausa; para S1, beneficio por continuidad o abono en puntos habituales.
Las tasas son descriptivas, no prueban causalidad ni efectividad de las acciones.

Dos ejecuciones completas reprodujeron exactamente métricas, asignaciones,
coordenadas PCA y los tres PNG. Las asignaciones completas quedan localmente
en `datos_red/p2-23-asignaciones.csv`; los agregados y gráficos están versionados.

[Método, reproducción y limitaciones](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/segmentacion_p2_23.md) ·
[Gráficos y resultados](https://github.com/TaTan09/red-metropolitana/blob/p2/hector/docs/metricas/p2-23-segmentacion/resumen.md).

El segmento no se ha incorporado al clasificador. Si se incorpora después,
StandardScaler y KMeans deben ajustarse dentro de cada fold de validación.

## 8. Próxima entrega de Alejandro — 1.4 y 2.1

El bloqueo de features ya está resuelto. Alejandro puede partir del código
publicado en `p2/hector` y consumir **sólo A**:

```sql
select *
from silver.silver_p2_features_tarjeta
where corte = 'A';
```

Para 1.4 debe entregar dos baselines —tasa positiva de A y puntaje de una
feature—, al menos dos penalizaciones de logística, elección de regularización,
curva de la métrica frente a lambda e interpretación de coeficientes.
Todos deben utilizar los mismos cinco folds estratificados de A y una métrica
justificada con media y desviación estándar.

Para 2.1 debe agregar el ensemble, comparar entrenamiento/validación y
sesgo-varianza, calcular importancia por permutación en validación y justificar
el modelo seleccionado. El preprocesamiento se ajusta dentro de cada fold.
La codificación de `operador`, si se utiliza, también va dentro del pipeline.

**Para desbloquear 2.2, compartir:**

- Código y commit reproducible de los modelos y sus parámetros seleccionados.
- Asignación de folds y semilla para reutilizar exactamente la validación.
- Predicciones OOF de A: `unidad_id`, `fecha_corte`, fold, etiqueta real,
  modelo y probabilidad de abandono, con una predicción por tarjeta/modelo.
- Métrica media/desviación y evidencia de que cada predicción OOF procede
  de un modelo que no entrenó con esa tarjeta.

B no se usa para seleccionar features, modelo, regularización ni parámetros.

## 9. Próxima entrega de Héctor — 2.2

Se hará después de recibir los modelos y OOF de A. El escenario es Q5 por
contacto, retención del 25 % de quienes se irían y Q60 por usuario retenido.
Hay que derivar la ganancia, elegir el umbral con OOF A y guardar la curva.
**El umbral final todavía no se ha seleccionado.**

Una vez fijado modelo y umbral: entrenar con todo A, evaluar **una sola vez**
en B y registrar fecha, commit, métrica, matriz de confusión y ganancia.
Si B empeora, se explica; no se vuelve a ajustar usando B.

Los conteos de etiquetas B de 1.2 y las comprobaciones de integridad no son
una evaluación del clasificador. Esa evaluación de 2.2 sigue pendiente.

## 10. Próxima entrega de Jonatán — 2.4

Puede preparar la interfaz y la integración con las features ya estables.
El cierre requiere el modelo, preprocesamiento y umbral finales de 2.1/2.2.

- Guardar el pipeline completo del modelo con versión y dependencias fijas.
- Implementar `predecir.py --datos <carpeta> --fecha-corte 2026-08-30`, cargando
  el modelo guardado sin reentrenarlo.
- Generar C con `unidad_id`, `tarjetas`, `puntaje` y `contactar`, una fila por
  unidad elegible. La población actual C tiene 76420 tarjetas.
- Recuperar las llaves originales desde `silver_p2_poblacion_tarjeta`;
  `unidad_id` no sustituye el campo `tarjetas` del CSV requerido.
- Incorporar las tareas nuevas al flujo y completar la ficha del modelo.
- Verificar invariancia de predicciones C al agregar los 30 días posteriores.

La auditoría A de 1.3 no sustituye la prueba completa de predicciones C de 2.4.
Todavía no se han entregado esas predicciones ni se ha elegido su umbral.

## 11. Coordinación Git e integración

La referencia compartida actual es `p2/hector`: incluye los commits de Jonatán
con su autoría conservada y los de Héctor para 1.3/2.3. Actualizar únicamente
desde `main` todavía no aporta estas features, porque no se han fusionado allí.

Cada integrante integra en **su propia rama**, con el árbol de trabajo limpio:

```powershell
git fetch origin
git switch p2/alejandro
git merge origin/p2/hector
```

Para Jonatán, usar su rama en el segundo comando. Si Alejandro aún no tiene
una rama local, puede crearla con `git switch --no-track -c p2/alejandro origin/p2/hector`
en lugar de `git switch p2/alejandro` y del merge inicial.
Resolver cualquier conflicto revisando cambios y pruebas; no copiar archivos
manualmente ni sobrescribir el trabajo de otro integrante.

Para publicar por primera vez, Alejandro usa `git push -u origin p2/alejandro`;
los demás utilizan el nombre de su propia rama.
Cada integrante realiza sus commits descriptivos y push a su rama. Revisar
`git status`, `git diff` y lo preparado antes de confirmar. No hacer push
forzado, no borrar ramas ajenas y no incluir `.env`, ZIP, Raw, Bronze ni bases.
La integración a `main` debe acordarse mediante revisión y PR.

Los commits propios de Héctor hasta la validación técnica son:
`fd3c34e`, `60af59e`, `af7780f`, `0cbf7ff`, `0a9501f`, `1056618`,
`60a7de9`, `f91e073` y `781c758`. La actualización de esta guía se versiona aparte.

Si se usa un asistente, las autorizaciones de commit/push deben ser explícitas
para esa sesión y rama. Héctor las dio para `p2/hector`; no implican permiso
para modificar `main` ni las ramas de los compañeros.

## 12. Reproducción y próximos pasos del grupo

Con Silver P2 ya reconstruido, estos comandos regeneran las entregas sin
volver a cargar todo el lake. Instalar el entorno y configurar `.env` primero:

```powershell
python -m pip install -r requirements-ml.txt
python scripts/run_dbt.py build --select tag:p2_12 tag:p2_13 --threads 1
python scripts/auditar_fuga_p2_13.py --output docs/evidencias/p2-equipo-auditoria.json --dataset-label proyecto-2-verificado
python scripts/generar_evidencia_p2_13.py --output datos_red/p2-equipo-features.json
python scripts/segmentar_p2_23.py --output-dir datos_red/p2-equipo-segmentacion --assignments datos_red/p2-equipo-segmentos.csv
$env:P2_TEST_POSTGRES='1'
python -m unittest discover -s tests -v
```

Entorno validado: Python 3.12 en Windows/PowerShell. Usar destinos nuevos;
los scripts protegen los resultados existentes contra sobrescritura.

Secuencia inmediata:

1. Alejandro publica o comparte su avance y confirma integración de las features.
2. Alejandro completa/verifica 1.4 y 2.1 y entrega OOF de A.
3. Héctor realiza 2.2 con esas OOF; B se mantiene reservado hasta ese punto.
4. Jonatán cierra 2.4 con el modelo y umbral finales y entrega predicciones C.
5. El equipo integra el informe, revisa la ficha y prepara la defensa conjunta.

**Para la defensa:** todos deben poder explicar la unidad tarjeta, su costo,
las ventanas y etiquetas, el recorte con cero diferencias, por qué B se usa
una sola vez, la selección de modelos/umbral, k=2 frente al codo k=4,
la varianza PCA y la futura prueba de invariancia de C. La división del
desarrollo no divide la responsabilidad de la defensa.
