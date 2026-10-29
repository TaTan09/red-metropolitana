# Métricas CDC y padrón vigente de Transmetro

- **Fecha:** `2026-10-28T20:15:42-06:00`
- **Archivo:** `cdc_padron_usuarios.csv`
- **SHA-256:** `f1b483aba844ad1c5c1da71003c621bcbc8ce231ecf5283e42d18050261f480f`
- **Total CDC:** 77,636

## Operaciones

| Operación | Cantidad |
|---|---:|
| INSERT | 29,700 |
| UPDATE | 35,841 |
| DELETE | 12,095 |

## Llaves observadas

| Tipo | Cantidad |
|---|---:|
| METRORIEL | 3,398 |
| SIN_TARJETA | 5,510 |
| TRANSMETRO | 55,403 |
| TRANSURBANO | 13,325 |

## Padrón Transmetro derivado

- Tarjetas únicas finales: **40,612**
- Activas finales: **32,544**
- Inactivas finales: **8,068**
- DELETE sin atributos previos visibles: **4,189**

## Decisión de arquitectura

El CDC completo se conserva como `staging.cdc_registro_ambiguo`.
El padrón solicitado de Transmetro se deriva en `staging.padron_transmetro_actual` usando únicamente llaves `TC-########`.
Los DELETE no eliminan físicamente tarjetas; las dejan `INACTIVA`.

Las tablas de Staging se reconstruyen desde el Parquet Bronze en cada corrida, por lo que repetir el proceso produce el mismo estado final.
