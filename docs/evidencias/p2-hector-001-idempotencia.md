# Idempotencia del flujo completo del proyecto

Proyecto 2: se validaron las nueve fuentes y se limpió el estado generado una sola vez,
antes de la corrida 1, mediante --fresh-start. Raw se conservó.

Se ejecutó dos veces el mismo flujo Prefect con los mismos archivos Raw,
sin borrar Bronze, el estado SQLite de deduplicación ni los volúmenes Docker entre corridas.
Idempotencia significa que reprocesar las mismas fuentes no cambia el estado analítico final.

- Corrida 1: 2,849.60 s; terminó 2026-10-29T10:05:08-06:00.
- Corrida 2: 1,269.73 s; terminó 2026-10-29T10:26:18-06:00.
- Comparación de SHA-256 Raw, filas Parquet, conteos SQL y fingerprints de negocio: **IGUALES**.
- Referencia Gold reconciliado con Silver (fuentes nuevas): **OK**.
- Cada corrida ejecutó `python scripts/run_dbt.py build` con sus pruebas.

## Conteos de ambas corridas

### Preparación fresh-start (antes de corrida 1)

Duración total: 44.87 s.

| Etapa | Segundos |
|---|---:|
| `validar_raw` | 12.44 |
| `validar_compose` | 0.73 |
| `reiniciar_docker` | 3.59 |
| `confirmar_reset_docker` | 0.88 |
| `limpiar_local` | 7.09 |
| `levantar_docker` | 2.65 |
| `esperar_servicios` | 11.38 |
| `crear_topics` | 0.13 |

## Requisito 1.1: conteos oficiales Proyecto 2 contra Bronze

Las diferencias se conservan para su explicación; no detienen las dos corridas.
El código de salida del flujo sigue evaluando idempotencia y la referencia Gold.

### Requisito 1.1 — Corrida 1

Referencia: LEEME oficial del Proyecto 2, requisito 1.1.

Estado: **OK**.

filas_cargadas suma las filas persistidas en los Parquet Bronze de cada fuente.
diferencia = filas_cargadas - filas_esperadas; no se usan conteos de Silver/Gold ni mensajes Kafka.

| archivo | filas_esperadas | filas_cargadas | diferencia |
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

Las nueve fuentes coinciden con la referencia oficial del Proyecto 2.


Conteos Raw adicionales (no sustituyen filas_cargadas):

| archivo | filas_raw |
|---|---:|
| aerometro_boardings.csv | 387053 |
| am_estaciones.csv | 14 |
| cdc_padron_usuarios.csv | 77636 |
| metroriel_viajes.jsonl | 590844 |
| mr_estaciones.csv | 22 |
| tm_estaciones.csv | 104 |
| transmetro_validaciones.csv | 713786 |
| transurbano_transacciones.csv | 1635788 |
| tu_paradas.csv | 328 |

### Requisito 1.1 — Corrida 2

Referencia: LEEME oficial del Proyecto 2, requisito 1.1.

Estado: **OK**.

filas_cargadas suma las filas persistidas en los Parquet Bronze de cada fuente.
diferencia = filas_cargadas - filas_esperadas; no se usan conteos de Silver/Gold ni mensajes Kafka.

| archivo | filas_esperadas | filas_cargadas | diferencia |
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

Las nueve fuentes coinciden con la referencia oficial del Proyecto 2.


Conteos Raw adicionales (no sustituyen filas_cargadas):

| archivo | filas_raw |
|---|---:|
| aerometro_boardings.csv | 387053 |
| am_estaciones.csv | 14 |
| cdc_padron_usuarios.csv | 77636 |
| metroriel_viajes.jsonl | 590844 |
| mr_estaciones.csv | 22 |
| tm_estaciones.csv | 104 |
| transmetro_validaciones.csv | 713786 |
| transurbano_transacciones.csv | 1635788 |
| tu_paradas.csv | 328 |

