{% macro normalizar_zona(columna_zona) %}
    case
        when {{ columna_zona }} is null or trim({{ columna_zona }}) = '' then 'Desconocida'
        when upper(trim({{ columna_zona }})) ~ '^Z[0-9]+$' then
            'Zona ' || regexp_replace(trim({{ columna_zona }}), '[^0-9]', '', 'g')
        when lower(trim({{ columna_zona }})) ~ '^zona[[:space:]]*[0-9]+$' then
            'Zona ' || regexp_replace(trim({{ columna_zona }}), '[^0-9]', '', 'g')
        when lower(trim({{ columna_zona }})) ~ '^district[[:space:]]*[0-9]+$' then
            'Zona ' || regexp_replace(trim({{ columna_zona }}), '[^0-9]', '', 'g')
        else initcap(trim({{ columna_zona }}))
    end
{% endmacro %}
