{{ config(materialized='view') }}

-- Identidades observadas, no personas confirmadas. Aerómetro permanece aislado:
-- no es medible su multimodalidad persona-a-persona con TM/TU/MR.
with distribucion as (
    select modos_observados, metodo_identidad, count(*) as usuarios
    from {{ ref('dim_usuario') }}
    group by modos_observados, metodo_identidad
)
select modos_observados, metodo_identidad, usuarios,
       sum(usuarios) over ()::bigint as total_usuarios_observados,
       sum(case when modos_observados > 1 then usuarios else 0 end) over ()::bigint as usuarios_multimodales_total,
       sum(case when modos_observados = 1 then usuarios else 0 end) over ()::bigint as usuarios_unimodales_total,
       round(100.0 * sum(case when modos_observados > 1 then usuarios else 0 end) over ()
             / nullif(sum(usuarios) over (), 0), 2) as pct_usuarios_multimodales
from distribucion
