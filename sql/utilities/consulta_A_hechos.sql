select m.nombre_modo, z.nombre_zona, t.hora, sum(f.cantidad_abordajes)
from gold.fact_abordajes f
join gold.dim_tiempo t on t.tiempo_sk = f.tiempo_sk
join gold.dim_zona z on z.zona_sk = f.zona_sk
join gold.dim_modo m on m.modo_sk = f.modo_sk
group by m.nombre_modo, z.nombre_zona, t.hora;