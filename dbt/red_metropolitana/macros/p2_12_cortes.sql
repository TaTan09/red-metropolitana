{% macro p2_12_cortes(incluir_c=false) -%}
    {% set cortes = var('p2_cortes', {'A': '2026-07-01', 'B': '2026-07-31', 'C': '2026-08-30'}) %}
    {% for nombre in (['A', 'B', 'C'] if incluir_c else ['A', 'B']) %}
    select '{{ nombre }}'::text as corte,
           '{{ cortes[nombre] | replace("'", "''") }}'::timestamp as fecha_corte
    {% if not loop.last %}union all{% endif %}
    {% endfor %}
{%- endmacro %}
