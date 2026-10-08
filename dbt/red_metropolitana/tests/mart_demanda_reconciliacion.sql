with esperado as (
    select
        (select count(*) from {{ ref('fact_abordajes') }})
        + (select count(*) from {{ ref('fact_viajes_metroriel') }}) as eventos,
        (select coalesce(sum(tarifa_quetzales), 0) from {{ ref('fact_abordajes') }})
        + (select coalesce(sum(tarifa_quetzales), 0) from {{ ref('fact_viajes_metroriel') }}) as tarifa
),
obtenido as (
    select sum(cantidad_eventos) as eventos, sum(tarifa_total_gtq) as tarifa
    from {{ ref('mart_demanda_hora') }}
)
select e.eventos as eventos_esperados, o.eventos as eventos_obtenidos,
       e.tarifa as tarifa_esperada, o.tarifa as tarifa_obtenida
from esperado e
cross join obtenido o
where e.eventos is distinct from o.eventos
   or e.tarifa is distinct from o.tarifa