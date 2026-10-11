{{ config(materialized='view') }}

select
    fecha, hora, es_dia_habil, es_hora_pico,
    case when es_hora_pico then 'Hora pico' else 'Fuera de pico' end as franja,
    modo, zona,
    cantidad_eventos as cantidad_abordajes,
    tarifa_total_gtq
from {{ ref('mart_demanda_hora') }}
where tipo_evento = 'abordaje'