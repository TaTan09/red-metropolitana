{{ config(materialized='table') }}

-- Cada evento CDC Transmetro genera una versión. seq define el orden inequívoco;
-- commit_ts conserva la fecha de negocio aun si dos eventos comparten timestamp.
with eventos as (
    select
        tarjeta::text as tarjeta_id,
        seq::bigint as seq,
        commit_ts::timestamp as commit_ts,
        upper(op::text) as operacion,
        nullif(perfil::text, '') as perfil,
        nullif(zona_residencia::text, '') as zona_residencia
    from {{ source('staging', 'cdc_registro_ambiguo') }}
    where tipo_llave = 'TRANSMETRO'
),
ordenados as (
    select e.*,
        max(seq) filter (where operacion in ('INSERT', 'UPDATE') and perfil is not null)
            over (partition by tarjeta_id order by seq rows between unbounded preceding and current row) as perfil_seq,
        max(seq) filter (where operacion in ('INSERT', 'UPDATE') and zona_residencia is not null)
            over (partition by tarjeta_id order by seq rows between unbounded preceding and current row) as zona_seq
    from eventos e
),
versiones as (
    select
        e.tarjeta_id,
        e.seq as valid_from_seq,
        lead(e.seq) over (partition by e.tarjeta_id order by e.seq) as valid_to_seq,
        e.commit_ts as valid_from,
        lead(e.commit_ts) over (partition by e.tarjeta_id order by e.seq) as valid_to,
        e.operacion,
        case when e.operacion = 'DELETE' then 'INACTIVA' else 'ACTIVA' end as estado_tarjeta,
        perfil_evento.perfil as perfil_usuario,
        zona_evento.zona_residencia as zona_residencia
    from ordenados e
    left join eventos perfil_evento on perfil_evento.tarjeta_id = e.tarjeta_id and perfil_evento.seq = e.perfil_seq
    left join eventos zona_evento on zona_evento.tarjeta_id = e.tarjeta_id and zona_evento.seq = e.zona_seq
)
select
    tarjeta_id || ':' || valid_from_seq::text as version_id,
    tarjeta_id,
    valid_from_seq,
    valid_to_seq,
    valid_from,
    valid_to,
    valid_to_seq is null as vigente,
    operacion,
    estado_tarjeta,
    perfil_usuario,
    zona_residencia
from versiones
