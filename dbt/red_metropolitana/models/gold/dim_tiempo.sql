{{ config(materialized='table') }}

with instantes as (
    select fecha_hora from {{ ref('silver_transmetro_validaciones') }}
    union
    select fecha_hora from {{ ref('silver_transurbano_transacciones') }}
    union
    select fecha_hora from {{ ref('silver_aerometro_boardings') }}
    union
    select fecha_hora_ingreso from {{ ref('silver_metroriel_viajes') }}
    union
    select fecha_hora_salida from {{ ref('silver_metroriel_viajes') }}
)
select
    to_char(fecha_hora, 'YYYYMMDDHH24MISS')::bigint as tiempo_sk,
    fecha_hora,
    fecha_hora::date as fecha,
    extract(year from fecha_hora)::integer as anio,
    extract(month from fecha_hora)::integer as mes,
    extract(day from fecha_hora)::integer as dia,
    extract(isodow from fecha_hora)::integer as dia_semana_iso,
    extract(hour from fecha_hora)::integer as hora,
    extract(minute from fecha_hora)::integer as minuto,
    extract(second from fecha_hora)::integer as segundo,
    (extract(isodow from fecha_hora) between 1 and 5) as es_dia_habil,
    (
        extract(isodow from fecha_hora) between 1 and 5
        and (extract(hour from fecha_hora) between 6 and 8
             or extract(hour from fecha_hora) between 17 and 19)
    ) as es_hora_pico
from instantes
where fecha_hora is not null
