{{ config(materialized='view') }}

-- Tableau usa esta vista: abordajes y viajes conservan unidades distintas.
select
    nombre_zona,
    estaciones_metroriel,
    abordajes_otros_modos,
    abordajes_transmetro,
    abordajes_transurbano,
    abordajes_aerometro,
    viajes_metroriel_iniciados,
    pct_abordajes_otros_modos_red,
    ranking_demanda_otros_modos,
    total_abordajes_otros_modos_red,
    areas_en_ranking_red
from {{ ref('mart_metroriel_zonas') }}
