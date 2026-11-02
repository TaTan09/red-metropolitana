{{ config(materialized='table', tags=['p2_12']) }}

-- Métrica descriptiva posterior a la etiqueta. Nunca alimenta la población.
-- No es una corrección de etiqueta ni un enlace personal verificado.
with cortes as (
    {{ p2_12_cortes() }}
), actividad_futura as (
    select distinct c.corte, u.operador, u.llave_operacional
    from cortes c
    join {{ ref('silver_p2_usos_tarjeta') }} u
      on u.fecha_uso >= c.fecha_corte
     and u.fecha_uso < c.fecha_corte + interval '30 days'
     and u.disponible_desde < c.fecha_corte + interval '30 days'
), positivos_con_otra_actividad as (
    select distinct p.corte, p.unidad_id
    from {{ ref('silver_p2_poblacion_tarjeta') }} p
    join {{ ref('bridge_identidad_usuario') }} origen
      on origen.sistema_origen = p.operador and origen.llave_origen = p.llave_operacional
    join {{ ref('bridge_identidad_usuario') }} otro
      on otro.usuario_canonico_id = origen.usuario_canonico_id
     and otro.sistema_origen <> origen.sistema_origen
    join actividad_futura a
      on a.corte = p.corte and a.operador = otro.sistema_origen
     and a.llave_operacional = otro.llave_origen
    where p.etiqueta = 1
      and origen.metodo_match = 'PATRON_NUMERICO_INFERIDO'
      and otro.metodo_match = 'PATRON_NUMERICO_INFERIDO'
      and origen.usuario_canonico_id like 'USR-%'
      -- AM es HASH_AISLADO en P1; no inventar correspondencia cruzada.
      and origen.sistema_origen <> 'Aerometro' and otro.sistema_origen <> 'Aerometro'
)
select c.corte, c.fecha_corte,
       count(p.unidad_id) as poblacion,
       count(*) filter (where p.etiqueta = 1) as positivos,
       round(1.0 * count(*) filter (where p.etiqueta = 1)
             / nullif(count(p.unidad_id), 0), 8) as tasa_positiva,
       count(otra.unidad_id) as positivos_con_actividad_otro_operador,
       round(1.0 * count(otra.unidad_id)
             / nullif(count(*) filter (where p.etiqueta = 1), 0), 8) as proporcion_costo,
       count(*) filter (where p.etiqueta = 1 and p.operador = 'Aerometro') as positivos_aerometro
from cortes c
left join {{ ref('silver_p2_poblacion_tarjeta') }} p on p.corte = c.corte
left join positivos_con_otra_actividad otra on otra.corte = p.corte and otra.unidad_id = p.unidad_id
group by c.corte, c.fecha_corte
