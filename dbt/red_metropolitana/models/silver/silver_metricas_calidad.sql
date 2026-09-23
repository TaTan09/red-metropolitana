-- Este es el entregable de conteos por regla que pide 1.3
{{ config(materialized='table') }}

select 
    fuente,
    motivo_rechazo,
    count(*) as total_registros,
    round((count(*)::numeric / sum(count(*)) over(partition by fuente)) * 100, 3) as porcentaje_dentro_fuente
from {{ ref('silver_cuarentena') }}
group by fuente, motivo_rechazo
order by fuente, total_registros desc
