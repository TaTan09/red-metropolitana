{% macro normalizar_zona(columna_zona) %}
    case 
        when {{ columna_zona }} is null or trim({{ columna_zona }}) = '' then 'Desconocida'
        when lower({{ columna_zona }}) ~ 'district' then 
            'Zona ' || regexp_replace({{ columna_zona }}, '[^0-9]', '', 'g')
        when upper({{ columna_zona }}) ~ '^Z[0-9]+' then 
            'Zona ' || regexp_replace({{ columna_zona }}, '[^0-9]', '', 'g')
        when lower({{ columna_zona }}) ~ '^zona' then 
            'Zona ' || regexp_replace({{ columna_zona }}, '[^0-9]', '', 'g')
        else 'Zona ' || regexp_replace({{ columna_zona }}, '[^0-9]', '', 'g')
    end
{% endmacro %}