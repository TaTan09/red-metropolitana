{{ config(materialized='table') }}

-- Grano: un viaje Silver cerrado con origen, destino, ingreso y salida.
select
    md5('MetroRiel:' || v.bronze_record_id) as viaje_sk,
    {{ usuario_sk('b.usuario_canonico_id') }} as usuario_sk,
    to_char(v.fecha_hora_ingreso, 'YYYYMMDDHH24MISS')::bigint as tiempo_ingreso_sk,
    to_char(v.fecha_hora_salida, 'YYYYMMDDHH24MISS')::bigint as tiempo_salida_sk,
    md5(origen.zona_conformada) as zona_origen_sk,
    md5(destino.zona_conformada) as zona_destino_sk,
    md5('MetroRiel:' || v.origen_estacion_id) as punto_origen_sk,
    md5('MetroRiel:' || v.destino_estacion_id) as punto_destino_sk,
    md5('MetroRiel') as modo_sk,
    md5('MetroRiel:SERVICIO_GENERAL') as servicio_sk,
    'MetroRiel'::text as fuente_evento,
    1::integer as cantidad_viajes,
    v.tarifa_quetzales,
    v.duracion_minutos
from {{ ref('silver_metroriel_viajes') }} v
join {{ ref('bridge_identidad_usuario') }} b
    on b.sistema_origen = 'MetroRiel' and b.llave_origen = v.tarjeta_mr
join {{ ref('silver_catalogo_puntos') }} origen
    on origen.modo = 'MetroRiel' and origen.codigo_punto = v.origen_estacion_id
join {{ ref('silver_catalogo_puntos') }} destino
    on destino.modo = 'MetroRiel' and destino.codigo_punto = v.destino_estacion_id
