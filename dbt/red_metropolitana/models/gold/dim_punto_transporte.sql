{{ config(materialized='table') }}

select
    md5(modo || ':' || codigo_punto) as punto_sk,
    md5(modo) as modo_sk,
    md5(zona_conformada) as zona_sk,
    codigo_punto,
    nombre_punto,
    modo,
    zona_conformada,
    servicio_codigo,
    latitud,
    longitud
from {{ ref('silver_catalogo_puntos') }}
