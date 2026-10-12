-- Comparación fila a fila en ambos sentidos, incluyendo ranking y denominador de red.
with esperado as (
    select nombre_zona, estaciones_metroriel, abordajes_otros_modos,
           abordajes_transmetro, abordajes_transurbano, abordajes_aerometro,
           viajes_metroriel_iniciados, pct_abordajes_otros_modos_red,
           ranking_demanda_otros_modos, total_abordajes_otros_modos_red,
           areas_en_ranking_red
    from {{ ref('mart_metroriel_zonas') }}
),
obtenido as (
    select nombre_zona, estaciones_metroriel, abordajes_otros_modos,
           abordajes_transmetro, abordajes_transurbano, abordajes_aerometro,
           viajes_metroriel_iniciados, pct_abordajes_otros_modos_red,
           ranking_demanda_otros_modos, total_abordajes_otros_modos_red,
           areas_en_ranking_red
    from {{ ref('v_tableau_metroriel') }}
)
select 'fila_faltante_o_distinta_en_vista' as problema, nombre_zona
from (select * from esperado except all select * from obtenido) faltantes
union all
select 'fila_extra_o_distinta_en_vista', nombre_zona
from (select * from obtenido except all select * from esperado) extras
