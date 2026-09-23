{{ config(materialized='table') }}

-- 1. Transmetro: Duplicados de torniquete
with tm_duplicados as (
    select 
        'Transmetro' as fuente,
        bronze_record_id as id_registro_crudo,
        'DUPLICADO_TORNIQUETE' as motivo_rechazo,
        json_build_object(
            'tarjeta', tarjeta,
            'estacion_id', estacion_id,
            'fecha_hora', fecha_hora
        ) as payload,
        current_timestamp as fecha_deteccion
    from (
        select *,
               row_number() over(
                   partition by tarjeta, estacion_id, fecha_hora 
                   order by ingesta_timestamp, bronze_record_id
               ) as rn
        from {{ source('staging', 'transmetro_validaciones') }}
    ) t
    where rn > 1
),

-- 2. Transurbano: Código de parada nulo
tu_nulos as (
    select 
        'Transurbano' as fuente,
        bronze_record_id as id_registro_crudo,
        'COD_PARADA_NULO' as motivo_rechazo,
        json_build_object(
            'num_tarjeta', num_tarjeta,
            'ruta', ruta,
            'fecha', fecha,
            'hora', hora
        ) as payload,
        current_timestamp as fecha_deteccion
    from {{ source('staging', 'transurbano_transacciones') }}
    where cod_parada is null or trim(cod_parada::text) = ''
),

-- 3. Transurbano: Fecha Futura o Inválida
tu_futuro as (
    select 
        'Transurbano' as fuente,
        bronze_record_id as id_registro_crudo,
        'FECHA_FUTURA' as motivo_rechazo,
        json_build_object(
            'num_tarjeta', num_tarjeta,
            'fecha', fecha,
            'hora', hora
        ) as payload,
        current_timestamp as fecha_deteccion
    from (
        select *,
            case 
                when fecha ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' then to_date(fecha, 'DD/MM/YYYY')
                when fecha ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then to_date(fecha, 'YYYY-MM-DD')
                else null
            end as f_parsed
        from {{ source('staging', 'transurbano_transacciones') }}
    ) t
    where f_parsed is null or (f_parsed + hora::time)::timestamp > '2026-10-01 00:00:00'::timestamp
),

-- 4. MetroRiel: Viajes sin salida
mr_sin_salida as (
    select 
        'MetroRiel' as fuente,
        bronze_record_id as id_registro_crudo,
        'VIAJE_SIN_EXIT' as motivo_rechazo,
        json_build_object(
            'viaje_id', trip_id,
            'tarjeta_mr', card,
            'origen_estacion_id', entry_station
        ) as payload,
        current_timestamp as fecha_deteccion
    from {{ source('staging', 'metroriel_viajes') }}
    where exit_station is null or exit_ts is null
)

select * from tm_duplicados
union all
select * from tu_nulos
union all
select * from tu_futuro
union all
select * from mr_sin_salida
