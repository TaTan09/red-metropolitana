# Marts y vistas Gold

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
| puntos_transmetro, puntos_transurbano, puntos_metroriel, puntos_aerometro | Desglose de `puntos_transporte` por modo, desde `dim_zona`; la suma de los cuatro es `puntos_transporte` |
| eventos_totales | Suma de `cantidad_eventos` de la zona |
| eventos_transmetro, eventos_transurbano, eventos_metroriel, eventos_aerometro | Desglose por modo; la suma de los cuatro es `eventos_totales` |
| eventos_por_punto | `eventos_totales` / `puntos_transporte`; NULL si la zona no tiene puntos. **Mezcla unidades y modos**: para comparar usar los ratios por modo |
| eventos_por_punto_transmetro, eventos_por_punto_transurbano, eventos_por_punto_aerometro | Abordajes del modo / puntos del mismo modo; NULL si la zona no tiene puntos de ese modo |
| viajes_por_estacion_metroriel | Viajes iniciados en la zona (origen) / estaciones MetroRiel de la zona; NULL si no hay estaciones |
| pct_demanda_red | Participación de la zona en el total de eventos de la red |
| ranking_demanda | Posición por `eventos_totales` (empates comparten posición) |
| inconsistencia_cobertura | true si la zona tiene servicio y cero eventos, o no tiene servicio y tiene eventos |

**Reglas heredadas:** MetroRiel cuenta una vez por viaje, en el ingreso y en
la zona de origen. La zona destino no se cuenta aquí.
Los `puntos_*` salen de `dim_zona`, que los calcula en `silver_universo_zonas`
desde `silver_catalogo_puntos` (oferta, no actividad).

**Advertencias:**
- `eventos_totales` mezcla abordajes (TM/TU/AM) con viajes (MR). No es una
  cantidad de personas ni de viajes. `pct_demanda_red` hereda la misma mezcla.
- `tiene_servicio` sale de los catálogos, no de la actividad. Una zona sin
  servicio tiene cero eventos por construcción, así que el mart muestra dónde
  NO hay servicio, pero no mide demanda potencial ni dónde hace falta
  servicio. Esa pregunta no se puede responder con estas fuentes.
- El universo de 16 zonas viene del generador entregado (`silver_universo_zonas`),
  no de un catálogo oficial externo.
- `eventos_por_punto` divide eventos de cuatro modos entre puntos de cuatro modos,
  y las redes son muy desiguales (328 paradas TU contra 22 estaciones MR), así
  que en la práctica tiende a reflejar cuántas paradas de bus tiene la zona. Para comparar
  rendimiento entre zonas o modos se usan los ratios por modo. El de MetroRiel
  mide viajes iniciados por estación, no abordajes.

**Reconciliación:** `sum(eventos_totales)` = `sum(cantidad_eventos)` de
`mart_demanda_hora` (1,688,959 hoy), en total y por modo.

**Pruebas:** `mart_cobertura_grano`, `mart_cobertura_reconciliacion`,
`mart_cobertura_consistencia`, `mart_cobertura_puntos_por_modo` (los puntos por
modo suman el total de cada zona y cuadran con `dim_punto_transporte`: 104, 328,
22 y 14) y pruebas de unicidad y no nulos en `schema.yml`.

## Vistas para Tableau (`v_tableau_*`)

Tableau se conecta a estas vistas, no a los `mart_*`. Las vistas separan abordajes
y viajes para que ninguna visualización pueda sumar unidades distintas sin querer.

Son vistas dbt (`materialized='view'`) en el esquema `gold`, sin lógica propia más
allá de filtrar, renombrar y calcular rankings. No contienen identificadores de usuario.

### v_tableau_demanda_abordajes

**Pregunta que responde:** demanda por modo, zona y hora de Transmetro, Transurbano y Aerómetro.

**Grano:** fecha × hora × modo × zona (el de `mart_demanda_hora`, filtrado a `tipo_evento = 'abordaje'`).

