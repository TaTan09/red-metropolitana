# Métricas CDC y padrón vigente de Transmetro

- **Fecha:** `2026-09-22T11:25:53-06:00`
- **Archivo:** `cdc_padron_usuarios.csv`
- **SHA-256:** `68e4d9dd258809dd4a45a0c5f9023ad6f3b5d32912e4447b9d20b9a7258de5c4`
- **Total CDC:** 31,050

## Operaciones

| Operación | Cantidad |
|---|---:|
| INSERT | 10,800 |
| UPDATE | 16,200 |
| DELETE | 4,050 |

## Llaves observadas

| Tipo | Cantidad |
|---|---:|
| METRORIEL | 1,295 |
| SIN_TARJETA | 2,206 |
| TRANSMETRO | 22,326 |
| TRANSURBANO | 5,223 |

## Padrón Transmetro derivado

- Tarjetas únicas finales: **17,432**
- Activas finales: **15,096**
- Inactivas finales: **2,336**
- DELETE sin atributos previos visibles: **1,821**

## Decisión de arquitectura

El CDC completo se conserva como `staging.cdc_registro_ambiguo`.
El padrón solicitado de Transmetro se deriva en `staging.padron_transmetro_actual` usando únicamente llaves `TC-########`.
Los DELETE no eliminan físicamente tarjetas; las dejan `INACTIVA`.

Las tablas de Staging se reconstruyen desde la fuente en cada corrida, por lo que repetir el proceso produce el mismo estado final.
