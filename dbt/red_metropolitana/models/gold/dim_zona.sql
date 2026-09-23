{{ config(materialized='table') }}

select distinct
    md5(zona_conformada) as zona_sk,
    zona_conformada as nombre_zona
from {{ ref('silver_catalogo_puntos') }}
