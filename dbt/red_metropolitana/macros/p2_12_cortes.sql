{% macro p2_12_cortes() -%}
    select 'A'::text as corte, timestamp '2026-07-01 00:00:00' as fecha_corte
    union all
    select 'B'::text, timestamp '2026-07-31 00:00:00'
{%- endmacro %}
