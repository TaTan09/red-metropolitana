-- Conserva viajes cerrados con entrada y salida
{{ config(materialized='table') }}

select
    viaje_id::text as viaje_id,
    tarjeta_mr::text as tarjeta_mr,
    origen_estacion_id::text as origen_estacion_id,
    destino_estacion_id::text as destino_estacion_id,
    fecha_hora_ingreso::timestamp as fecha_hora_ingreso,
    fecha_hora_salida::timestamp as fecha_hora_salida,
    coalesce(monto_viaje::numeric, 2.50) as tarifa_quetzales,
    round(extract(epoch from (fecha_hora_salida::timestamp - fecha_hora_ingreso::timestamp)) / 60.0, 2) as duracion_minutos,
    ingesta_timestamp
from {{ source('bronze', 'metroriel_viajes') }}
where destino_estacion_id is not null 
  and fecha_hora_salida is not null