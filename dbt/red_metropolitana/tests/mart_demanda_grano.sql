select fecha, hora, modo, zona, count(*) as filas
from {{ ref('mart_demanda_hora') }}
group by fecha, hora, modo, zona
having count(*) > 1