{{ config(materialized='table', tags=['p2_12']) }}

with cortes as (
    {{ p2_12_cortes() }}
), previos as (
    select c.corte, c.fecha_corte, u.operador, u.llave_operacional,
           count(*) as eventos_previos_28d
    from cortes c
    join {{ ref('silver_p2_usos_tarjeta') }} u
      on u.fecha_uso >= c.fecha_corte - interval '28 days'
     and u.fecha_uso < c.fecha_corte
     and u.disponible_desde < c.fecha_corte
    group by c.corte, c.fecha_corte, u.operador, u.llave_operacional
    having count(*) >= 2
), poblacion as (
    select p.*
    from previos p
    -- Interpretación literal confirmada: cualquier DELETE previo excluye,
    -- incluso si después hubo reactivación. No consultar vigente/valid_to:
    -- dependen de eventos futuros respecto del corte.
    where not exists (
        select 1 from {{ ref('silver_padron_transmetro_scd2') }} d
        where p.operador = 'Transmetro'
          and d.tarjeta_id = p.llave_operacional
          and d.operacion = 'DELETE'
          and d.valid_from < p.fecha_corte
    )
), futuros as (
    select c.corte, u.operador, u.llave_operacional,
           count(*) as eventos_futuros_30d
    from cortes c
    join {{ ref('silver_p2_usos_tarjeta') }} u
      on u.fecha_uso >= c.fecha_corte
     and u.fecha_uso < c.fecha_corte + interval '30 days'
     and u.disponible_desde < c.fecha_corte + interval '30 days'
    group by c.corte, u.operador, u.llave_operacional
)
select
    -- Los nombres de operador son un vocabulario fijo sin ':'. La llave puede
    -- contener ':' sin perder el namespace; el ID no depende de corte/identidad.
    md5(p.operador || ':' || p.llave_operacional) as unidad_id,
    p.operador, p.llave_operacional, p.corte, p.fecha_corte,
    p.eventos_previos_28d,
    coalesce(f.eventos_futuros_30d, 0) as eventos_futuros_30d,
    case when coalesce(f.eventos_futuros_30d, 0) = 0 then 1 else 0 end as etiqueta
from poblacion p
left join futuros f
  on f.corte = p.corte and f.operador = p.operador
 and f.llave_operacional = p.llave_operacional