| Columna | Descripción |
|---|---|
| fecha, hora, es_dia_habil, es_hora_pico | Desde `dim_tiempo` |
| franja | `Hora pico` o `Fuera de pico`. Como la hora pico solo existe en días hábiles, `Fuera de pico` incluye fines de semana |
| modo, zona | Modo y zona de acceso |
| cantidad_abordajes | Aditiva. Accesos válidos |
| tarifa_total_gtq | Aditiva. Suma de importes registrados |

### v_tableau_demanda_viajes_mr

**Pregunta que responde:** cuándo y dónde empiezan los viajes de MetroRiel.

**Grano:** fecha × hora × zona de origen (`mart_demanda_hora` filtrado a `tipo_evento = 'viaje'`).

| Columna | Descripción |
|---|---|
| fecha, hora, es_dia_habil, es_hora_pico, franja | Igual que la vista de abordajes |
| modo | Siempre `MetroRiel` |
| zona_origen | Zona de la estación de ingreso |
| viajes_iniciados | Aditiva. Un viaje cuenta una vez, en su ingreso |
| tarifa_total_gtq | Aditiva. Suma de importes registrados |

**Regla:** la zona es la de origen. La columna se llama `zona_origen` para que no se
lea como demanda en la zona. Un viaje que termina en otra zona no se cuenta en ella.

### v_tableau_cobertura

**Pregunta que responde:** dónde hay servicio, qué modos lo dan y cuánta actividad se
observa por zona, sin mezclar unidades.

**Grano:** una fila por zona de `dim_zona` (16 hoy).

| Columna | Descripción |
|---|---|
| nombre_zona, tipo_area, tiene_servicio, modos_con_servicio | Oferta, desde `dim_zona` |
| puntos_transporte, puntos_transmetro, puntos_transurbano, puntos_metroriel, puntos_aerometro | Puntos de la zona, total y por modo |
| abordajes, abordajes_transmetro, abordajes_transurbano, abordajes_aerometro | Abordajes TM/TU/AM; `abordajes` es la suma de los tres |
| viajes_mr_iniciados | Viajes MetroRiel iniciados en la zona (origen) |
| eventos_por_punto_transmetro, eventos_por_punto_transurbano, eventos_por_punto_aerometro | Abordajes por punto del mismo modo |
| viajes_por_estacion_metroriel | Viajes iniciados por estación MetroRiel |
| pct_abordajes_red | Participación de la zona en los abordajes de la red |
| ranking_abordajes | Posición por `abordajes` (empates comparten posición) |
| ranking_viajes_mr_origen | Posición por `viajes_mr_iniciados` (empates comparten posición) |

**Qué no expone:** `eventos_totales`, `eventos_por_punto` ni `pct_demanda_red`,
porque mezclan abordajes con viajes.

**Caso MetroRiel (zonas 17, 12, 8, 6 y 1):** estas zonas encabezan
`ranking_viajes_mr_origen` en parte porque los viajes se cuentan en la zona de
origen, y las 22 estaciones están todas en esas cinco zonas. El ranking mide dónde
empiezan los viajes, no una demanda comparable con la de los otros modos.

**Limitación:** `tiene_servicio` sale de los catálogos de los operadores, no de la
actividad. La vista muestra dónde no hay servicio, pero no mide dónde hace falta.

### Reconciliación y pruebas

`v_tableau_reconciliacion`: `sum(cantidad_abordajes)` debe dar las filas de
`fact_abordajes` (1,393,448), y `sum(viajes_iniciados)` las de `fact_viajes_metroriel`
(295,511), tanto en las vistas de demanda como en la de cobertura.

## mart_metroriel_zonas

**Pregunta que apoya (enunciado 2.1):** «Dada la demanda observada en las zonas
12, 8, 1, 6 y 17, ¿el trazado propuesto atiende donde más se necesita?».
El mart aporta demanda observada de los otros modos y posición frente a toda la
red para analizar esa pregunta; no produce una recomendación sobre el trazado.

**Grano:** una fila por zona con al menos una estación MetroRiel, para todo el
período disponible en los hechos Gold. El trazado se deriva de
`dim_punto_transporte` con `modo = 'MetroRiel'`, agrupado por `zona_sk`; las
cinco zonas no están hardcodeadas en el modelo. Hoy son Zona 12, Zona 8, Zona 1,
Zona 6 y Zona 17, con 22 estaciones en total.

