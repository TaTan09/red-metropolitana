# Definiciones oficiales, dueños y reglas de calidad

## Granos oficiales

- **Abordaje:** validación/acceso individual válido de Transmetro, Transurbano o Aerómetro. Una fila de `gold.fact_abordajes` representa un abordaje; no confirma destino ni trayecto puerta-a-puerta.
- **Viaje MetroRiel:** trayecto completo registrado con origen y destino y salida presente. Una fila de `gold.fact_viajes_metroriel` representa un viaje completo. Para demanda mensual se fecha por ingreso y se cuenta una vez en origen; el destino y la salida siguen siendo parte del viaje.
- **Evento de movilidad registrado:** un registro válido de cualquiera de los dos hechos. Sumar abordajes y viajes MR es una convención de conteo de registros con distinto grano, nunca una equivalencia de viajes puerta-a-puerta comparables.
- **Usuario observado:** identidad analítica de `dim_usuario`, construida desde las llaves operacionales válidas del puente Silver; no persona comprobada ni tarjeta vigente del padrón.
- **Usuario multimodal:** identidad con `modos_observados > 1`. Se cuenta una vez en el período completo observado mediante `v_tableau_multimodalidad`; no depende de que tenga un par próximo temporalmente.
- **Usuario unimodal:** identidad con `modos_observados = 1`; unimodales + multimodales = total observado. Aerómetro aparece aislado por limitación de enlace, no por evidencia de exclusividad real.
- **Transbordo inferido:** dos eventos consecutivos del mismo usuario inferido, en modos distintos, separados por más de 0 y como máximo **90 minutos**. Orden determinista: `fecha_hora, modo, bronze_record_id`. MR aporta el ingreso de su viaje completo. El generador no entrega una cadena puerta-a-puerta confirmada y la proximidad temporal no demuestra transferencia física real. El mart conserva ambos identificadores Bronze.
- **Usuario activo en el período observado:** identidad con al menos un evento válido disponible en el período; el universo de `dim_usuario` lo satisface. No equivale al estado activo administrativo de `silver_padron_transmetro_scd2`. No se publica un MAU recurrente de dos días en 30 días: esa métrica no está implementada.

La identidad `AM-<hash>` de Aerómetro no enlaza con `USR-<número inferido>` de TM/TU/MR. Su multimodalidad persona-a-persona con otros sistemas **no es medible** con estas llaves. Un resultado cero en `incluye_aerometro` no significa cero transferencias físicas. Tampoco el patrón numérico demuestra identidad civil de TM/TU/MR.

## Prueba de fuego: registros del mes

La consulta canónica está en `sql/utilities/eventos_movilidad_mes.sql`. Determina el mes del máximo timestamp real Gold, incluyendo salida MR. En el snapshot verificado el período global es 2026-06-01 04:00:00 a 2026-07-15 23:44:33, hora local Guatemala, por lo que el mes seleccionado es **julio de 2026**. Es un mes parcialmente observado: los datos terminan el 15 de julio. No se extrapola al mes completo.

```powershell
Get-Content sql/utilities/eventos_movilidad_mes.sql | docker exec -i red_metropolitana_postgres psql -U red_user -d red_metropolitana
```

La consulta utiliza `fact_abordajes.tiempo_sk`, `fact_viajes_metroriel.tiempo_ingreso_sk` y `dim_tiempo.fecha_hora`, filtra `[inicio_mes, inicio_mes + 1 mes)` y devuelve por separado `abordajes_mes_tm_tu_am`, `viajes_metroriel_mes` y su suma `eventos_movilidad_mes`. Silver ya excluye los registros inválidos; no restar de nuevo la cuarentena, que permite múltiples motivos por registro. Dos integrantes con el mismo snapshot y esta consulta deben obtener los mismos valores. Para fijar otro mes existente sustituir el CTE `periodo` por un timestamp literal documentado.

