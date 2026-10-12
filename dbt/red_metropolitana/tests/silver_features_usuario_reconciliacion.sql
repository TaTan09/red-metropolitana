with operaciones as (
    select 'Transmetro'::text modo, tarjeta_id llave, fecha_hora fecha, fecha_hora disponible,
           tarifa_quetzales tarifa, estacion_id punto
    from {{ ref('silver_transmetro_validaciones') }}
    union all select 'Transurbano', id_tarjeta, fecha_hora, fecha_hora, tarifa_quetzales, cod_parada
    from {{ ref('silver_transurbano_transacciones') }}
    union all select 'Aerometro', user_hash, fecha_hora, fecha_hora, tarifa_quetzales, station_code
    from {{ ref('silver_aerometro_boardings') }}
    union all select 'MetroRiel', tarjeta_mr, fecha_hora_ingreso, fecha_hora_salida, tarifa_quetzales, origen_estacion_id
    from {{ ref('silver_metroriel_viajes') }}
), corte as (
    select min(fecha_corte) as cutoff from {{ ref('silver_features_usuario') }}
), eventos as (
    select b.usuario_canonico_id, o.*, c.cutoff,
           coalesce(z.zona_conformada, 'ZONA_DESCONOCIDA') zona
    from operaciones o
    join {{ ref('bridge_identidad_usuario') }} b on b.sistema_origen = o.modo and b.llave_origen = o.llave
    left join {{ ref('silver_catalogo_puntos') }} z on z.modo = o.modo and z.codigo_punto = o.punto
    cross join corte c where o.fecha <= c.cutoff and o.disponible <= c.cutoff
), esperado as (
    select usuario_canonico_id, count(*) total, count(distinct modo) modos,
           min(fecha) primero, max(fecha) ultimo, count(distinct fecha::date) dias,
           count(*) filter (where fecha > cutoff - interval '7 days') e7,
           count(*) filter (where fecha > cutoff - interval '30 days') e30,
           count(*) filter (where fecha > cutoff - interval '90 days') e90,
           round(sum(tarifa)::numeric, 2) gasto, round(avg(tarifa)::numeric, 2) promedio,
           count(*) filter (where extract(isodow from fecha) between 1 and 5
             and extract(hour from fecha) in (6,7,8,17,18,19))::numeric / count(*) pico
    from eventos group by usuario_canonico_id
), favoritos as (
    select distinct on (usuario_canonico_id) usuario_canonico_id, modo
    from eventos group by usuario_canonico_id, modo
    order by usuario_canonico_id, count(*) desc, modo
), zonas as (
    select distinct on (usuario_canonico_id) usuario_canonico_id, zona
    from eventos group by usuario_canonico_id, zona
    order by usuario_canonico_id, count(*) desc, zona
)
select coalesce(e.usuario_canonico_id, f.usuario_canonico_id) as usuario
from esperado e
full join {{ ref('silver_features_usuario') }} f using (usuario_canonico_id)
left join favoritos m on m.usuario_canonico_id = e.usuario_canonico_id
left join zonas z on z.usuario_canonico_id = e.usuario_canonico_id
where e.usuario_canonico_id is null or f.usuario_canonico_id is null
   or (f.total_eventos, f.modos_utilizados, f.primer_evento, f.ultimo_evento, f.dias_activos,
       f.eventos_ultimos_7_dias, f.eventos_ultimos_30_dias, f.eventos_ultimos_90_dias,
       f.gasto_total_gtq, f.tarifa_promedio_gtq, f.proporcion_eventos_hora_pico,
       f.modo_mas_usado, f.zona_origen_frecuente)
      is distinct from
      (e.total, e.modos, e.primero, e.ultimo, e.dias, e.e7, e.e30, e.e90,
       e.gasto, e.promedio, e.pico, m.modo, z.zona)
