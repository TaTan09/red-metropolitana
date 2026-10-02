{{ config(materialized='table') }}

-- Universo oficial de áreas definido por el generador entregado por el docente.
-- Se usa para poder distinguir áreas con y sin servicio; los catálogos operacionales
-- solo contienen áreas efectivamente atendidas.
with universo(nombre_zona, tipo_area) as (
    values
        ('Zona 1', 'zona'),
        ('Zona 4', 'zona'),
        ('Zona 6', 'zona'),
        ('Zona 7', 'zona'),
        ('Zona 8', 'zona'),
        ('Zona 9', 'zona'),
        ('Zona 10', 'zona'),
        ('Zona 11', 'zona'),
        ('Zona 12', 'zona'),
        ('Zona 13', 'zona'),
        ('Zona 17', 'zona'),
        ('Zona 18', 'zona'),
        ('Mixco', 'municipio'),
        ('Villa Nueva', 'municipio'),
        ('San Miguel Petapa', 'municipio'),
        ('Santa Catarina Pinula', 'municipio')
),
cobertura as (
    select
        zona_conformada as nombre_zona,
        count(distinct modo)::integer as modos_con_servicio,
        count(*)::integer as puntos_transporte
    from {{ ref('silver_catalogo_puntos') }}
    group by zona_conformada
)
select
    u.nombre_zona,
    u.tipo_area,
    coalesce(c.modos_con_servicio, 0) as modos_con_servicio,
    coalesce(c.puntos_transporte, 0) as puntos_transporte,
    (coalesce(c.modos_con_servicio, 0) > 0) as tiene_servicio
from universo u
left join cobertura c using (nombre_zona)
