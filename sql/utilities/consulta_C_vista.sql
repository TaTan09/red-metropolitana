select modo, zona, hora, sum(cantidad_abordajes)
from gold.v_tableau_demanda_abordajes
group by modo, zona, hora;