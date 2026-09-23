-- Una versión por evento CDC y sin solapamiento de secuencias.
select tarjeta_id, valid_from_seq
from {{ ref('silver_padron_transmetro_scd2') }}
group by tarjeta_id, valid_from_seq
having count(*) <> 1
union all
select tarjeta_id, valid_from_seq
from {{ ref('silver_padron_transmetro_scd2') }}
where valid_to_seq <= valid_from_seq
union all
select coalesce(s.tarjeta_id, c.tarjeta) as tarjeta_id,
       coalesce(s.valid_from_seq, c.seq::bigint) as valid_from_seq
from {{ ref('silver_padron_transmetro_scd2') }} s
full outer join {{ source('staging', 'cdc_registro_ambiguo') }} c
  on c.tipo_llave = 'TRANSMETRO' and s.tarjeta_id = c.tarjeta and s.valid_from_seq = c.seq::bigint
where (c.tipo_llave = 'TRANSMETRO' and s.tarjeta_id is null)
   or (s.tarjeta_id is not null and c.tarjeta is null)
