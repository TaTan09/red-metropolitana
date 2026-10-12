# Validacion numerica y tecnica de Fase 2

Fecha de consulta: 2026-10-12T11:30:24-06:00. PostgreSQL local; cifras del snapshot real.

## Fuentes y cutoff

Minimo global: **2026-06-01 04:00:00**. Maximo/cutoff: **2026-07-15 23:44:33**, Guatemala UTC-6. Incluye salida MR.

| Fuente Silver | Eventos validos | Minimo | Maximo de evento |
|---|---:|---|---|
| Transmetro | 362,106 | 2026-06-01 04:00:06 | 2026-07-15 22:59:50 |
| Transurbano | 827,788 | 2026-06-01 04:00:02 | 2026-07-15 22:59:55 |
| Aerometro | 203,554 | 2026-06-01 04:00:17 | 2026-07-15 22:59:56 |
| MetroRiel | 295,511 | 2026-06-01 04:00:00 | 2026-07-15 22:59:42 |

Salida MR maxima: 2026-07-15 23:44:33.

## Features y multimodalidad

Features: **70,380 filas**, **70,380 IDs unicos**; 0 nulos en cada una de las 25 columnas y 0 ultimos eventos posteriores al corte.

Gold: **36,827 multimodales**, **33,553 unimodales**, **70,380 total**, **52.33 %**. Unimodales + multimodales = total.

| Cantidad de modos | Usuarios (Silver y Gold) |
|---:|---:|
| 1 | 33,553 |
| 2 | 26,831 |
| 3 | 9,996 |

| Metodo Gold | Usuarios |
|---|---:|
| HASH_AISLADO | 14,496 |
| PATRON_NUMERICO_INFERIDO | 55,884 |

Ventanas Silver: 7 dias = 264,871; 30 dias = 1,132,630; 90 dias = 1,688,959. Total = 1,688,959 eventos registrados de granos distintos.

## Transbordos inferidos

Total: **41,565**; tiempo minimo **0.02 min**, maximo **90.00 min**, promedio **42.343430 min** (sobre diferencias redondeadas del mart).

| Combinacion | Pares inferidos |
|---|---:|
| Transurbano -> Transmetro | 9,585 |
| Transmetro -> Transurbano | 9,581 |
| MetroRiel -> Transurbano | 7,933 |
| Transurbano -> MetroRiel | 7,651 |
| Transmetro -> MetroRiel | 3,447 |
| MetroRiel -> Transmetro | 3,368 |

incluye_aerometro=true: **0**. AM-<hash> no enlaza con USR-: no es medible la multimodalidad persona-a-persona de Aerometro, ni se demuestra ausencia de transferencias fisicas. El generador no confirma cadenas puerta-a-puerta.

## Prueba de fuego del mes

Julio 2026, observado hasta el 15: 468,037 abordajes TM/TU/AM y 100,275 viajes MR = 568,312 eventos de movilidad registrados. Consulta SQL canonica ejecutada dos veces, resultados iguales. No son viajes puerta-a-puerta comparables ni estimaciones del mes completo.

## Validacion dbt

| Ejecucion | Pruebas PASS | Modelos/hook success | Errores | Skips | Segundos dbt |
|---|---:|---:|---:|---:|---:|
| build_inicial_cancelado | 87 | 17 | 1 | 28 | 445.73 |
| build_corregido | 67 | 5 | 0 | 0 | 53.85 |
| build_idempotencia | 67 | 7 | 0 | 0 | 63.50 |
| pruebas_silver_features | 28 | 1 | 0 | 0 | 21.80 |
| pruebas_silver_scd2 | 2 | 1 | 0 | 0 | 1.57 |
| pruebas_gold | 128 | 1 | 0 | 0 | 28.31 |

`success` incluye un hook, no una prueba. Gold final: 128 pruebas, PASS de consola=129 con hook. Silver: 28 de features/reconciliacion y 2 SCD2 =30. Build corregido: 4 modelos +67 pruebas +hook; repeticion: 6 modelos +67 pruebas +hook. Parse y docs generate finales: codigo 0. Catalogo completo: 18 modelos Gold, 197 columnas; descripciones coinciden con las columnas PostgreSQL.

El build inicial se cancelo tras 240.51 s en features: el plan subestimaba el resultado de row_number/rn=1 y elegia un nested loop costoso. DISTINCT ON mantiene el desempate y redujo esa materializacion a 13.95 s en el build corregido. Se conserva su error, no se presenta como corrida exitosa.

## Idempotencia, RBAC y Raw

Dos builds corregidos: conteos y fingerprints de contenido de negocio iguales en features, mart, ambas vistas, dim_usuario, bridge y cuarentena. Se excluyen exclusivamente fecha_proceso del bridge y fecha_deteccion de cuarentena. Fingerprint: MD5 de concatenacion ordenada de MD5 de cada fila JSONB; comprueba contenido de negocio y multiplicidad sin exponer IDs. No es prueba byte a byte de las tablas con auditoria, ni sustituye las dos corridas historicas Prefect.

tableau_ro: NOLOGIN, sin superuser/createdb/createrole; CONNECT y USAGE Gold; SELECT de todas las 18 relaciones actuales y de una futura tabla de prueba; Staging/Silver sin USAGE y lectura efectivamente denegada con SET ROLE. La tabla de prueba se revierte por rollback. El workbook sigue en red_user, sin cambios.

Auditoria fisica: un par real Transurbano -> MetroRiel verificado en Bronze y contra los registros Raw con SHA-256 y payload coincidente. El JSON contiene archivo/numero de registro sin tarjeta ni ID individual; no es auditoria exhaustiva.

Inventario regenerado con datos_red: 9 resultados reales, esquemas y conteos OK, bytes/tamanos y SHA-256 completos, sin ruta absoluta. Los nueve archivos son identicos por hash a data/raw. Las ocho evidencias historicas permanecen identicas al commit f64a23e.

## Reproduccion de evidencia adicional

```powershell
python scripts/verificar_fase2.py --snapshot antes
python scripts/run_dbt.py build --select bridge_identidad_usuario silver_cuarentena silver_features_usuario mart_multimodalidad v_tableau_transbordos v_tableau_multimodalidad --threads 1
python scripts/verificar_fase2.py --snapshot despues --registrar-dbt build_idempotencia
python scripts/verificar_fase2.py --report
```

Registros de estados dbt: ejecutar `--registrar-dbt ETIQUETA` inmediatamente despues del comando, antes de que otro dbt sobrescriba run_results.json. El estado intermedio queda ignorado en target/.
