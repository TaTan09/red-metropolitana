{{ config(materialized='table') }}

select
    md5(nombre_zona) as zona_sk,
    nombre_zona,
    tipo_area,
    modos_con_servicio,
    puntos_transporte,
    tiene_servicio
from {{ ref('silver_universo_zonas') }}
