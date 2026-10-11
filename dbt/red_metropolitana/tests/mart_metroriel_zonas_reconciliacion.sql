-- Recalcular desde los hechos, usando fuente_evento en vez del join de modos del mart.
-- MetroRiel nunca entra en la medida de abordajes de otros modos.
with abordajes as (
    select zona_sk,
        sum(cantidad_abordajes)::bigint as total,
        sum(cantidad_abordajes) filter (where fuente_evento = 'Transmetro')::bigint as tm,
        sum(cantidad_abordajes) filter (where fuente_evento = 'Transurbano')::bigint as tu,
        sum(cantidad_abordajes) filter (where fuente_evento = 'Aerometro')::bigint as am
    from {{ ref('fact_abordajes') }}
    where fuente_evento in ('Transmetro', 'Transurbano', 'Aerometro')
    group by zona_sk
),
viajes as (
    select zona_origen_sk, sum(cantidad_viajes)::bigint as mr
    from {{ ref('fact_viajes_metroriel') }}
    group by zona_origen_sk
)
select m.nombre_zona
from {{ ref('mart_metroriel_zonas') }} m
left join abordajes a on a.zona_sk = m.zona_sk
left join viajes v on v.zona_origen_sk = m.zona_sk
where m.abordajes_otros_modos is distinct from coalesce(a.total, 0)
   or m.abordajes_transmetro is distinct from coalesce(a.tm, 0)
   or m.abordajes_transurbano is distinct from coalesce(a.tu, 0)
   or m.abordajes_aerometro is distinct from coalesce(a.am, 0)
   or m.viajes_metroriel_iniciados is distinct from coalesce(v.mr, 0)
   or m.abordajes_otros_modos <> m.abordajes_transmetro
       + m.abordajes_transurbano + m.abordajes_aerometro
   or least(m.abordajes_transmetro, m.abordajes_transurbano,
            m.abordajes_aerometro, m.viajes_metroriel_iniciados) < 0
