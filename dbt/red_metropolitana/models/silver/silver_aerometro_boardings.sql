{{ config(materialized='table') }}

with am_base as (
    select 
        b.boarding_id::text as boarding_id,
        b.user_hash::text as user_hash,
        b.station_code::text as station_code,
        b.axis::text as eje,
        -- Conversión UTC a Hora Oficial Guatemala (CST / UTC-6)
        (b.timestamp_utc::timestamp at time zone 'UTC' at time zone 'America/Guatemala')::timestamp as fecha_hora,
        b.cabin_number,
        coalesce(b.fare::numeric, 3.00) as tarifa_quetzales,
        b.bronze_record_id,
        b.ingesta_timestamp,
        e.district as zona_cruda
    from {{ source('staging', 'aerometro_boardings') }} b
    left join {{ source('staging', 'am_estaciones') }} e on b.station_code = e.station_code
)

select
    boarding_id,
    user_hash,
    station_code,
    eje,
    fecha_hora,
    cabin_number,
    {{ normalizar_zona('zona_cruda') }} as zona_conformada,
    tarifa_quetzales,
    bronze_record_id,
    ingesta_timestamp
from am_base
