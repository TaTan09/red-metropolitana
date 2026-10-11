{{ config(materialized='table') }}

-- Grano: una fila por zona con estaciones MetroRiel.
-- La demanda de otros modos excluye los viajes MetroRiel.
with estaciones as (
    select zona_sk, count(*)::integer as estaciones_metroriel
    from {{ ref('dim_punto_transporte') }}
    where modo = 'MetroRiel'
    group by zona_sk
),
abordajes as (
    select
        a.zona_sk,
        sum(a.cantidad_abordajes)::bigint as abordajes_otros_modos,
        sum(a.cantidad_abordajes) filter (where m.nombre_modo = 'Transmetro')::bigint
            as abordajes_transmetro,
        sum(a.cantidad_abordajes) filter (where m.nombre_modo = 'Transurbano')::bigint
            as abordajes_transurbano,
        sum(a.cantidad_abordajes) filter (where m.nombre_modo = 'Aerometro')::bigint
            as abordajes_aerometro
    from {{ ref('fact_abordajes') }} a
    join {{ ref('dim_modo') }} m on m.modo_sk = a.modo_sk
    where m.nombre_modo in ('Transmetro', 'Transurbano', 'Aerometro')
    group by a.zona_sk
),
viajes as (
    -- Un viaje cuenta una vez en su zona de origen; no se cuenta el destino.
    select zona_origen_sk, sum(cantidad_viajes)::bigint as viajes_metroriel_iniciados
    from {{ ref('fact_viajes_metroriel') }}
    group by zona_origen_sk
),
universo as (
    select
        z.zona_sk,
        z.nombre_zona,
        coalesce(a.abordajes_otros_modos, 0)::bigint as abordajes_otros_modos,
        coalesce(a.abordajes_transmetro, 0)::bigint as abordajes_transmetro,
        coalesce(a.abordajes_transurbano, 0)::bigint as abordajes_transurbano,
        coalesce(a.abordajes_aerometro, 0)::bigint as abordajes_aerometro,
        coalesce(v.viajes_metroriel_iniciados, 0)::bigint as viajes_metroriel_iniciados
    from {{ ref('dim_zona') }} z
    left join abordajes a on a.zona_sk = z.zona_sk
    left join viajes v on v.zona_origen_sk = z.zona_sk
),
ranking_red as (
    -- Se calcula en TODO dim_zona, incluidas las áreas sin abordajes.
    select
        u.*,
        sum(u.abordajes_otros_modos) over ()::bigint as total_abordajes_otros_modos_red,
        count(*) over ()::integer as areas_en_ranking_red,
        rank() over (order by u.abordajes_otros_modos desc) as ranking_demanda_otros_modos
    from universo u
)
select
    r.zona_sk,
    r.nombre_zona,
    e.estaciones_metroriel,
    r.abordajes_otros_modos,
    r.abordajes_transmetro,
    r.abordajes_transurbano,
    r.abordajes_aerometro,
    r.viajes_metroriel_iniciados,
    coalesce(round(100.0 * r.abordajes_otros_modos
        / nullif(r.total_abordajes_otros_modos_red, 0), 2), 0)
        as pct_abordajes_otros_modos_red,
    r.ranking_demanda_otros_modos,
    r.total_abordajes_otros_modos_red,
    r.areas_en_ranking_red
from ranking_red r
-- Seleccionar el trazado DESPUÉS del ranking y del denominador de toda la red.
join estaciones e on e.zona_sk = r.zona_sk
