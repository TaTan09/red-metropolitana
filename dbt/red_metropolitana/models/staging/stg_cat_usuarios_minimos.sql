{{ config(materialized='table') }}

with tu_keys as (
    select distinct 
        num_tarjeta::text as llave_origen,
        'Transurbano' as sistema_origen
    from {{ source('bronze', 'transurbano_transacciones') }}
    where num_tarjeta is not null and trim(num_tarjeta::text) != ''
),

mr_keys as (
    select distinct 
        tarjeta_mr::text as llave_origen,
        'MetroRiel' as sistema_origen
    from {{ source('bronze', 'metroriel_viajes') }}
    where tarjeta_mr is not null and trim(tarjeta_mr::text) != ''
),

am_keys as (
    select distinct 
        user_hash::text as llave_origen,
        'Aerometro' as sistema_origen
    from {{ source('bronze', 'aerometro_boardings') }}
    where user_hash is not null and trim(user_hash::text) != ''
)

select * from tu_keys
union all
select * from mr_keys
union all
select * from am_keys