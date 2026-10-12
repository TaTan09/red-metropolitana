# Inventario y validación de Raw

- **Fecha de validación:** `2026-10-12T11:16:00-06:00`
- **Estado general:** **OK**
- **Archivos esperados:** 9
- **Archivos encontrados:** 9

## Inventario

| Archivo | Registros | Esperados | Tamaño MB | Esquema | Conteo | SHA-256 |
|---|---:|---:|---:|---|---|---|
| `tm_estaciones.csv` | 104 | 104 | 0.01 | OK | OK | `4d53a95abb4f115b7da7f69db2c392e1748d6704807d81408a5e510f791624d0` |
| `tu_paradas.csv` | 328 | 328 | 0.01 | OK | OK | `a888a09c45189cfeac0a0577377d1b4c662923ee55f798d961f418aa2ac93b90` |
| `mr_estaciones.csv` | 22 | 22 | 0.00 | OK | OK | `c302ffbc6f0bdcf926c8eaaf9a5427ec5d38d482cc44431e3aeb20a8febb8e8c` |
| `am_estaciones.csv` | 14 | 14 | 0.00 | OK | OK | `e3acbeed8608fb9a6b9a8df87646bf5294e644aa64bd95484f1424b92ae21723` |
| `transmetro_validaciones.csv` | 363,221 | 363,221 | 22.93 | OK | OK | `5f88356e427d0ec19b193f6aaafedc288d9bf3fbad1881f011a7d9ea912730d2` |
| `transurbano_transacciones.csv` | 832,791 | 832,791 | 41.13 | OK | OK | `8ce5028499b7b6c7274fd838430e87d373065d377e5ec1f062a4fa6497083fad` |
| `metroriel_viajes.jsonl` | 299,100 | 299,100 | 52.75 | OK | OK | `23feb4a3a55ce506bf34de5faf7834f9c390b7ca70499cc9fb3ec1c3650ebede` |
| `aerometro_boardings.csv` | 203,554 | 203,554 | 11.56 | OK | OK | `898b871c6b3457b6b63a522d5dd8966e3a75bcaf215156a65c4a9d211af4cdc7` |
| `cdc_padron_usuarios.csv` | 31,050 | 31,050 | 2.05 | OK | OK | `68e4d9dd258809dd4a45a0c5f9023ad6f3b5d32912e4447b9d20b9a7258de5c4` |

## Archivos faltantes

Ninguno.

## Archivos extra

Ninguno.

## Interpretación

Este reporte valida la capa **Raw**. No aplica limpieza, normalización ni reglas de negocio.
Los hashes SHA-256 permiten comprobar que un archivo no cambió entre corridas.
