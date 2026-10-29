# Proyecto 2 — Requisito 1.1 — Corrida 1

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
