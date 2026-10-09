-- Una fila por zona de dim_zona, sin repetidas.
select 'filas_distintas_de_dim_zona' as problema, count(*)::text as detalle
from {{ ref('mart_cobertura') }}
having count(*) <> (select count(*) from {{ ref('dim_zona') }})
union all
select 'zona_repetida', nombre_zona
from {{ ref('mart_cobertura') }}
group by nombre_zona
having count(*) > 1