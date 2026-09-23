{{ config(materialized='table') }}

with ranked as (
    select 
        estacion_id::text as estacion_id,
        tarjeta::text as tarjeta_id,
        fecha_hora::timestamp as fecha_hora,
        linea::text as linea,
        coalesce(tarifa::numeric, 1.00) as tarifa_quetzales,
        ingesta_timestamp,
        row_number() over(
            partition by tarjeta, estacion_id, fecha_hora 
            order by ingesta_timestamp
        ) as rn
    from {{ source('bronze', 'transmetro_validaciones') }}
)

select
    estacion_id,
    tarjeta_id,
    fecha_hora,
    linea,
    tarifa_quetzales,
    ingesta_timestamp
from ranked
where rn = 1