select usuario_canonico_id
from {{ ref('silver_features_usuario') }}
where total_eventos <= 0 or modos_utilizados not between 1 and 4
   or es_multimodal != (modos_utilizados > 1)
   or usa_aerometro != (eventos_aerometro > 0)
   or total_eventos != eventos_transmetro + eventos_transurbano + eventos_aerometro + eventos_metroriel
   or eventos_ultimos_7_dias < 0
   or eventos_ultimos_7_dias > eventos_ultimos_30_dias
   or eventos_ultimos_30_dias > eventos_ultimos_90_dias
   or eventos_ultimos_90_dias > total_eventos
   or proporcion_eventos_hora_pico not between 0 and 1
   or primer_evento > ultimo_evento or ultimo_evento > fecha_corte
   or dias_desde_ultimo_evento != floor(extract(epoch from (fecha_corte - ultimo_evento)) / 86400)
   or span_dias_uso != floor(extract(epoch from (ultimo_evento - primer_evento)) / 86400)
   or (metodo_match = 'HASH_AISLADO' and (modos_utilizados != 1 or not usa_aerometro))
