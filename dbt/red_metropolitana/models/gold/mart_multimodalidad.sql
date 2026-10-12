{{ config(materialized='table') }}

-- Transbordos inferidos, no confirmados físicamente: eventos consecutivos de
-- una identidad inferida en modos distintos, separados por >0 y <=90 minutos.
-- Aerómetro tiene identidad aislada y no permite medir enlaces con otros modos.

with eventos_unificados as (
    -- 1. Abordajes: Transmetro, Transurbano, Aerometro
    select
        fa.usuario_sk,
        fa.modo_sk,
        dm.nombre_modo as modo,
        dz.nombre_zona as zona,
        dt.fecha_hora,
        fa.tarifa_quetzales,
        fa.bronze_record_id
    from {{ ref('fact_abordajes') }} fa
    inner join {{ ref('dim_modo') }} dm on fa.modo_sk = dm.modo_sk
    inner join {{ ref('dim_zona') }} dz on fa.zona_sk = dz.zona_sk
    inner join {{ ref('dim_tiempo') }} dt on fa.tiempo_sk = dt.tiempo_sk

    union all

    -- 2. Viajes: MetroRiel (se toma el evento de ingreso para la secuencia del viaje)
    select
        fvm.usuario_sk,
        fvm.modo_sk,
        'MetroRiel' as modo,
        dz.nombre_zona as zona,
        dt.fecha_hora,
        fvm.tarifa_quetzales,
        fvm.bronze_record_id
    from {{ ref('fact_viajes_metroriel') }} fvm
    inner join {{ ref('dim_zona') }} dz on fvm.zona_origen_sk = dz.zona_sk
    inner join {{ ref('dim_tiempo') }} dt on fvm.tiempo_ingreso_sk = dt.tiempo_sk
),

secuencia_eventos as (
    select
        usuario_sk,
        modo,
        zona,
        fecha_hora,
        tarifa_quetzales,
        bronze_record_id,
        lag(modo) over (
            partition by usuario_sk
            order by fecha_hora, modo, bronze_record_id
        ) as modo_anterior,
        lag(zona) over (
            partition by usuario_sk
            order by fecha_hora, modo, bronze_record_id
        ) as zona_anterior,
        lag(fecha_hora) over (
            partition by usuario_sk
            order by fecha_hora, modo, bronze_record_id
        ) as fecha_hora_anterior,
        lag(tarifa_quetzales) over (
            partition by usuario_sk
            order by fecha_hora, modo, bronze_record_id
        ) as tarifa_anterior,
        lag(bronze_record_id) over (
            partition by usuario_sk
            order by fecha_hora, modo, bronze_record_id
        ) as bronze_record_id_anterior
    from eventos_unificados
),

transbordos_detectados as (
    select
        md5(
            usuario_sk || ':' ||
            bronze_record_id_anterior || ':' || bronze_record_id
        ) as transbordo_sk,
        usuario_sk,
        bronze_record_id_anterior as bronze_record_id_origen,
        bronze_record_id as bronze_record_id_destino,
        fecha_hora_anterior as momento_inicio_transbordo,
        fecha_hora as momento_fin_transbordo,
        modo_anterior as modo_origen,
        modo as modo_destino,
        (modo_anterior || ' -> ' || modo) as combinacion_modos,
        zona_anterior as zona_origen,
        zona as zona_destino,
        extract(epoch from (fecha_hora - fecha_hora_anterior)) / 60.0 as tiempo_transferencia_minutos,
        (tarifa_anterior + tarifa_quetzales) as tarifa_acumulada_gtq,
        case
            when modo_anterior = 'Aerometro' or modo = 'Aerometro' then true
            else false
        end as incluye_aerometro,
        fecha_hora_anterior::date as fecha_transbordo,
        extract(hour from fecha_hora_anterior)::integer as hora_transbordo
    from secuencia_eventos
    where modo_anterior is not null
      and modo != modo_anterior
      -- Ventana única: estrictamente más de 0 y hasta 90 minutos inclusive.
      and fecha_hora > fecha_hora_anterior
      and (fecha_hora - fecha_hora_anterior) <= interval '90 minutes'
)

select
    transbordo_sk,
    usuario_sk,
    bronze_record_id_origen,
    bronze_record_id_destino,
    fecha_transbordo,
    hora_transbordo,
    momento_inicio_transbordo,
    momento_fin_transbordo,
    modo_origen,
    modo_destino,
    combinacion_modos,
    zona_origen,
    zona_destino,
    round(tiempo_transferencia_minutos::numeric, 2) as tiempo_transferencia_minutos,
    tarifa_acumulada_gtq,
    incluye_aerometro,
    1 as cantidad_transbordos
from transbordos_detectados
