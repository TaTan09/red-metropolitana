{{ config(materialized='table') }}

with universo_llaves as (
    select distinct tarjeta_id as llave_origen, 'Transmetro' as operador from {{ ref('silver_transmetro_validaciones') }}
    union
    select distinct id_tarjeta as llave_origen, 'Transurbano' as operador from {{ ref('silver_transurbano_transacciones') }}
    union
    select distinct tarjeta_mr as llave_origen, 'MetroRiel' as operador from {{ ref('silver_metroriel_viajes') }}
    union
    select distinct user_hash as llave_origen, 'Aerometro' as operador from {{ ref('silver_aerometro_boardings') }}
)

select 
    case 
        when operador = 'Aerometro' then 'AM-' || llave_origen
        when operador = 'Transmetro' and llave_origen ~ '^TC-[0-9]+' then 
            'USR-' || lpad(regexp_replace(llave_origen, '[^0-9]', '', 'g'), 8, '0')
        when operador = 'Transurbano' and llave_origen ~ '^[0-9]+' then 
            'USR-' || lpad(ltrim(llave_origen, '0'), 8, '0')
        when operador = 'MetroRiel' and llave_origen ~ '^MR[0-9]+' then 
            'USR-' || lpad(regexp_replace(llave_origen, '[^0-9]', '', 'g'), 8, '0')
        else 'SIN-TARJETA-' || md5(llave_origen)
    end as usuario_canonico_id,
    operador as sistema_origen,
    llave_origen,
    case 
        when operador = 'Aerometro' then 'HASH_AISLADO'
        else 'PATRON_NUMERICO_INFERIDO'
    end as metodo_match,
    case 
        when operador = 'Aerometro' then 'ALTO_LOCAL'
        else 'INFERENCIA_ACADEMICA_MEDIA'
    end as nivel_confianza,
    current_date as fecha_proceso
from universo_llaves