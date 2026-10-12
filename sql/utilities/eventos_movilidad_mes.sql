-- Mes del máximo timestamp Gold real (hora local Guatemala); reproducible para
-- el mismo snapshot. Devuelve unidades separadas, no viajes puerta-a-puerta.
with limites as (
    select max(t.fecha_hora) as instante
    from gold.fact_abordajes f join gold.dim_tiempo t using (tiempo_sk)
    union all
    select max(t.fecha_hora)
    from gold.fact_viajes_metroriel f
    join gold.dim_tiempo t on t.tiempo_sk = f.tiempo_ingreso_sk
    union all
    select max(t.fecha_hora)
    from gold.fact_viajes_metroriel f
    join gold.dim_tiempo t on t.tiempo_sk = f.tiempo_salida_sk
), periodo as (
    select date_trunc('month', max(instante)) as inicio_mes from limites
), abordajes as (
    select count(*) as n
    from gold.fact_abordajes f join gold.dim_tiempo t using (tiempo_sk)
    cross join periodo p
    where t.fecha_hora >= p.inicio_mes and t.fecha_hora < p.inicio_mes + interval '1 month'
), viajes as (
    select count(*) as n
    from gold.fact_viajes_metroriel f
    join gold.dim_tiempo t on t.tiempo_sk = f.tiempo_ingreso_sk
    cross join periodo p
    where t.fecha_hora >= p.inicio_mes and t.fecha_hora < p.inicio_mes + interval '1 month'
)
select p.inicio_mes::date as mes, a.n as abordajes_mes_tm_tu_am,
       v.n as viajes_metroriel_mes, a.n + v.n as eventos_movilidad_mes
from periodo p cross join abordajes a cross join viajes v;
