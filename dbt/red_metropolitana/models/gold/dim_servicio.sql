{{ config(materialized='table') }}

with servicios as (
    select distinct 'Transmetro'::text as modo,
        coalesce(nullif(linea::text, ''), 'SIN_SERVICIO') as codigo,
        'Línea'::text as tipo
    from {{ ref('silver_transmetro_validaciones') }}
    union
    select distinct 'Transurbano', coalesce(nullif(ruta::text, ''), 'SIN_SERVICIO'), 'Ruta'
    from {{ ref('silver_transurbano_transacciones') }}
    union
    select distinct 'Aerometro', coalesce(nullif(eje::text, ''), 'SIN_SERVICIO'), 'Eje'
    from {{ ref('silver_aerometro_boardings') }}
    union
    select 'MetroRiel', 'SERVICIO_GENERAL', 'Servicio'
    from {{ ref('silver_metroriel_viajes') }}
)
select
    md5(modo || ':' || codigo) as servicio_sk,
    md5(modo) as modo_sk,
    modo,
    codigo as codigo_servicio,
    tipo as tipo_servicio
from servicios
