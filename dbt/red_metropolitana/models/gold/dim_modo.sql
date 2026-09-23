{{ config(materialized='table') }}

select distinct
    md5(modo) as modo_sk,
    modo as nombre_modo
from {{ ref('silver_catalogo_puntos') }}
