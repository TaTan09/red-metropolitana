-- Las cinco zonas son una expectativa del dataset actual, no un filtro del mart.
with esperado as (
    select p.zona_sk, z.nombre_zona, count(*)::integer as estaciones
    from {{ ref('dim_punto_transporte') }} p
    join {{ ref('dim_zona') }} z on z.zona_sk = p.zona_sk
    where p.modo = 'MetroRiel'
    group by p.zona_sk, z.nombre_zona
)
select 'zona_o_estaciones_distintas_del_catalogo' as problema,
       coalesce(e.zona_sk, m.zona_sk) as detalle
from esperado e
full outer join {{ ref('mart_metroriel_zonas') }} m using (zona_sk)
where e.estaciones is distinct from m.estaciones_metroriel
   or e.nombre_zona is distinct from m.nombre_zona
   or m.estaciones_metroriel <= 0
union all
select 'cantidad_de_zonas_distinta_de_cinco', count(*)::text
from {{ ref('mart_metroriel_zonas') }}
having count(*) <> 5
union all
select 'universo_de_areas_distinto_de_dieciseis', count(*)::text
from {{ ref('dim_zona') }}
having count(*) <> 16
