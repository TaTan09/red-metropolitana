{{ config(tags=['p2_13']) }}
with f as (select * from {{ ref('silver_p2_features_tarjeta') }}),
     p as (select * from {{ ref('silver_p2_poblacion_tarjeta') }})
select coalesce(f.unidad_id, p.unidad_id) as unidad_id
from f full join p using (unidad_id, fecha_corte)
where f.unidad_id is null or p.unidad_id is null
   or f.etiqueta is distinct from p.etiqueta
   or f.viajes_28d is distinct from p.eventos_previos_28d
   or f.viajes_7d < 0 or f.viajes_7d > f.viajes_14d or f.viajes_14d > f.viajes_28d
   or f.dias_activos_28d not between 1 and 28
   or f.dias_desde_ultimo_uso <= 0 or f.dias_desde_ultimo_uso > 28
   or f.proporcion_hora_pico not between 0 and 1
   or f.proporcion_fin_semana not between 0 and 1
   or (f.corte = 'C' and f.etiqueta is not null)
union all
select unidad_id from f group by unidad_id, fecha_corte having count(*) <> 1
