-- depends_on: {{ ref('dim_usuario') }}
-- depends_on: {{ ref('fact_abordajes') }}
-- depends_on: {{ ref('fact_viajes_metroriel') }}
select table_name, column_name
from information_schema.columns
where table_schema = 'gold'
  and table_name in ('dim_usuario', 'fact_abordajes', 'fact_viajes_metroriel')
  and column_name in (
      'tarjeta', 'tarjeta_id', 'tarjeta_mr', 'id_tarjeta', 'llave_origen',
      'user_hash', 'usuario_canonico_id', 'num_tarjeta', 'card'
  )