### Bronze (filas por fuente)

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `aerometro_boardings` | 387,053 | 387,053 | IGUALES |
| `am_estaciones` | 14 | 14 | IGUALES |
| `cdc_padron_usuarios` | 77,636 | 77,636 | IGUALES |
| `metroriel_viajes` | 590,844 | 590,844 | IGUALES |
| `mr_estaciones` | 22 | 22 | IGUALES |
| `tm_estaciones` | 104 | 104 | IGUALES |
| `transmetro_validaciones` | 713,786 | 713,786 | IGUALES |
| `transurbano_transacciones` | 1,635,788 | 1,635,788 | IGUALES |
| `tu_paradas` | 328 | 328 | IGUALES |

### Staging PostgreSQL

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `aerometro_boardings` | 387,053 | 387,053 | IGUALES |
| `am_estaciones` | 14 | 14 | IGUALES |
| `cdc_registro_ambiguo` | 77,636 | 77,636 | IGUALES |
| `metroriel_viajes` | 590,844 | 590,844 | IGUALES |
| `mr_estaciones` | 22 | 22 | IGUALES |
| `padron_transmetro_actual` | 40,612 | 40,612 | IGUALES |
| `tm_estaciones` | 104 | 104 | IGUALES |
| `transmetro_validaciones` | 713,786 | 713,786 | IGUALES |
| `transurbano_transacciones` | 1,635,788 | 1,635,788 | IGUALES |
| `tu_paradas` | 328 | 328 | IGUALES |
| `usuarios_aerometro_min` | 16,930 | 16,930 | IGUALES |
| `usuarios_metroriel_min` | 26,414 | 26,414 | IGUALES |
| `usuarios_transurbano_min` | 45,685 | 45,685 | IGUALES |

### Silver dbt

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `bridge_identidad_usuario` | 130,322 | 130,322 | IGUALES |
| `silver_aerometro_boardings` | 387,053 | 387,053 | IGUALES |
| `silver_catalogo_puntos` | 468 | 468 | IGUALES |
| `silver_cuarentena` | 18,922 | 18,922 | IGUALES |
| `silver_features_usuario` | 87,102 | 87,102 | IGUALES |
| `silver_metroriel_viajes` | 583,745 | 583,745 | IGUALES |
| `silver_padron_transmetro_scd2` | 55,403 | 55,403 | IGUALES |
| `silver_transmetro_validaciones` | 711,684 | 711,684 | IGUALES |
| `silver_transurbano_transacciones` | 1,626,075 | 1,626,075 | IGUALES |
| `silver_universo_zonas` | 16 | 16 | IGUALES |

### Gold dbt (granos diferentes)

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `dim_modo` | 4 | 4 | IGUALES |
| `dim_punto_transporte` | 468 | 468 | IGUALES |
| `dim_servicio` | 52 | 52 | IGUALES |
| `dim_tiempo` | 2,320,223 | 2,320,223 | IGUALES |
| `dim_usuario` | 87,102 | 87,102 | IGUALES |
| `dim_zona` | 16 | 16 | IGUALES |
| `fact_abordajes` | 2,724,812 | 2,724,812 | IGUALES |
| `fact_viajes_metroriel` | 583,745 | 583,745 | IGUALES |
| `mart_cobertura` | 16 | 16 | IGUALES |
| `mart_demanda_hora` | 74,440 | 74,440 | IGUALES |
| `mart_metroriel_zonas` | 5 | 5 | IGUALES |
| `mart_multimodalidad` | 74,174 | 74,174 | IGUALES |

### Vistas Tableau

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `v_tableau_cobertura` | 16 | 16 | IGUALES |
| `v_tableau_demanda_abordajes` | 65,915 | 65,915 | IGUALES |
| `v_tableau_demanda_viajes_mr` | 8,525 | 8,525 | IGUALES |
| `v_tableau_metroriel` | 5 | 5 | IGUALES |
| `v_tableau_multimodalidad` | 4 | 4 | IGUALES |
| `v_tableau_transbordos` | 66,045 | 66,045 | IGUALES |

### Gold abordajes por modo

| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |
|---|---:|---:|---|
| `Aerometro` | 387,053 | 387,053 | IGUALES |
| `Transmetro` | 711,684 | 711,684 | IGUALES |
| `Transurbano` | 1,626,075 | 1,626,075 | IGUALES |

## Resumen dbt capturado automáticamente

Los estados proceden del run_results.json del build de cada corrida; no de cifras fijas.

| Corrida | Pruebas PASS | Modelos success | Hooks success | Warnings | Errores | Skips |
|---|---:|---:|---:|---:|---:|---:|
| 1 | 183 | 34 | 1 | 0 | 0 | 0 |
| 2 | 183 | 34 | 1 | 0 | 0 | 0 |

## Fingerprints de contenido de negocio

MD5 de concatenación ordenada de MD5 de filas JSONB: conserva multiplicidad y no depende del orden físico.
Se comparan por separado todas las relaciones Silver, Gold y las seis vistas, sin equiparar sus granos.
Únicamente se excluyen bridge_identidad_usuario.fecha_proceso y silver_cuarentena.fecha_deteccion,
campos de auditoría no deterministas. No se afirma idempotencia byte a byte de esas tablas.

| Relación | Fingerprint corrida 1 | Fingerprint corrida 2 | Comparación |
|---|---|---|---|
| `gold.dim_modo` | 1dfaa5143881cf0f1d380b2f09ec32c4 | 1dfaa5143881cf0f1d380b2f09ec32c4 | IGUALES |
| `gold.dim_punto_transporte` | 1225471f8f31839c7ffc88aa8c0c732d | 1225471f8f31839c7ffc88aa8c0c732d | IGUALES |
| `gold.dim_servicio` | 9fe56925c2c725091bd55cf740798753 | 9fe56925c2c725091bd55cf740798753 | IGUALES |
| `gold.dim_tiempo` | 5cbef65329c4e3af92e14c70b6534bfe | 5cbef65329c4e3af92e14c70b6534bfe | IGUALES |
| `gold.dim_usuario` | 430de3f2d20ce04951e499851a7bdcad | 430de3f2d20ce04951e499851a7bdcad | IGUALES |
| `gold.dim_zona` | bcfc5d21e8a5e6ee01b8a272398e5d70 | bcfc5d21e8a5e6ee01b8a272398e5d70 | IGUALES |
| `gold.fact_abordajes` | 5ed1f38eca15accb2725d0bed1746db7 | 5ed1f38eca15accb2725d0bed1746db7 | IGUALES |
| `gold.fact_viajes_metroriel` | 432846bf887645e124a250357049efdd | 432846bf887645e124a250357049efdd | IGUALES |
| `gold.mart_cobertura` | 3794beccdac473f3a1119631d3598a2c | 3794beccdac473f3a1119631d3598a2c | IGUALES |
| `gold.mart_demanda_hora` | b70e428192f25118f3531debc38db897 | b70e428192f25118f3531debc38db897 | IGUALES |
| `gold.mart_metroriel_zonas` | cb6af08fb039ffaf1f4188a595f8531b | cb6af08fb039ffaf1f4188a595f8531b | IGUALES |
| `gold.mart_multimodalidad` | ab3e1712968f2874eb1dcc660da3be55 | ab3e1712968f2874eb1dcc660da3be55 | IGUALES |
| `gold.v_tableau_cobertura` | 4215257ec107c446b16714fb0e9bf159 | 4215257ec107c446b16714fb0e9bf159 | IGUALES |
| `gold.v_tableau_demanda_abordajes` | 0df745d052a3fc8f356a40d49bc38c4d | 0df745d052a3fc8f356a40d49bc38c4d | IGUALES |
| `gold.v_tableau_demanda_viajes_mr` | e3d78f5c0a2bee3067f4e835ded9cb54 | e3d78f5c0a2bee3067f4e835ded9cb54 | IGUALES |
| `gold.v_tableau_metroriel` | c2bab987e7b1df81c20a62ec16cb49e4 | c2bab987e7b1df81c20a62ec16cb49e4 | IGUALES |
| `gold.v_tableau_multimodalidad` | 543b3e9c986234d91e430bf65f72a5ec | 543b3e9c986234d91e430bf65f72a5ec | IGUALES |
| `gold.v_tableau_transbordos` | 9da85ca8f89e105a30369926117010b9 | 9da85ca8f89e105a30369926117010b9 | IGUALES |
| `silver.bridge_identidad_usuario` | 5859a1db5775a8608ae89aca1dcded81 | 5859a1db5775a8608ae89aca1dcded81 | IGUALES |
| `silver.silver_aerometro_boardings` | 8a6ad86d6102404deedbcaf5f6c22029 | 8a6ad86d6102404deedbcaf5f6c22029 | IGUALES |
| `silver.silver_catalogo_puntos` | 954481794bc5dee10341d1e0aaa1eaad | 954481794bc5dee10341d1e0aaa1eaad | IGUALES |
| `silver.silver_cuarentena` | e9dbf5667b3ae5aafe95ff12b5a44cb7 | e9dbf5667b3ae5aafe95ff12b5a44cb7 | IGUALES |
| `silver.silver_features_usuario` | 873f702eb1aa9735a759bcd5aefef952 | 873f702eb1aa9735a759bcd5aefef952 | IGUALES |
| `silver.silver_metroriel_viajes` | db2ea32f0bdb1b29755c7be599e3ccf2 | db2ea32f0bdb1b29755c7be599e3ccf2 | IGUALES |
| `silver.silver_padron_transmetro_scd2` | 0ab2a043f7ad8fd30046977eafeff34b | 0ab2a043f7ad8fd30046977eafeff34b | IGUALES |
| `silver.silver_transmetro_validaciones` | 55926274c120e633ef5c4df3353bc544 | 55926274c120e633ef5c4df3353bc544 | IGUALES |
| `silver.silver_transurbano_transacciones` | 026195c4478d4c3f9417d7c2ebba3103 | 026195c4478d4c3f9417d7c2ebba3103 | IGUALES |
| `silver.silver_universo_zonas` | c6c2348c47d3f6995f14a9d3862b17a2 | c6c2348c47d3f6995f14a9d3862b17a2 | IGUALES |
## Streaming y deduplicación

