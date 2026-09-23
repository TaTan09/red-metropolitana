with esperado as (
    select
        (select count(*) from {{ ref('silver_transmetro_validaciones') }})
        + (select count(*) from {{ ref('silver_transurbano_transacciones') }})
        + (select count(*) from {{ ref('silver_aerometro_boardings') }}) as abordajes,
        (select count(*) from {{ ref('silver_metroriel_viajes') }}) as viajes
),
obtenido as (
    select
        (select count(*) from {{ ref('fact_abordajes') }}) as abordajes,
        (select count(*) from {{ ref('fact_viajes_metroriel') }}) as viajes
)
select * from esperado e cross join obtenido o
where e.abordajes <> o.abordajes or e.viajes <> o.viajes
