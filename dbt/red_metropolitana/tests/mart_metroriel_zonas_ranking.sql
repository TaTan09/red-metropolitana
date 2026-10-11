-- Ranking independiente: 1 + cantidad de áreas con más abordajes, entre TODAS las áreas.
-- count(*) comprueba el grano de un abordaje por fila de fact_abordajes.
with por_area as (
    select z.zona_sk, count(a.abordaje_sk)::bigint as abordajes
    from {{ ref('dim_zona') }} z
    left join {{ ref('fact_abordajes') }} a on a.zona_sk = z.zona_sk
        and a.fuente_evento in ('Transmetro', 'Transurbano', 'Aerometro')
    group by z.zona_sk
),
red as (
    select sum(abordajes)::bigint as total, count(*)::integer as areas
    from por_area
)
select m.nombre_zona
from {{ ref('mart_metroriel_zonas') }} m
join por_area a on a.zona_sk = m.zona_sk
cross join red r
where m.ranking_demanda_otros_modos is distinct from
      (1 + (select count(*) from por_area otra where otra.abordajes > a.abordajes))
   or m.total_abordajes_otros_modos_red is distinct from r.total
   or m.areas_en_ranking_red is distinct from r.areas
   or m.pct_abordajes_otros_modos_red is distinct from
      coalesce(round(100.0 * a.abordajes / nullif(r.total, 0), 2), 0)
   or m.pct_abordajes_otros_modos_red not between 0 and 100
   or m.ranking_demanda_otros_modos not between 1 and r.areas
