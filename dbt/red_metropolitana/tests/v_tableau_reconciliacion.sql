with v as (
    select
        (select coalesce(sum(cantidad_abordajes), 0) from {{ ref('v_tableau_demanda_abordajes') }}) as ab,
        (select coalesce(sum(viajes_iniciados), 0)   from {{ ref('v_tableau_demanda_viajes_mr') }}) as vi,
        (select coalesce(sum(abordajes), 0)          from {{ ref('v_tableau_cobertura') }}) as ab_cob,
        (select coalesce(sum(viajes_mr_iniciados), 0) from {{ ref('v_tableau_cobertura') }}) as vi_cob
),
f as (
    select
        (select count(*) from {{ ref('fact_abordajes') }}) as ab,
        (select count(*) from {{ ref('fact_viajes_metroriel') }}) as vi
)
select v.*, f.ab as ab_esperado, f.vi as vi_esperado
from v cross join f
where v.ab <> f.ab or v.ab_cob <> f.ab
   or v.vi <> f.vi or v.vi_cob <> f.vi