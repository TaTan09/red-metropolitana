# Evidencia de idempotencia — Streaming Transmetro

**Fecha:** 2026-09-12

## Objetivo

Demostrar que una repetición técnica de los mismos eventos Kafka no genera filas duplicadas en Bronze.

## Prueba 1 — Primera publicación/consumo

Se publicaron 10 eventos del archivo `transmetro_validaciones.csv`.

Resultado del consumidor:

| Métrica | Valor |
|---|---:|
| Mensajes consumidos | 10 |
| Eventos nuevos en Bronze | 10 |
| Repeticiones técnicas omitidas | 0 |
| Mensajes inválidos | 0 |
| Parquet creados | 1 |

Archivo Bronze generado:

```text
part-p0-000000000000-000000000009.parquet
```

## Prueba 2 — Repetición de los mismos 10 eventos

Se volvió a ejecutar el productor con las mismas primeras 10 filas.

Como `_event_id` se genera de forma determinística usando el SHA-256 del archivo y el número de fila, los 10 eventos recibieron los mismos identificadores técnicos.

Resultado del consumidor:

| Métrica | Valor |
|---|---:|
| Mensajes consumidos | 10 |
| Eventos nuevos en Bronze | 0 |
| Repeticiones técnicas omitidas | 10 |
| Mensajes inválidos | 0 |
| Parquet creados | 0 |

## Conclusión

La repetición técnica de los mismos eventos no duplica Bronze.

El mecanismo de idempotencia funciona de la siguiente manera:

```text
SHA-256 del archivo + número de fila
              ↓
        _event_id estable
              ↓
   consumidor consulta estado
       ├── ya existe → omite
       └── no existe → persiste en Bronze
```

## Distinción importante

Esta deduplicación se aplica únicamente a repeticiones técnicas del pipeline.

Los duplicados reales del torniquete presentes en el archivo fuente tienen números de fila distintos, por lo que conservan `_event_id` distintos y llegan a Bronze. Su tratamiento corresponde a las reglas de calidad de Silver.
