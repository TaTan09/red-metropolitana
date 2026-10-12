# ADR 002 — Decisiones de Fase 2: marts, vistas para Tableau y cobertura

Estado: Aceptado, salvo la decisión 5 (pendiente)
Fecha: 2026-10-10

## Contexto

Fase 1 dejó Gold con seis dimensiones y dos hechos. Fase 2 agrega las tablas que
consume el tablero: `mart_demanda_hora` y `mart_cobertura`. Al construirlas apareció
un riesgo de interpretación: `fact_abordajes` (TM, TU, AM) y `fact_viajes_metroriel`
miden cosas distintas, y sumarlas en una sola columna da un número que no es
personas ni viajes.

## Decisiones

### 1. Vistas separadas para Tableau en vez de conectar a los marts

Se crean `v_tableau_demanda_abordajes`, `v_tableau_demanda_viajes_mr` y
`v_tableau_cobertura`. Tableau se conecta a ellas, no a los `mart_*`.

Alternativas consideradas:
- Una sola vista de demanda con columna `tipo_evento`. Más simple, pero la
  protección depende de que quien arme el dashboard filtre bien.
- Tableau directo sobre los marts. Sin trabajo en dbt, pero la protección vive en
  un libro de Tableau que no se versiona ni se prueba.

Razón: con vistas separadas, mezclar unidades queda imposible por diseño. La vista
de cobertura no expone `eventos_totales`, `eventos_por_punto` ni `pct_demanda_red`,
y tiene dos rankings separados (`ranking_abordajes` y `ranking_viajes_mr_origen`).
La prueba `v_tableau_reconciliacion` verifica que las vistas sumen exactamente las
filas de los hechos (1,393,448 abordajes y 295,511 viajes).

### 2. Puntos por modo en `dim_zona`

`silver_universo_zonas` calcula `puntos_transmetro`, `puntos_transurbano`,
`puntos_metroriel` y `puntos_aerometro`; `dim_zona` los expone y `mart_cobertura`
los usa para ratios por modo.

Alternativa considerada: contarlos dentro de `mart_cobertura` desde
`dim_punto_transporte`. No toca dimensiones, pero reparte la oferta entre dos
lugares.

Razón: la oferta (`tiene_servicio`, `modos_con_servicio`, puntos) queda en un solo
origen. `eventos_por_punto` dividía eventos de cuatro modos entre puntos de cuatro
modos; con el desglose se comparan abordajes por punto del mismo modo, y viajes
por estación en MetroRiel. La prueba `mart_cobertura_puntos_por_modo` verifica que
los puntos por modo sumen el total de cada zona y que cuadren con
`dim_punto_transporte` (104, 328, 22 y 14; 468 en total).

Consecuencia: `dim_zona` ganó cuatro columnas y sigue con 16 filas. Se actualizaron
`schema.yml` y el DDL.

### 3. `dim_zona` se construye desde `silver_universo_zonas`

El universo de 16 áreas (12 zonas y 4 municipios) viene del generador entregado.
Permite mostrar áreas sin servicio (hoy Santa Catarina Pinula). La causa del conteo
anterior de 13 y su corrección están en `docs/evidencias/004-correccion-zonas.md`.

### 4. MetroRiel cuenta una vez por viaje, en el ingreso y en la zona de origen

En `mart_demanda_hora` y en las vistas, cada viaje MetroRiel se asigna a la zona de
origen. La zona destino no se cuenta. La columna se llama `zona_origen` en la vista
de viajes para que no se lea como demanda en la zona.

Consecuencia: el ranking de MetroRiel mide dónde empiezan los viajes, no una
demanda comparable con la de los otros modos. Los viajes y los abordajes no se
comparan entre sí.

Según los catálogos, las 22 estaciones MetroRiel están en las zonas 17, 12, 8, 6 y 1
(verificado en `v_tableau_cobertura`: solo esas cinco zonas tienen estaciones o viajes
iniciados). Por eso encabezan `ranking_viajes_mr_origen`.

### 5. Rol de solo lectura `tableau_ro`

El workbook local usa `red_user`, que también puede leer Staging y Silver,
donde están las tarjetas originales. Eso contradice el principio de que el tablero
solo ve Gold. La revisión de Fase 2 provisiona `tableau_ro` con acceso solo al esquema `gold`,
usando `ALTER DEFAULT PRIVILEGES` para que conserve el acceso cuando dbt recree las
tablas y vistas, con la contraseña fuera del repositorio.

Se creó sin LOGIN para no inventar ni guardar contraseñas. La habilitación mediante
`TABLEAU_RO_PASSWORD` y el cambio manual de conexión en Tableau siguen pendientes.
Ver `docs/seguridad/seguridad_y_datos_personales.md` y la evidencia de permisos.

## Evidencia

- `docs/metricas/rendimiento_fase2.md`: la misma pregunta de demanda tarda unos
  3,456 ms desde los hechos y unos 45 ms desde el mart (34.5 ms desde la vista).
  El mart pesa 3.2 MB contra 506 MB del hecho.
- `docs/evidencias/004-correccion-zonas.md`: 13 → 16 zonas.

## Limitaciones

- `cantidad_eventos` en `mart_demanda_hora` mezcla abordajes y viajes. La protección
  existe en las vistas, no en los marts: quien consulte los marts directamente debe
  filtrar por `tipo_evento`.
- El universo de 16 áreas viene del generador, no de una fuente geográfica oficial.
- `tiene_servicio` sale de los catálogos de los operadores. Muestra dónde no hay
  servicio, pero no mide demanda potencial ni dónde hace falta servicio.
- `es_hora_pico` solo es verdadero en días hábiles, así que `Fuera de pico` incluye
  fines de semana.
- Los tiempos de consulta se midieron en un solo equipo y con los datos ya en la
  caché de PostgreSQL.
