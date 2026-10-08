(select distinct on (fuente_evento) fuente_evento, bronze_record_id
 from gold.fact_abordajes
 order by fuente_evento, bronze_record_id)
union all
(select 'MetroRiel', min(bronze_record_id) from gold.fact_viajes_metroriel);