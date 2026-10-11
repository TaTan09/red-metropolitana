-- Los puntos por modo deben sumar el total de la zona y cuadrar con dim_punto_transporte.
select nombre_zona as detalle, 'suma_por_modo_distinta_del_total' as problema
from {{ ref('mart_cobertura') }}
where puntos_transmetro + puntos_transurbano + puntos_metroriel + puntos_aerometro
      <> puntos_transporte
union all
select z.modo, 'total_por_modo_distinto_de_dim_punto_transporte'
from (
    select 'Transmetro' as modo, sum(puntos_transmetro) as n from {{ ref('dim_zona') }}
    union all select 'Transurbano', sum(puntos_transurbano) from {{ ref('dim_zona') }}
    union all select 'MetroRiel',   sum(puntos_metroriel)   from {{ ref('dim_zona') }}
    union all select 'Aerometro',   sum(puntos_aerometro)   from {{ ref('dim_zona') }}
) z
left join (
    select modo, count(*) as n from {{ ref('dim_punto_transporte') }} group by modo
) p on p.modo = z.modo
where z.n is distinct from p.n