```sql
-- Consulta de comprobación del universo; unidades separadas.
select
  (select count(*) from gold.fact_abordajes) as abordajes_tm_tu_am,
  (select count(*) from gold.fact_viajes_metroriel) as viajes_metroriel;
```

Los valores ejecutados dos veces y su igualdad están en `docs/metricas/validacion_fase2.json`. La suma de registros no representa viajes puerta-a-puerta.

## Dueño por dominio

Roles institucionales propuestos para la Agencia; no implican que exista una organización real creada por este proyecto. El dueño autoriza cambios semánticos y Gobierno de Datos registra versión, impacto, pruebas y aprobación antes del despliegue.

| Dominio | Dueño / rol que autoriza la definición |
|---|---|
| Usuario / identidad | Gestión de Identidad y Usuarios, con Seguridad para cambios de enlace |
| Tiempo / calendario | Gobierno de Datos, con Operaciones para huso y horas pico |
| Zona | Planificación Territorial |
| Punto de transporte | Operaciones del operador, con Planificación Territorial |
| Modo | Planeación de Red |
| Servicio | Operaciones del operador |
| Abordajes | Operaciones TM/TU/AM |
| Viajes MetroRiel | Operaciones MetroRiel |
| Multimodalidad / transbordos inferidos | Planeación de Red, con Gestión de Identidad para los límites del enlace |

## Reglas de calidad implementadas

Todas se detectan en **Silver**, leyendo Staging. `silver_cuarentena` conserva `id_registro_crudo = bronze_record_id`, fuente, motivo, payload y fecha de detección. No elimina Raw/Bronze; el ID permite continuar a Parquet y, por hash/número de registro, al archivo crudo. Un registro puede tener más de un motivo.

| Fuente / regla | Condición exacta del SQL | Acción |
|---|---|---|
| Transmetro / `DUPLICADO_TORNIQUETE` | `row_number > 1` para misma tarjeta, estación y fecha-hora; prioridad por ingesta_timestamp, bronze_record_id | Duplicados de negocio a cuarentena; `silver_transmetro_validaciones` conserva `rn = 1` |
| Transurbano / `COD_PARADA_NULO` | Código NULL o vacío después de trim | Cuarentena; excluido de operación Silver |
| Transurbano / `FECHA_FUTURA` | Formato distinto de DD/MM/YYYY o YYYY-MM-DD produce fecha NULL, o timestamp mayor a **2026-10-01 00:00:00** | Cuarentena; operación Silver exige fecha parseada, parada válida y timestamp hasta ese límite |
| MetroRiel / `VIAJE_SIN_EXIT` | `exit_station IS NULL OR exit_ts IS NULL` | Cuarentena; operación Silver conserva sólo viajes cerrados |

`FECHA_FUTURA` incluye fechas de formato no reconocido bajo el mismo motivo; no existe un motivo separado de fecha inválida. La implementación usa `to_date` y casts: no se afirma que detecte de forma segura cualquier fecha imposible o cualquier hora mal formada; algunos valores pueden detener el build. El límite fijo de calidad TU es distinto del cutoff de features, que se calcula con eventos válidos reales. Las reglas actuales son las de `silver_cuarentena.sql` y los cuatro modelos operacionales, sin añadir reglas ficticias.

## Idempotencia y trazabilidad

Reprocesar las mismas fuentes debe conservar conteos, claves y contenido de negocio. `bridge_identidad_usuario.fecha_proceso` (`current_date`) y `silver_cuarentena.fecha_deteccion` (`current_timestamp`) son auditoría dependiente de ejecución: no se garantiza igualdad byte a byte de esas tablas. La evidencia histórica de Fase 1 compara hashes Raw/Parquet y conteos SQL, no todos los bytes de Silver. La evidencia adicional de Fase 2 compara claves y contenido excluyendo sólo esos campos de auditoría; no sustituye las corridas históricas ni una demostración completa del flujo Prefect en la defensa.