**Fuentes:** exclusivamente modelos Gold: `dim_zona` (universo de 16 áreas),
`dim_punto_transporte` (estaciones), `dim_modo` (clasificación de los abordajes),
`fact_abordajes` y `fact_viajes_metroriel`. Los hechos y las dimensiones siguen
construyéndose desde Silver; este mart no lee Silver, Staging, Bronze ni Raw.
Las agregaciones se realizan antes de unirlas por zona para evitar multiplicar
abordajes o viajes al enlazarlos con varias estaciones.

| Columna | Definición |
|---|---|
| zona_sk, nombre_zona | Clave y nombre de la zona en `dim_zona` |
| estaciones_metroriel | Número de estaciones del catálogo MetroRiel en la zona; mide oferta, no capacidad |
| abordajes_otros_modos | Suma de `cantidad_abordajes` de Transmetro, Transurbano y Aerómetro en la zona. Excluye los viajes MetroRiel |
| abordajes_transmetro, abordajes_transurbano, abordajes_aerometro | Desglose de la medida anterior por modo; su suma debe ser `abordajes_otros_modos` |
| viajes_metroriel_iniciados | Suma de `cantidad_viajes` por `zona_origen_sk`. Cada viaje se cuenta una vez en el origen, sin contar el destino |
| pct_abordajes_otros_modos_red | `100 × abordajes_otros_modos / total_abordajes_otros_modos_red`, redondeado a dos decimales; 0 si no existen abordajes en toda la red |
| ranking_demanda_otros_modos | `rank()` descendente por abordajes de otros modos, calculado sobre todas las áreas de `dim_zona`; los empates comparten puesto y dejan saltos |
| total_abordajes_otros_modos_red | Suma de abordajes TM/TU/AM en las 16 áreas; denominador de la participación, repetido en cada fila y no aditivo |
| areas_en_ranking_red | Tamaño del universo usado para calcular el ranking: 16 actualmente; no es el número de zonas MetroRiel y no es aditivo |

**Orden del cálculo:** primero se agregan abordajes por zona; después se incorporan
las 16 áreas con `left join`, incluyendo áreas con cero abordajes. Sobre ese
universo se calculan el total de red y el ranking. Solo al final se seleccionan
las zonas con estaciones MetroRiel. Así, por ejemplo, un puesto 9 sigue siendo
el puesto 9 de la red y no se convierte en el puesto 5 del trazado.

**Denominador:** «total de la red» significa aquí todos los abordajes de los
otros tres modos en el universo completo, no abordajes más viajes MetroRiel.
La participación de estas cinco zonas puede sumar menos de 100 % porque no
abarcan todas las áreas.

**Limitaciones:**

- La demanda observada **no equivale a demanda potencial**, necesidad insatisfecha
  ni cantidad de personas. Solo incluye eventos válidos que llegaron a Gold.
- «Demanda previa» se usa como aproximación mediante actividad de otros modos;
  los datos no demuestran que esos abordajes ocurrieran antes de la apertura de
  MetroRiel ni permiten atribuir efectos al trazado.
- MetroRiel mide **viajes iniciados** y los otros tres modos miden **abordajes**.
  No deben sumarse ni compararse como si fueran la misma unidad.
- El universo de 16 áreas proviene del generador del docente; las áreas sin
  servicio quedan con cero actividad observada, sin demostrar ausencia de demanda.
- Contar estaciones no mide frecuencias, capacidad, accesibilidad ni necesidades
  futuras. Un mayor número de abordajes tampoco demuestra por sí solo que el
  trazado sea óptimo.
- El mart resume todo el período: un filtro en Tableau sobre las cinco zonas no
  recalcula el ranking ni el denominador. Para analizar otro período sería
  necesario volver a calcular ambos sobre todo el universo de áreas.
- El linaje `bronze_record_id` permanece en los hechos Gold. El mart es agregado
  y su trazabilidad se reconstruye consultando esos hechos por zona y modo.

