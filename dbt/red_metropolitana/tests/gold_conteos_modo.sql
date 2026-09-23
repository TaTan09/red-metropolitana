with esperado as (
    select 'Transmetro'::text as modo, count(*) as filas
    from {{ ref('silver_transmetro_validaciones') }}
    union all
    select 'Transurbano', count(*)
    from {{ ref('silver_transurbano_transacciones') }}
    union all
    select 'Aerometro', count(*)
    from {{ ref('silver_aerometro_boardings') }}
),
obtenido as (
    select fuente_evento as modo, count(*) as filas
    from {{ ref('fact_abordajes') }}
    group by fuente_evento
)
select coalesce(e.modo, o.modo) as modo, e.filas as esperado, o.filas as obtenido
from esperado e
full outer join obtenido o using (modo)
where e.filas is distinct from o.filas
