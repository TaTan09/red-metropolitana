# Calidad y cuarentena de Silver

## Conteos por regla

| Fuente | Regla | Violaciones |
|---|---|---:|
| MetroRiel | `VIAJE_SIN_EXIT` | 3,589 |
| Transmetro | `DUPLICADO_TORNIQUETE` | 1,115 |
| Transurbano | `COD_PARADA_NULO` | 4,189 |
| Transurbano | `FECHA_FUTURA` | 817 |
| **Total** | | **9,710** |

Las **9,710** filas son violaciones de reglas (`UNION ALL`), no 9,710 registros distintos. Tres transacciones de Transurbano infringen a la vez `COD_PARADA_NULO` y `FECHA_FUTURA`. Por tanto hay **9,707 registros únicos** en cuarentena: 1,115 de Transmetro, 5,003 de Transurbano y 3,589 de MetroRiel. La intersección se comprobó sobre el Parquet Bronze y con `count(DISTINCT (fuente, id_registro_crudo))` en PostgreSQL tras ejecutar dbt.

`silver.silver_cuarentena.id_registro_crudo` usa el identificador técnico estable del registro Bronze. Una misma fila puede aparecer varias veces con motivos distintos. Para verificar en PostgreSQL:

```sql
SELECT count(*) AS violaciones,
       count(DISTINCT (fuente, id_registro_crudo)) AS registros_unicos
FROM silver.silver_cuarentena;

SELECT fuente, count(*) AS violaciones,
       count(DISTINCT id_registro_crudo) AS registros_unicos
FROM silver.silver_cuarentena
GROUP BY fuente;
```

Las reglas de calidad se aplican en Silver. Staging conserva duplicados, paradas vacías, fechas futuras y viajes sin salida.

## Padrón Transmetro

`silver.silver_padron_transmetro_scd2` genera una versión por evento CDC de llave Transmetro y ordena por `seq`. Incluye vigencia por secuencia y fecha de commit, operación, estado, perfil y zona. El estado vigente debe reconciliar con `staging.padron_transmetro_actual`: **17,432 tarjetas totales, 15,096 activas y 2,336 inactivas**. Un snapshot ejecutado solo contra ese estado vigente no reproduce las versiones previas del CDC.
