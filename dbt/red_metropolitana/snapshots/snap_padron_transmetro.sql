{% snapshot snap_padron_transmetro %}

{{
    config(
        target_schema='silver',
        unique_key='tarjeta_id',
        strategy='check',
        check_cols=['estado_tarjeta', 'perfil_usuario', 'zona_residencia'],
        invalidate_hard_deletes=True
    )
}}

select 
    tarjeta::text as tarjeta_id,
    perfil::text as perfil_usuario,
    zona_residencia::text as zona_residencia,
    estado::text as estado_tarjeta,
    ultima_seq,
    ultimo_commit_ts::timestamp as fecha_modificacion,
    ultima_operacion,
    current_timestamp as ingesta_timestamp
from {{ source('staging', 'padron_transmetro_actual') }}

{% endsnapshot %}