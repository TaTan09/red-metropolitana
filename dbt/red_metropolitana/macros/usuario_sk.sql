{% macro usuario_sk(canonical_expr) -%}
    encode(
        hmac(
            convert_to(({{ canonical_expr }})::text, 'UTF8'),
            convert_to('{{ env_var("GOLD_PSEUDONYM_KEY") | replace("'", "''") }}', 'UTF8'),
            'sha256'
        ),
        'hex'
    )
{%- endmacro %}
