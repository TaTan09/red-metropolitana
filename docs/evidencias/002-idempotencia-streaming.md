# Evidencia de idempotencia — Streaming (Transmetro y Aerómetro)

## Contexto

El pipeline de streaming Transmetro y Aerómetro debe ser idempotente, es decir, correr el
mismo producer y el mismo consumer más de una vez sobre el mismo archivo fuente
no debe generar eventos duplicados en Bronze.

La idempotencia se logra en dos capas:

- **Producer:** genera un `_event_id` determinístico como
  `SHA-256(sha256_del_archivo + numero_de_fila)`. Si el archivo fuente no
  cambia, el mismo registro siempre produce el mismo `_event_id`.
- **Consumer:** mantiene un registro persistente de `_event_id` ya procesados
  en `data/bronze/_control/streaming_state.sqlite`. Si un evento ya fue
  escrito a Bronze anteriormente, se cuenta como "duplicado técnico" y no se
  vuelve a escribir en Parquet.

Para comprobarlo, se ejecutó el mismo lote de 100 registros dos veces
seguidas para cada operador, usando `--limit 100` en el producer y
`--max-messages 100` en el consumer.

Entorno: Docker Compose local (`red_metropolitana_kafka`, imagen
`apache/kafka:4.3.1`, modo KRaft de un solo nodo).

## Prueba: Transmetro

Archivo fuente: `data/raw/transmetro_validaciones.csv`
SHA-256: `5f88356e427d0ec19b193f6aaafedc288d9bf3fbad1881f011a7d9ea912730d2`
Topic: `transmetro-validaciones`

### Corrida 1 (carga inicial)

```
python ingestion/streaming/producer_transmetro.py --limit 100
```
```
Eventos procesados: 100
Resultado          : OK
```

```
python ingestion/streaming/consumer_transmetro.py --max-messages 100
```
```
Mensajes consumidos          : 100
Eventos nuevos en Bronze     : 100
Repeticiones técnicas omitidas: 0
Mensajes inválidos           : 0
Parquet creados              : 1
Resultado                    : OK
```

Archivo generado: `data/bronze/transmetro_validaciones/fecha_ingesta=2026-09-13/part-p0-000000000000-000000000099.parquet`

### Corrida 2 (misma carga, repetida)

```
python ingestion/streaming/producer_transmetro.py --limit 100
```
```
Eventos procesados: 100
Resultado          : OK
```

```
python ingestion/streaming/consumer_transmetro.py --max-messages 100
```
```
Mensajes consumidos          : 100
Eventos nuevos en Bronze     : 0
Repeticiones técnicas omitidas: 100
Mensajes inválidos           : 0
Parquet creados              : 0
Resultado                    : OK
```

### Resultado

| Métrica | Corrida 1 | Corrida 2 |
|---|---|---|
| Mensajes consumidos | 100 | 100 |
| Eventos nuevos en Bronze | 100 | 0 |
| Duplicados técnicos | 0 | 100 |
| Parquet creados | 1 | 0 |

Después de las dos corridas, `data/bronze/transmetro_validaciones/` contiene
un único archivo Parquet con 100 filas, no dos.

## Prueba: Aerómetro

Archivo fuente: `data/raw/aerometro_boardings.csv`
SHA-256: `898b871c6b3457b6b63a522d5dd8966e3a75bcaf215156a65c4a9d211af4cdc7`
Topic: `aerometro-boardings`

### Corrida 1 (carga inicial)

```
python ingestion/streaming/producer_aerometro.py --limit 100
```
```
Eventos procesados: 100
Resultado          : OK
```

```
python ingestion/streaming/consumer_aerometro.py --max-messages 100
```
```
Mensajes consumidos          : 100
Eventos nuevos en Bronze     : 100
Repeticiones técnicas omitidas: 0
Mensajes inválidos           : 0
Parquet creados              : 1
Resultado                    : OK
```

Archivo generado: `data/bronze/aerometro_boardings/fecha_ingesta=2026-09-13/part-p0-000000000000-000000000099.parquet`

### Corrida 2 (misma carga, repetida)

```
python ingestion/streaming/producer_aerometro.py --limit 100
```
```
Eventos procesados: 100
Resultado          : OK
```

```
python ingestion/streaming/consumer_aerometro.py --max-messages 100
```
```
Mensajes consumidos          : 100
Eventos nuevos en Bronze     : 0
Repeticiones técnicas omitidas: 100
Mensajes inválidos           : 0
Parquet creados              : 0
Resultado                    : OK
```

### Resultado

| Métrica | Corrida 1 | Corrida 2 |
|---|---|---|
| Mensajes consumidos | 100 | 100 |
| Eventos nuevos en Bronze | 100 | 0 |
| Duplicados técnicos | 0 | 100 |
| Parquet creados | 1 | 0 |

Igual que Transmetro, después de dos corridas, `data/bronze/aerometro_boardings/`
contiene un único archivo Parquet con 100 filas.

## Conclusión

Ambos flujos de streaming Transmetro y Aerómetro cumplen la regla de
idempotencia definida en la arquitectura del proyecto: repetir la ingesta con
los mismos datos de origen no genera registros duplicados en Bronze. La
deduplicación ocurre a nivel técnico con `_event_id`, sin tocar ni eliminar los
duplicados de negocio reales que puedan existir en el archivo fuente, por
ejemplo, los duplicados de torniquete de Transmetro, los cuales se conservan
intencionalmente en Bronze para ser tratados como regla de calidad en Silver.

## Nota técnica: warning "Coordinator load in progress"

Durante la primera publicación al topic `transmetro-validaciones` (la
primera vez que ese topic se creó en el broker), el producer mostró:

```
%4|...|GETPID|red-metropolitana-transmetro-producer#producer-1| [thrd:main]:
Failed to acquire idempotence PID from broker localhost:9092/1:
Broker: Coordinator load in progress: retrying
```

Esto es un **warning Leve de librdkafka**, no un error del pipeline. Ocurre
porque el broker aún estaba inicializando el coordinador de transacciones
para ese topic recién creado. El propio mensaje indica que el cliente
reintentó automáticamente, y la corrida terminó con `Resultado: OK` y los 100
eventos procesados correctamente. No requirió ninguna acción ni cambio de
código. No volvió a aparecer en corridas posteriores sobre el mismo topic.