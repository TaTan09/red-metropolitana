# Evidencia de idempotencia — Ingesta Batch a Bronze

**Fecha:** 2026-09-12

## Objetivo

Demostrar que ejecutar dos veces la ingesta Batch con los mismos archivos Raw no crea datos duplicados en Bronze.

## Resultados

| Fuente | Primera corrida | Segunda corrida | Registros | Resultado |
|---|---|---|---:|---|
| `tm_estaciones.csv` | INGESTED | SKIPPED | 104 | Sin duplicación |
| `tu_paradas.csv` | INGESTED | SKIPPED | 328 | Sin duplicación |
| `mr_estaciones.csv` | INGESTED | SKIPPED | 22 | Sin duplicación |
| `am_estaciones.csv` | INGESTED | SKIPPED | 14 | Sin duplicación |
| `transurbano_transacciones.csv` | INGESTED | SKIPPED | 832,791 | Sin duplicación |
| `metroriel_viajes.jsonl` | INGESTED | SKIPPED | 299,100 | Sin duplicación |

## Interpretación

En la primera corrida los seis archivos fueron escritos en Bronze.

En la segunda corrida, sin modificar los archivos Raw, los seis archivos fueron detectados mediante su SHA-256 como lotes ya ingeridos y el proceso devolvió `SKIPPED`.

Por lo tanto, la segunda ejecución no creó nuevas particiones ni nuevas filas para estos lotes.

## Mecanismo utilizado

La idempotencia Batch se controla mediante:

1. cálculo de SHA-256 del archivo Raw;
2. registro del hash y la salida Bronze en `data/bronze/_control/batch_manifest.json`;
3. comprobación del hash antes de volver a escribir;
4. reutilización del Parquet existente cuando el lote ya fue procesado.

> Esta evidencia corresponde a la ingesta Batch. La idempotencia del pipeline completo se volverá a demostrar cuando estén integradas las etapas de Streaming, CDC, Silver, Gold y orquestación.
