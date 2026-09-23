{{ config(materialized='table') }}

with parsed_dates as (
    select
        t.num_tarjeta::text as id_tarjeta,
        case 
            when t.fecha ~ '^[0-9]{2}/[0-9]{2}/[0-9]{4}$' then to_date(t.fecha, 'DD/MM/YYYY')
            when t.fecha ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' then to_date(t.fecha, 'YYYY-MM-DD')
            else null
        end as fecha_valida,
        t.fecha as fecha_raw,
        t.hora as hora_raw,
        t.cod_parada::text as cod_parada,
        t.ruta::text as ruta,
        (t.monto_centavos::numeric / 100.0) as tarifa_quetzales,
        t.ingesta_timestamp,
        p.sector as zona_cruda
    from {{ source('staging', 'transurbano_transacciones') }} t
    left join {{ source('staging', 'tu_paradas') }} p on t.cod_parada = p.cod_parada
),

transurbano_base as (
    select
        ('TU-' || row_number() over(order by fecha_valida, hora_raw, id_tarjeta))::text as id_transaccion,
        id_tarjeta,
        (fecha_valida + hora_raw::time)::timestamp as fecha_hora,
        cod_parada,
        ruta,
        tarifa_quetzales,
        ingesta_timestamp,
        zona_cruda
    from parsed_dates
    where fecha_valida is not null
)

select
    id_transaccion,
    id_tarjeta,
    fecha_hora,
    cod_parada,
    ruta,
    {{ normalizar_zona('zona_cruda') }} as zona_conformada,
    tarifa_quetzales,
    ingesta_timestamp
from transurbano_base
where cod_parada is not null 
  and trim(cod_parada) != ''
  and fecha_hora <= '2026-10-01 00:00:00'::timestamp