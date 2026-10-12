-- Comprueba completitud, consecutividad y trazabilidad contra los hechos Gold.
with eventos as (
    select f.usuario_sk, m.nombre_modo as modo, t.fecha_hora, f.bronze_record_id
    from {{ ref('fact_abordajes') }} f
    join {{ ref('dim_modo') }} m using (modo_sk)
    join {{ ref('dim_tiempo') }} t using (tiempo_sk)
    union all
    select f.usuario_sk, 'MetroRiel', t.fecha_hora, f.bronze_record_id
    from {{ ref('fact_viajes_metroriel') }} f
    join {{ ref('dim_tiempo') }} t on t.tiempo_sk = f.tiempo_ingreso_sk
), secuencia as (
    select *, lag(modo) over w as modo_previo,
           lag(fecha_hora) over w as fecha_previa,
           lag(bronze_record_id) over w as id_previo
    from eventos
    window w as (partition by usuario_sk order by fecha_hora, modo, bronze_record_id)
), esperado as (
    select usuario_sk, id_previo as bronze_record_id_origen, bronze_record_id as bronze_record_id_destino
    from secuencia where modo != modo_previo
      and fecha_hora > fecha_previa and fecha_hora <= fecha_previa + interval '90 minutes'
), real as (
    select usuario_sk, bronze_record_id_origen, bronze_record_id_destino
    from {{ ref('mart_multimodalidad') }}
)
(select * from esperado except all select * from real)
union all
(select * from real except all select * from esperado)
