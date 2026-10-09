{{ config(materialized='table') }}

-- Grano: una fila por zona del universo (dim_zona), con o sin servicio.
-- Oferta (dim_zona) + uso observado (mart_demanda_hora).
-- MetroRiel se cuenta por viaje iniciado, en la zona de origen (regla de mart_demanda_hora).
with uso as (
    select
        zona,
        sum(cantidad_eventos)::bigint as eventos_totales,
        sum(cantidad_eventos) filter (where modo = 'Transmetro')::bigint  as eventos_transmetro,
        sum(cantidad_eventos) filter (where modo = 'Transurbano')::bigint as eventos_transurbano,
        sum(cantidad_eventos) filter (where modo = 'MetroRiel')::bigint   as eventos_metroriel,
        sum(cantidad_eventos) filter (where modo = 'Aerometro')::bigint   as eventos_aerometro
    from {{ ref('mart_demanda_hora') }}
    group by zona
),
base as (
    select
        z.zona_sk,
        z.nombre_zona,
        z.tipo_area,
        z.tiene_servicio,
        z.modos_con_servicio,
        z.puntos_transporte,
        coalesce(u.eventos_totales, 0)     as eventos_totales,
        coalesce(u.eventos_transmetro, 0)  as eventos_transmetro,
        coalesce(u.eventos_transurbano, 0) as eventos_transurbano,
        coalesce(u.eventos_metroriel, 0)   as eventos_metroriel,
        coalesce(u.eventos_aerometro, 0)   as eventos_aerometro
    from {{ ref('dim_zona') }} z
    left join uso u on u.zona = z.nombre_zona
)
select
    b.*,
    round(b.eventos_totales::numeric / nullif(b.puntos_transporte, 0), 1) as eventos_por_punto,
    round(100.0 * b.eventos_totales / nullif(sum(b.eventos_totales) over (), 0), 2) as pct_demanda_red,
    rank() over (order by b.eventos_totales desc) as ranking_demanda,
    (b.tiene_servicio and b.eventos_totales = 0)
      or (not b.tiene_servicio and b.eventos_totales > 0) as inconsistencia_cobertura
from base b