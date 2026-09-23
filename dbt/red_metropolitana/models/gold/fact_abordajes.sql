{{ config(materialized='table') }}

-- Grano: un evento Silver válido de acceso/abordaje TM, TU o AM.
with eventos as (
    select
        'Transmetro'::text as modo,
        bronze_record_id as evento_id,
        tarjeta_id as llave_origen,
        estacion_id as codigo_punto,
        fecha_hora,
        linea as servicio_codigo,
        tarifa_quetzales
    from {{ ref('silver_transmetro_validaciones') }}
    union all
    select
        'Transurbano', bronze_record_id, id_tarjeta, cod_parada,
        fecha_hora, ruta, tarifa_quetzales
    from {{ ref('silver_transurbano_transacciones') }}
    union all
    select
        'Aerometro', bronze_record_id, user_hash, station_code,
        fecha_hora, eje, tarifa_quetzales
    from {{ ref('silver_aerometro_boardings') }}
)
select
    md5(e.modo || ':' || e.evento_id) as abordaje_sk,
    {{ usuario_sk('b.usuario_canonico_id') }} as usuario_sk,
    to_char(e.fecha_hora, 'YYYYMMDDHH24MISS')::bigint as tiempo_sk,
    md5(p.zona_conformada) as zona_sk,
    md5(e.modo || ':' || e.codigo_punto) as punto_sk,
    md5(e.modo) as modo_sk,
    md5(e.modo || ':' || coalesce(nullif(e.servicio_codigo, ''), 'SIN_SERVICIO')) as servicio_sk,
    e.modo as fuente_evento,
    1::integer as cantidad_abordajes,
    e.tarifa_quetzales
from eventos e
join {{ ref('bridge_identidad_usuario') }} b
    on b.sistema_origen = e.modo and b.llave_origen = e.llave_origen
join {{ ref('silver_catalogo_puntos') }} p
    on p.modo = e.modo and p.codigo_punto = e.codigo_punto
