{{ config(materialized='table') }}

-- Sólo Silver. El corte por defecto es el máximo timestamp real de las cuatro
-- fuentes, incluidas las salidas MR. Se puede fijar para un snapshot histórico.
with limites as (
    select max(fecha_hora) as instante from {{ ref('silver_transmetro_validaciones') }}
    union all select max(fecha_hora) from {{ ref('silver_transurbano_transacciones') }}
    union all select max(fecha_hora) from {{ ref('silver_aerometro_boardings') }}
    union all select max(fecha_hora_ingreso) from {{ ref('silver_metroriel_viajes') }}
    union all select max(fecha_hora_salida) from {{ ref('silver_metroriel_viajes') }}
), corte as (
    select
        {% if var('features_cutoff', none) is not none %}
        '{{ var("features_cutoff") | replace("'", "''") }}'::timestamp
        {% else %}
        max(instante)
        {% endif %} as fecha_corte
    from limites
), operaciones as (
    select 'Transmetro'::text as modo, tarjeta_id as llave_origen,
           fecha_hora, fecha_hora as disponible_desde, tarifa_quetzales,
           estacion_id as codigo_punto
    from {{ ref('silver_transmetro_validaciones') }}
    union all
    select 'Transurbano', id_tarjeta, fecha_hora, fecha_hora, tarifa_quetzales, cod_parada
    from {{ ref('silver_transurbano_transacciones') }}
    union all
    select 'Aerometro', user_hash, fecha_hora, fecha_hora, tarifa_quetzales, station_code
    from {{ ref('silver_aerometro_boardings') }}
    union all
    select 'MetroRiel', tarjeta_mr, fecha_hora_ingreso, fecha_hora_salida,
           tarifa_quetzales, origen_estacion_id
    from {{ ref('silver_metroriel_viajes') }}
), eventos as (
    select p.usuario_canonico_id, p.metodo_match, p.nivel_confianza,
           o.modo, o.fecha_hora, o.tarifa_quetzales, c.fecha_corte,
           coalesce(z.zona_conformada, 'ZONA_DESCONOCIDA') as zona_origen,
           (extract(isodow from o.fecha_hora) between 1 and 5
            and extract(hour from o.fecha_hora) in (6, 7, 8, 17, 18, 19)) as es_hora_pico
    from operaciones o
    inner join {{ ref('bridge_identidad_usuario') }} p
        on p.sistema_origen = o.modo and p.llave_origen = o.llave_origen
    left join {{ ref('silver_catalogo_puntos') }} z
        on z.modo = o.modo and z.codigo_punto = o.codigo_punto
    cross join corte c
    where o.fecha_hora <= c.fecha_corte
      and o.disponible_desde <= c.fecha_corte
), modos as (
    select distinct on (usuario_canonico_id) usuario_canonico_id, modo
    from eventos group by usuario_canonico_id, modo
    order by usuario_canonico_id, count(*) desc, modo asc
), zonas as (
    select distinct on (usuario_canonico_id) usuario_canonico_id, zona_origen
    from eventos group by usuario_canonico_id, zona_origen
    order by usuario_canonico_id, count(*) desc, zona_origen asc
), agregados as (
    select usuario_canonico_id, min(metodo_match) as metodo_match,
           min(nivel_confianza) as nivel_confianza, fecha_corte,
           count(*) as total_eventos, count(distinct modo)::integer as modos_utilizados,
           count(distinct fecha_hora::date) as dias_activos,
           min(fecha_hora) as primer_evento, max(fecha_hora) as ultimo_evento,
           count(*) filter (where fecha_hora > fecha_corte - interval '7 days') as eventos_ultimos_7_dias,
           count(*) filter (where fecha_hora > fecha_corte - interval '30 days') as eventos_ultimos_30_dias,
           count(*) filter (where fecha_hora > fecha_corte - interval '90 days') as eventos_ultimos_90_dias,
           count(*) filter (where es_hora_pico)::numeric / count(*) as proporcion_eventos_hora_pico,
           round(sum(tarifa_quetzales)::numeric, 2) as gasto_total_gtq,
           round(avg(tarifa_quetzales)::numeric, 2) as tarifa_promedio_gtq,
           count(*) filter (where modo = 'Transmetro') as eventos_transmetro,
           count(*) filter (where modo = 'Transurbano') as eventos_transurbano,
           count(*) filter (where modo = 'Aerometro') as eventos_aerometro,
           count(*) filter (where modo = 'MetroRiel') as eventos_metroriel
    from eventos group by usuario_canonico_id, fecha_corte
)
select a.usuario_canonico_id, a.metodo_match, a.nivel_confianza, a.fecha_corte,
       a.total_eventos, a.modos_utilizados, (a.modos_utilizados > 1) as es_multimodal,
       a.dias_activos, a.primer_evento, a.ultimo_evento,
       floor(extract(epoch from (a.ultimo_evento - a.primer_evento)) / 86400)::integer as span_dias_uso,
       a.eventos_ultimos_7_dias, a.eventos_ultimos_30_dias, a.eventos_ultimos_90_dias,
       m.modo as modo_mas_usado,
       floor(extract(epoch from (a.fecha_corte - a.ultimo_evento)) / 86400)::integer as dias_desde_ultimo_evento,
       a.proporcion_eventos_hora_pico, z.zona_origen as zona_origen_frecuente,
       a.gasto_total_gtq, a.tarifa_promedio_gtq,
       a.eventos_transmetro, a.eventos_transurbano, a.eventos_aerometro, a.eventos_metroriel,
       (a.eventos_aerometro > 0) as usa_aerometro
from agregados a
inner join modos m on m.usuario_canonico_id = a.usuario_canonico_id
inner join zonas z on z.usuario_canonico_id = a.usuario_canonico_id
