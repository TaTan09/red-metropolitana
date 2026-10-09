-- Zona con servicio y cero eventos, o sin servicio y con eventos.
select nombre_zona, tiene_servicio, eventos_totales
from {{ ref('mart_cobertura') }}
where inconsistencia_cobertura