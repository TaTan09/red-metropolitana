{{ config(materialized='view', tags=['p2_12']) }}

-- Sólo operaciones Silver. Un viaje MR cerrado es UN uso fechado por ingreso;
-- disponible_desde impide utilizarlo antes de su cierre (convención P1).
with operaciones as (
    select 'Transmetro'::text as operador, tarjeta_id as llave_operacional,
           bronze_record_id as evento_id, fecha_hora as fecha_uso,
           fecha_hora as disponible_desde
    from {{ ref('silver_transmetro_validaciones') }}
    union all
    select 'Transurbano', id_tarjeta, bronze_record_id, fecha_hora, fecha_hora
    from {{ ref('silver_transurbano_transacciones') }}
    union all
    select 'MetroRiel', tarjeta_mr, bronze_record_id, fecha_hora_ingreso, fecha_hora_salida
    from {{ ref('silver_metroriel_viajes') }}
    union all
    select 'Aerometro', user_hash, bronze_record_id, fecha_hora, fecha_hora
    from {{ ref('silver_aerometro_boardings') }}
)
select o.*
from operaciones o
where o.llave_operacional is not null and trim(o.llave_operacional) <> ''
  and o.fecha_uso is not null and o.disponible_desde is not null
  and not exists (
      select 1 from {{ ref('silver_cuarentena') }} q
      where q.fuente = o.operador and q.id_registro_crudo = o.evento_id
  )
