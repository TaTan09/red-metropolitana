{{ config(materialized='view') }}

-- No expone eventos_totales: mezcla abordajes con viajes.
with base as (
    select
        nombre_zona, tipo_area, tiene_servicio, modos_con_servicio,
        puntos_transporte, puntos_transmetro, puntos_transurbano,
        puntos_metroriel, puntos_aerometro,
        (eventos_transmetro + eventos_transurbano + eventos_aerometro) as abordajes,
        eventos_transmetro  as abordajes_transmetro,
        eventos_transurbano as abordajes_transurbano,
        eventos_aerometro   as abordajes_aerometro,
        eventos_metroriel   as viajes_mr_iniciados,
        eventos_por_punto_transmetro, eventos_por_punto_transurbano,
        eventos_por_punto_aerometro, viajes_por_estacion_metroriel
    from {{ ref('mart_cobertura') }}
)
select
    b.*,
    round(100.0 * b.abordajes / nullif(sum(b.abordajes) over (), 0), 2) as pct_abordajes_red,
    rank() over (order by b.abordajes desc)           as ranking_abordajes,
    rank() over (order by b.viajes_mr_iniciados desc) as ranking_viajes_mr_origen
from base b