**Pruebas:** `mart_metroriel_zonas_grano` contrasta zonas y estaciones con el
catálogo y comprueba las cinco zonas actuales y el universo de 16 áreas;
`mart_metroriel_zonas_reconciliacion` reconcilia cada modo y los viajes por origen
con los hechos, verifica la suma de los tres modos y excluye MetroRiel de los
abordajes; `mart_metroriel_zonas_ranking` calcula independientemente el puesto
como 1 más la cantidad de áreas con más abordajes y verifica denominador y
porcentaje. `schema.yml` añade unicidad, no nulos, relación con `dim_zona` y el
conjunto esperado de cinco nombres. Las expectativas del dataset se hardcodean
solo en pruebas, no en el mart.

## v_tableau_metroriel

**Destino de conexión de Tableau para este caso:** `gold.v_tableau_metroriel`.
Es una vista dbt sobre `mart_metroriel_zonas` con el mismo grano. Proyecta
explícitamente las métricas anteriores, salvo la clave técnica `zona_sk`;
no expone identificadores de usuario ni una columna que mezcle abordajes y viajes.

Permite construir:

- barras de `abordajes_otros_modos` por `nombre_zona`, con el desglose TM/TU/AM;
- el puesto global `ranking_demanda_otros_modos`, contextualizado con
  `areas_en_ranking_red` y `pct_abordajes_otros_modos_red`;
- una comparación de `estaciones_metroriel` con `abordajes_otros_modos`;
- una visualización separada de `viajes_metroriel_iniciados` por zona de origen.

En Tableau, usar `MIN`, `MAX` o atributo para el total repetido de red, el
número de áreas y el ranking; no sumar esos campos. El porcentaje conserva el
denominador de toda la red aunque la vista exponga solo las zonas del trazado.

**Pruebas:** `v_tableau_metroriel_reconciliacion` compara todas las columnas con
el mart, fila a fila y en ambos sentidos; se añaden unicidad y no nulos en
`schema.yml`.

**Build limitado a los modelos nuevos y sus pruebas**, con hechos y dimensiones
Gold ya materializados:

```powershell
python scripts/run_dbt.py build --select mart_metroriel_zonas v_tableau_metroriel --threads 1
```

Después, con los modelos Gold existentes materializados, ejecutar las pruebas
Gold relevantes:

```powershell
python scripts/run_dbt.py test --select path:models/gold --threads 1
```

### Resultados medidos del caso MetroRiel — 10 de octubre de 2026

Consulta de `gold.v_tableau_metroriel`, ordenada por ranking global. El
denominador es **1,393,448 abordajes TM/TU/AM** y el universo es de **16 áreas**.

| Zona | Estaciones MR | Abordajes otros modos | Transmetro | Transurbano | Aerómetro | Viajes MR iniciados | % abordajes red | Puesto global |
|---|---:|---:|---:|---:|---:|---:|---:|---:|
| Zona 17 | 4 | 97,608 | 27,870 | 55,426 | 14,312 | 53,755 | 7.00 | 3 |
| Zona 12 | 4 | 96,792 | 24,277 | 57,916 | 14,599 | 53,970 | 6.95 | 5 |
| Zona 1 | 4 | 85,862 | 20,835 | 50,517 | 14,510 | 53,803 | 6.16 | 9 |
| Zona 8 | 5 | 82,922 | 27,891 | 55,031 | 0 | 66,924 | 5.95 | 11 |
| Zona 6 | 5 | 74,487 | 21,181 | 53,306 | 0 | 67,059 | 5.35 | 15 |

Las cinco zonas suman 22 estaciones, 437,671 abordajes de otros modos (31.41 %
de los abordajes de la red, calculado antes de redondear) y, por separado,
295,511 viajes MetroRiel iniciados. Estos valores describen la actividad del
dataset; no constituyen una recomendación sobre el trazado.

**Incidencias del entorno local:** Docker estaba apagado y las tablas del volumen
PostgreSQL estaban desactualizadas frente a `main`: `dim_zona` tenía 16 filas
pero no las columnas `puntos_*`, y los hechos no proyectaban aún
`bronze_record_id`. Para completar la regresión se rematerializaron
`silver_universo_zonas`, `dim_zona`, los dos hechos y los marts/vistas anteriores
desde sus SQL actuales, sin modificar sus archivos ni reglas. No fue necesario
cambiar los modelos de Hector.

