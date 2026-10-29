{{ config(materialized='table', tags=['p2_13'], indexes=[{'columns': ['unidad_id', 'fecha_corte'], 'unique': true}]) }}

-- Grano TARJETA: no enlazar operadores mediante identidad personal inferida.
with eventos as (
    select p.unidad_id, p.fecha_corte, u.*,
           (extract(isodow from u.fecha_uso) between 1 and 5
            and extract(hour from u.fecha_uso) in (6, 7, 8, 17, 18, 19)) as hora_pico
    from {{ ref('silver_p2_poblacion_tarjeta') }} p
    join {{ ref('silver_p2_usos_tarjeta') }} u
      on u.operador = p.operador and u.llave_operacional = p.llave_operacional
     and u.fecha_uso >= p.fecha_corte - interval '28 days'
     and u.fecha_uso < p.fecha_corte
     and u.disponible_desde < p.fecha_corte
), agregados as (
    select unidad_id, fecha_corte,
           count(*) as viajes_28d,
           count(*) filter (where fecha_uso >= fecha_corte - interval '7 days') as viajes_7d,
           count(*) filter (where fecha_uso >= fecha_corte - interval '14 days') as viajes_14d,
           count(distinct fecha_uso::date) as dias_activos_28d,
           extract(epoch from (fecha_corte - max(fecha_uso))) / 86400.0 as dias_desde_ultimo_uso,
           sum(tarifa_quetzales) as gasto_28d_gtq,
           avg(tarifa_quetzales) as tarifa_media_gtq,
           count(distinct punto_origen) as puntos_origen_28d,
           count(*) filter (where hora_pico)::numeric / count(*) as proporcion_hora_pico,
           count(*) filter (where extract(isodow from fecha_uso) in (6, 7))::numeric / count(*) as proporcion_fin_semana
    from eventos group by unidad_id, fecha_corte
)
select p.unidad_id, p.corte, p.fecha_corte, p.operador,
       a.viajes_28d, a.viajes_7d, a.viajes_14d, a.dias_activos_28d,
       a.dias_desde_ultimo_uso, a.gasto_28d_gtq, a.tarifa_media_gtq,
       a.puntos_origen_28d, a.proporcion_hora_pico, a.proporcion_fin_semana,
       p.etiqueta
from {{ ref('silver_p2_poblacion_tarjeta') }} p
join agregados a using (unidad_id, fecha_corte)
