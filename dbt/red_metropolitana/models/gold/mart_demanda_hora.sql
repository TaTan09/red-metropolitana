{{ config(materialized='table') }}

-- Grano: fecha x hora x modo x zona.
-- MetroRiel cuenta una vez por viaje, en el ingreso y en la zona de origen.
with eventos as (
    select
        tiempo_sk,
        zona_sk,
        modo_sk,
        'abordaje'::text as tipo_evento,
        cantidad_abordajes as cantidad_eventos,
        tarifa_quetzales
    from {{ ref('fact_abordajes') }}
    union all
    select
        tiempo_ingreso_sk,
        zona_origen_sk,
        modo_sk,
        'viaje'::text,
        cantidad_viajes,
        tarifa_quetzales
    from {{ ref('fact_viajes_metroriel') }}
)
select
    t.fecha,
    t.hora,
    t.es_dia_habil,
    t.es_hora_pico,
    m.nombre_modo as modo,
    z.nombre_zona as zona,
    e.tipo_evento,
    sum(e.cantidad_eventos)::bigint as cantidad_eventos,
    sum(e.tarifa_quetzales) as tarifa_total_gtq
from eventos e
join {{ ref('dim_tiempo') }} t on t.tiempo_sk = e.tiempo_sk
join {{ ref('dim_zona') }} z on z.zona_sk = e.zona_sk
join {{ ref('dim_modo') }} m on m.modo_sk = e.modo_sk
group by t.fecha, t.hora, t.es_dia_habil, t.es_hora_pico,
         m.nombre_modo, z.nombre_zona, e.tipo_evento