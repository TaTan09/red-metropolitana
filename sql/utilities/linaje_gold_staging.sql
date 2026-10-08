select f.bronze_record_id, s.fecha, s.hora, s.cod_parada, s.ruta, s.monto_centavos
from gold.fact_abordajes f
join staging.transurbano_transacciones s
  on s.bronze_record_id = f.bronze_record_id
where f.fuente_evento = 'Transurbano'
order by f.bronze_record_id
limit 1;