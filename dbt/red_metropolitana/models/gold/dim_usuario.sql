{{ config(materialized='table') }}

with identidades as (
    select
        {{ usuario_sk('usuario_canonico_id') }} as usuario_sk,
        sistema_origen,
        metodo_match
    from {{ ref('bridge_identidad_usuario') }}
)
select
    usuario_sk,
    count(distinct sistema_origen)::integer as modos_observados,
    case
        when bool_or(metodo_match = 'HASH_AISLADO') then 'HASH_AISLADO'
        else 'PATRON_NUMERICO_INFERIDO'
    end as metodo_identidad
from identidades
group by usuario_sk
