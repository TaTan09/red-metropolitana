with esperado as (
    select fecha_transbordo as fecha, hora_transbordo as hora,
           modo_origen, modo_destino, combinacion_modos, zona_origen, zona_destino,
           incluye_aerometro, count(*) as total_transbordos,
           round(avg(tiempo_transferencia_minutos), 2) as tiempo_promedio_transferencia_minutos,
           round(sum(tarifa_acumulada_gtq), 2) as tarifa_total_gtq
    from {{ ref('mart_multimodalidad') }}
    group by fecha_transbordo, hora_transbordo, modo_origen, modo_destino,
             combinacion_modos, zona_origen, zona_destino, incluye_aerometro
)
(select * from esperado except all select * from {{ ref('v_tableau_transbordos') }})
union all
(select * from {{ ref('v_tableau_transbordos') }} except all select * from esperado)
