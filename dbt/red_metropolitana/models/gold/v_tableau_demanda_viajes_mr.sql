{{ config(materialized='view') }}

-- Cada viaje cuenta una vez, en su ingreso y en la zona de ORIGEN.
select
    fecha, hora, es_dia_habil, es_hora_pico,
    case when es_hora_pico then 'Hora pico' else 'Fuera de pico' end as franja,
    modo,
    zona as zona_origen,
    cantidad_eventos as viajes_iniciados,
    tarifa_total_gtq
from {{ ref('mart_demanda_hora') }}
where tipo_evento = 'viaje'