with esperado as (
    select modos_observados, metodo_identidad, count(*) as usuarios,
           sum(count(*)) over ()::bigint as total_usuarios_observados,
           sum(case when modos_observados > 1 then count(*) else 0 end) over ()::bigint as usuarios_multimodales_total,
           sum(case when modos_observados = 1 then count(*) else 0 end) over ()::bigint as usuarios_unimodales_total,
           round(100.0 * sum(case when modos_observados > 1 then count(*) else 0 end) over ()
                 / nullif(sum(count(*)) over (), 0), 2) as pct_usuarios_multimodales
    from {{ ref('dim_usuario') }} group by modos_observados, metodo_identidad
), diferencias as (
    (select * from esperado except all select * from {{ ref('v_tableau_multimodalidad') }})
    union all
    (select * from {{ ref('v_tableau_multimodalidad') }} except all select * from esperado)
)
select * from diferencias
union all
select * from {{ ref('v_tableau_multimodalidad') }}
where usuarios_unimodales_total + usuarios_multimodales_total != total_usuarios_observados
   or modos_observados < 1 or modos_observados > 4
