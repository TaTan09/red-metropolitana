-- El estado vigente de cada tarjeta debe coincidir con el padrón reconstruido.
with vigente as (
    select * from {{ ref('silver_padron_transmetro_scd2') }} where vigente
),
actual as (
    select * from {{ source('staging', 'padron_transmetro_actual') }}
)
select coalesce(v.tarjeta_id, a.tarjeta) as tarjeta
from vigente v
full outer join actual a on v.tarjeta_id = a.tarjeta
where v.tarjeta_id is null or a.tarjeta is null
   or v.estado_tarjeta is distinct from a.estado
   or v.perfil_usuario is distinct from a.perfil
   or v.zona_residencia is distinct from a.zona_residencia
   or v.valid_from_seq is distinct from a.ultima_seq
