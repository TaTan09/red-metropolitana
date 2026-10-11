select modo, zona, hora, sum(cantidad_eventos)
from gold.mart_demanda_hora
where tipo_evento = 'abordaje'
group by modo, zona, hora;