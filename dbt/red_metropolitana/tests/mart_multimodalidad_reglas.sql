select transbordo_sk
from {{ ref('mart_multimodalidad') }}
where modo_origen = modo_destino
   or tiempo_transferencia_minutos <= 0 or tiempo_transferencia_minutos > 90
   or momento_fin_transbordo <= momento_inicio_transbordo
   or momento_fin_transbordo - momento_inicio_transbordo > interval '90 minutes'
   or tiempo_transferencia_minutos != round(extract(epoch from
      (momento_fin_transbordo - momento_inicio_transbordo))::numeric / 60, 2)
   or transbordo_sk != md5(usuario_sk || ':' || bronze_record_id_origen || ':' || bronze_record_id_destino)
   or incluye_aerometro != (modo_origen = 'Aerometro' or modo_destino = 'Aerometro')
   or cantidad_transbordos != 1
