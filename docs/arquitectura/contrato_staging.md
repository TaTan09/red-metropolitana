# Contrato de Staging — Proyecto 1 Red Metropolitana

## Objetivo

Este documento fija la interfaz compartida entre la ingesta (Bronze/Staging), los modelos Silver en dbt y el modelado Gold. Su propósito es permitir que los integrantes trabajen en paralelo sin cambiar nombres o significados de tablas de forma independiente.

## Reglas de la capa Staging

- Staging es reconstruible: puede vaciarse y cargarse de nuevo desde Bronze.
- Bronze se acumula; Staging no es el histórico definitivo.
- Staging NO aplica reglas de calidad de negocio que descarten registros.
- Duplicados de torniquete, paradas nulas, fechas futuras y viajes sin salida permanecen en Staging; se resuelven en Silver y/o cuarentena.
- Staging conserva unidades y formatos de origen cuando sea posible.
- Se permite aplanar estructuras técnicas (por ejemplo, JSON de MetroRiel) sin cambiar el significado de los datos.
- Gold nunca debe leer Staging ni Bronze directamente; Gold consumirá Silver.
- Si una tabla o columna de este contrato cambia, el cambio debe coordinarse con todo el equipo.

---

## Tablas de catálogos

### `staging.tm_estaciones`

| Columna | Origen |
|---|---|
| estacion_id | `tm_estaciones.csv` |
| nombre | `tm_estaciones.csv` |
| linea | `tm_estaciones.csv` |
| zona | `tm_estaciones.csv` |
| lat | `tm_estaciones.csv` |
| lon | `tm_estaciones.csv` |

Conteo esperado actual: **104 filas**.

### `staging.tu_paradas`

| Columna | Origen |
|---|---|
| cod_parada | `tu_paradas.csv` |
| descripcion | `tu_paradas.csv` |
| ruta | `tu_paradas.csv` |
| sector | `tu_paradas.csv` |

Conteo esperado actual: **328 filas**.

### `staging.mr_estaciones`

| Columna | Origen |
|---|---|
| id_estacion | `mr_estaciones.csv` |
| nombre_estacion | `mr_estaciones.csv` |
| zona_nombre | `mr_estaciones.csv` |
| km | `mr_estaciones.csv` |

Conteo esperado actual: **22 filas**.

### `staging.am_estaciones`

| Columna | Origen |
|---|---|
| station_code | `am_estaciones.csv` |
| station_name | `am_estaciones.csv` |
| axis | `am_estaciones.csv` |
| district | `am_estaciones.csv` |

Conteo esperado actual: **14 filas**.

---

## Tablas operacionales

### `staging.transmetro_validaciones`

Preserva el significado del CSV de origen. No eliminar todavía los duplicados de torniquete.

| Columna |
|---|
| validacion_id |
| tarjeta |
| estacion_id |
| linea |
| fecha_hora |
| tarifa |
| tipo |

Conteo esperado actual: **363,221 filas**.

### `staging.transurbano_transacciones`

Mantener la fecha y hora separadas y el monto en centavos. La conversión a fecha-hora estándar y quetzales corresponde a Silver.

| Columna |
|---|
| fecha |
| hora |
| num_tarjeta |
| cod_parada |
| ruta |
| monto_centavos |
| cod_estado |

Conteo esperado actual: **832,791 filas**.

### `staging.metroriel_viajes`

El JSONL puede aplanarse técnicamente, sin inventar salida cuando no exista.

| Columna | Significado |
|---|---|
| trip_id | identificador del viaje |
| card | llave del usuario |
| entry_station | `entry.station` |
| entry_ts | `entry.ts` |
| exit_station | `exit.station`, NULL si no hubo salida |
| exit_ts | `exit.ts`, NULL si no hubo salida |
| fare_gtq | tarifa de origen |
| duration_s | duración, NULL si no hubo salida |

Conteo esperado actual: **299,100 filas**.

### `staging.aerometro_boardings`

El timestamp sigue en UTC en Staging. La conversión a hora local de Guatemala corresponde a Silver.

| Columna |
|---|
| boarding_id |
| user_hash |
| station_code |
| axis |
| timestamp_utc |
| cabin_number |
| fare |

Conteo esperado actual: **203,554 filas**.

---

## CDC y padrón

### `staging.cdc_registro_ambiguo`

Ya implementada. Conserva todos los cambios recibidos y clasifica el formato de la llave.

Conteo actual: **31,050 filas**.

Categorías actuales:
- TRANSMETRO: 22,326
- TRANSURBANO: 5,223
- METRORIEL: 1,295
- SIN_TARJETA: 2,206

### `staging.padron_transmetro_actual`

Ya implementada. Resultado de aplicar INSERT, UPDATE y DELETE en orden de secuencia para llaves Transmetro.

Conteo actual: **17,432 tarjetas únicas**.
- ACTIVAS: 15,096
- INACTIVAS: 2,336

Los DELETE se representan como inactivos; no se eliminan físicamente.

---

## Catálogos mínimos de usuarios sin padrón

Deben construirse desde las llaves distintas de los archivos de operación. No inventar atributos.

### `staging.usuarios_transurbano_min`

| Columna |
|---|
| num_tarjeta |

Fuente: `staging.transurbano_transacciones`.

### `staging.usuarios_metroriel_min`

| Columna |
|---|
| card |

Fuente: `staging.metroriel_viajes`.

### `staging.usuarios_aerometro_min`

| Columna |
|---|
| user_hash |

Fuente: `staging.aerometro_boardings`.

Los conteos de usuarios únicos se documentarán cuando estas tres tablas sean construidas.

---

## Contrato para Silver

Alejandro puede asumir que las tablas anteriores serán la entrada de dbt.

Silver será responsable de:
- normalizar fechas;
- convertir montos a quetzales;
- convertir Aerómetro UTC a hora local;
- conformar zonas;
- resolver/explicitar la estrategia de identidad;
- separar registros válidos y cuarentena;
- resolver duplicados de torniquete;
- tratar paradas nulas, fechas futuras y viajes sin salida;
- historizar el padrón mediante SCD Tipo 2.

Silver no debe inventar atributos de usuario que los operadores no entregaron.

---

## Contrato para Gold

Jonatán puede diseñar el modelo dimensional antes de que Silver esté finalizado, pero la implementación de Gold deberá leer exclusivamente modelos Silver.

Diseño previsto:
- `dim_usuario`
- `dim_tiempo`
- `dim_zona`
- `dim_punto_transporte`
- `dim_modo`
- `dim_servicio`
- `fact_abordajes`
- `fact_viajes_metroriel`

El diseño definitivo se validará contra los modelos Silver antes de materializar Gold.

---

## Política de cambios

1. Los nombres de tablas de este documento son el contrato compartido.
2. Si alguien necesita cambiar una tabla o columna, debe comunicarlo antes de hacer merge.
3. Cada capa debe poder reconstruirse desde la capa anterior.
4. Todos los cambios deben quedar registrados en Git.
