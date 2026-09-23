-- Este es el entregable de conteos por regla que pide 1.3
{{ config(materialized='table') }}

with reglas as (
    select fuente, motivo_rechazo, count(*) as total_violaciones
    from {{ ref('silver_cuarentena') }}
    group by fuente, motivo_rechazo
),
unicos as (
    select fuente, count(distinct id_registro_crudo) as registros_unicos_fuente
    from {{ ref('silver_cuarentena') }}
    group by fuente
)
select
    r.fuente,
    r.motivo_rechazo,
    r.total_violaciones,
    u.registros_unicos_fuente,
    round(100.0 * r.total_violaciones / sum(r.total_violaciones) over (partition by r.fuente), 3) as porcentaje_dentro_fuente
from reglas r
join unicos u on r.fuente = u.fuente
