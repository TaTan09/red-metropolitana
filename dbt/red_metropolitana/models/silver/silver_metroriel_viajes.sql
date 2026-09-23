-- Conserva viajes cerrados con entrada y salida
{{ config(materialized='table') }}

select
    trip_id::text as viaje_id,
    card::text as tarjeta_mr,
    entry_station::text as origen_estacion_id,
    exit_station::text as destino_estacion_id,
    entry_ts::timestamp as fecha_hora_ingreso,
    exit_ts::timestamp as fecha_hora_salida,
    fare_gtq::numeric as tarifa_quetzales,
    round(duration_s::numeric / 60.0, 2) as duracion_minutos,
    bronze_record_id,
    ingesta_timestamp
from {{ source('staging', 'metroriel_viajes') }}
where exit_station is not null
  and exit_ts is not null