| Fuente | Corrida | Mensajes consumidos | Nuevos Bronze | Omitidos por `_event_id` |
|---|---:|---:|---:|---:|
| transmetro | 1 | 713,786 | 713,786 | 0 |
| aerometro | 1 | 387,053 | 387,053 | 0 |
| transmetro | 2 | 713,786 | 0 | 713,786 |
| aerometro | 2 | 387,053 | 0 | 387,053 |

## Duración de etapas

| Etapa | Corrida 1 (s) | Corrida 2 (s) |
|---|---:|---:|
| `validar_servicios` | 0.14 | 0.17 |
| `batch_to_bronze` | 19.39 | 2.50 |
| `cdc_to_bronze` | 22.41 | 21.81 |
| `streaming_transmetro` | 723.15 | 445.55 |
| `streaming_aerometro` | 385.23 | 114.73 |
| `rebuild_staging` | 614.59 | 219.03 |
| `dbt_build` | 720.43 | 315.90 |
| `collect_metrics` | 363.33 | 149.87 |

## Hallazgo y corrección

Antes de la orquestación, los productores podían informar entregas Kafka fallidas
en el callback y aun así terminar con código cero. Ahora contabilizan esas fallas
y devuelven código distinto de cero para detener Prefect.

Los consumidores esperan la asignación de partición antes de medir inactividad.
Los productores aplican espera acotada ante presión de la cola Kafka.
La cantidad consumida puede superar las filas Raw si existen publicaciones
anteriores; la deduplicación por `_event_id` impide agregar copias a Bronze.

La definición Docker asigna 1 GB de /dev/shm a PostgreSQL para las consultas paralelas.
fresh-start recreó los contenedores y el volumen antes de la primera corrida.

Los archivos `p2-hector-001-corrida-1.json` y `p2-hector-001-corrida-2.json` contienen los SHA-256
Raw, filas Parquet, conteos, fingerprints, duraciones y resumen dbt de cada corrida.
