{{ config(materialized='table') }}

-- Un punto natural por operador; las zonas se conforman aquí, antes de Gold.
select
    'Transmetro'::text as modo,
    estacion_id::text as codigo_punto,
    nombre::text as nombre_punto,
    {{ normalizar_zona('zona') }}::text as zona_conformada,
    linea::text as servicio_codigo,
    nullif(lat::text, '')::numeric as latitud,
    nullif(lon::text, '')::numeric as longitud
from {{ source('staging', 'tm_estaciones') }}

union all

select
    'Transurbano',
    cod_parada::text,
    descripcion::text,
    {{ normalizar_zona('sector') }}::text,
    ruta::text,
    null::numeric,
    null::numeric
from {{ source('staging', 'tu_paradas') }}

union all

select
    'MetroRiel',
    id_estacion::text,
    nombre_estacion::text,
    {{ normalizar_zona('zona_nombre') }}::text,
    'SERVICIO_GENERAL'::text,
    null::numeric,
    null::numeric
from {{ source('staging', 'mr_estaciones') }}

union all

select
    'Aerometro',
    station_code::text,
    station_name::text,
    {{ normalizar_zona('district') }}::text,
    axis::text,
    null::numeric,
    null::numeric
from {{ source('staging', 'am_estaciones') }}
