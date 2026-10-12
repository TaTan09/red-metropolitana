-- depends_on: {{ ref('v_tableau_multimodalidad') }}
select column_name
from information_schema.columns
where table_schema = 'gold' and table_name = 'v_tableau_multimodalidad'
  and column_name in ('usuario_sk', 'usuario_canonico_id', 'llave_origen',
      'tarjeta', 'tarjeta_id', 'id_tarjeta', 'tarjeta_mr', 'num_tarjeta', 'card', 'user_hash')
