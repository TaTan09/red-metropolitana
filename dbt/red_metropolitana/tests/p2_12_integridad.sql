{{ config(tags=['p2_12']) }}

select corte, unidad_id
from {{ ref('silver_p2_poblacion_tarjeta') }}
where eventos_previos_28d < 2 or eventos_futuros_30d < 0
   or (corte <> 'C' and (etiqueta is null or etiqueta <> case when eventos_futuros_30d = 0 then 1 else 0 end))
   or (corte = 'C' and (etiqueta is not null or eventos_futuros_30d is not null))
   or unidad_id <> md5(operador || ':' || llave_operacional)
union all
select corte, unidad_id
from {{ ref('silver_p2_poblacion_tarjeta') }}
group by corte, unidad_id
having count(*) > 1
union all
select corte, min(unidad_id)
from {{ ref('silver_p2_poblacion_tarjeta') }}
group by corte, operador, llave_operacional
having count(*) > 1
