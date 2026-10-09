-- El mart debe sumar lo mismo que mart_demanda_hora, en total y por modo.
with c as (
    select sum(eventos_totales) as total,
           sum(eventos_transmetro) as tm, sum(eventos_transurbano) as tu,
           sum(eventos_metroriel) as mr, sum(eventos_aerometro) as am
    from {{ ref('mart_cobertura') }}
),
d as (
    select sum(cantidad_eventos) as total,
           sum(cantidad_eventos) filter (where modo = 'Transmetro')  as tm,
           sum(cantidad_eventos) filter (where modo = 'Transurbano') as tu,
           sum(cantidad_eventos) filter (where modo = 'MetroRiel')   as mr,
           sum(cantidad_eventos) filter (where modo = 'Aerometro')   as am
    from {{ ref('mart_demanda_hora') }}
)
select c.total as total_cobertura, d.total as total_demanda
from c cross join d
where c.total is distinct from d.total
   or c.tm is distinct from d.tm or c.tu is distinct from d.tu
   or c.mr is distinct from d.mr or c.am is distinct from d.am
   or c.total <> c.tm + c.tu + c.mr + c.am