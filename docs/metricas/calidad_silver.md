# Reporte de Calidad de Datos y Cuarentena - Capa Silver

## 1. Resumen de Cuarentena por Regla
| Fuente | Motivo de Rechazo | Registros Aislados | % dentro de Fuente | Criterio Técnico |
| :--- | :--- | :---: | :---: | :--- |
| **MetroRiel** | `VIAJE_SIN_EXIT` | 3,589 | 100.00% | Viajes abiertos sin marcaje de torniquete de salida. |
| **Transmetro** | `DUPLICADO_TORNIQUETE` | 1,115 | 100.00% | Doble marcaje en misma tarjeta, estación y timestamp. |
| **Transurbano** | `COD_PARADA_NULO` | 4,189 | 83.68% | Transacciones sin identificador de parada en catálogo. |
| **Transurbano** | `FECHA_FUTURA` | 817 | 16.32% | Registros con estampas temporales posteriores a 2026-10-01. |
| **Total Aislado** | — | **9,710** | — | Registros no propagados a la capa Silver analítica. |

## 2. Historización SCD Tipo 2 (Padrón Transmetro)
- **Tabla:** `silver.snap_padron_transmetro`
- **Registros procesados:** 17,432 tarjetas únicas.
- **Estrategia:** `check` (`estado_tarjeta`, `perfil_usuario`, `zona_residencia`).