**Resultados de validación:**

| Ejecución | Resultado | Duración reportada por dbt |
|---|---|---:|
| Build limitado a `mart_metroriel_zonas` y `v_tableau_metroriel` | Dos modelos y 27 pruebas correctos; `PASS=30`, `WARN=0`, `ERROR=0`, contando el hook | 10.33 s |
| Pruebas Gold después de actualizar las materializaciones locales | 89 pruebas correctas; `PASS=90`, `WARN=0`, `ERROR=0`, contando el hook | 16.64 s |

Antes de actualizar la base, el build del mart de cobertura existente falló
por `puntos_transmetro` ausente y la primera regresión Gold tuvo cuatro errores
por `bronze_record_id` ausente en los hechos. Tras reconstruir desde los modelos
versionados, esas pruebas pasaron. Los hechos conservaron 1,393,448 abordajes y
295,511 viajes; los resultados del nuevo mart reconcilian con ellos.


## mart_multimodalidad y v_tableau_transbordos

Grano del mart: un par consecutivo de eventos de una identidad inferida, en modos distintos, separado por >0 y <=90 minutos. Orden estable: fecha_hora, modo, bronze_record_id. MR aporta el ingreso de su viaje completo. El generador no entrega una cadena puerta-a-puerta confirmada; son **transbordos inferidos**, y proximidad temporal no demuestra transferencia fisica.

Fuentes: ambos hechos Gold y dimensiones tiempo, zona y modo. Se conserva usuario_sk y bronze_record_id_origen/destino para llegar a los dos registros Bronze/Raw. transbordo_sk = MD5(usuario_sk + ':' + ID origen + ':' + ID destino), con clave HMAC de usuario estable.

La vista agrega fecha x hora x modo origen/destino x combinacion x zona origen/destino x incluye_aerometro. total_transbordos cuenta pares, no usuarios; tiempo promedio no es aditivo. tarifa_total_gtq suma tarifas de pares y puede contar un evento en dos pares: no equivale a recaudo. Pruebas: claves presentes/unicas, modos distintos, diferencia >0 y <=90, secuencia completa contra hechos y reconciliacion de todos los campos/grupos de la vista.

Aerometro tiene identidad AM-<hash>, aislada de USR- de TM/TU/MR. Su multimodalidad persona-a-persona con otros sistemas no es medible; incluye_aerometro=false no prueba ausencia de transferencias reales. No se inventa enlace de identidad.

## v_tableau_multimodalidad (requisito 2.1)

Grano: modos_observados x metodo_identidad. Consume exclusivamente gold.dim_usuario y no expone usuario_sk. Usuario multimodal = modos_observados >1; se cuenta cada identidad una vez en todo el periodo observado. No requiere proximidad temporal ni un transbordo inferido.

- SUM(usuarios): distribucion por cantidad de modos, con desglose opcional del metodo.
- MAX(usuarios_multimodales_total): KPI global de usuarios multimodales.
- MAX(pct_usuarios_multimodales): porcentaje global, en escala 0-100.
- MAX(total_usuarios_observados) y MAX(usuarios_unimodales_total): universo y complemento.

Los totales globales se repiten por grupo: usar MIN/MAX, nunca SUM. Los filtros de modos/metodo no recalculan el denominador global. Para un porcentaje del subconjunto, usar SUM de usuarios de grupos multimodales / SUM(usuarios) del subconjunto y etiquetarlo como tal. No ofrece filtros temporales/zonales de personas, porque dim_usuario resume todo el periodo sin esos campos.

Incluye identidades Aerometro aisladas en el denominador, por lo que el porcentaje representa multimodalidad **observable con las llaves disponibles**, no prevalencia real persona-a-persona de toda la red. No sumar identidades para afirmar poblacion civil unica. Ver diccionario Gold (197 campos, 18 modelos) y reconciliacion completa contra dim_usuario.

El workbook existente se conserva sin cambios. La vista queda lista para incorporarla manualmente en Tableau; esta revision no demuestra que esa hoja ya este integrada.
