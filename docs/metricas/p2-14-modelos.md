# Requisito 1.4 — Baselines y Regresión Logística Regularizada

## 1. Métrica Elegida y Justificación
Se seleccionó **ROC-AUC** como métrica principal de validación cruzada. El problema presenta un desbalance de clases (tasa positiva de abandono en Corte A: 14.4824%). ROC-AUC evalúa la capacidad global del modelo para ordenar a los usuarios por riesgo antes de fijar un umbral de corte operativo, siendo independiente de la probabilidad arbitraria de corte y permitiendo comparar directamente los baselines probabilísticos y heurísticos con los modelos entrenados.

## 2. Comparación de Modelos (CV 5 Folds Estratificados en Corte A)
Todos los modelos fueron evaluados con los mismos 5 folds estratificados (`random_state=2026`) sobre las 77,411 filas del Corte A, aplicando el escalado y preprocesamiento dentro de cada pliegue.

| Modelo | Penalización | Hiperparámetro | ROC-AUC Medio | Desviación Estándar |
|---|---|---|---:|---:|
| Baseline 1 (Tasa constante) | Ninguna | p = 0.1448 | 0.5000 | 0.0000 |
| Baseline 2 (Feature única) | Ninguna | dias_desde_ultimo_uso | 0.7954 | 0.0025 |
| Regresión Logística L1 | L1 (Lasso) | C = 0.100 (lambda = 10.0) | 0.8069 | 0.0021 |
| Regresión Logística L2 | L2 (Ridge) | C = 0.010 (lambda = 100.0) | **0.8071** | **0.0020** |

*Modelo seleccionado:* Regresión Logística L2 con $C = 0.01$ ($\lambda = 100.0$), que presentó la mayor capacidad discriminativa y estabilidad entre pliegues.

## 3. Curva de Métrica vs. Lambda
La gráfica de barrido de regularización fue guardada en `docs/evidencias/p2-14-lambda-vs-auc.png`. Se observa que castigos moderados a fuertes ($\lambda \in [10, 100]$) estabilizan los coeficientes de variables correlacionadas (como las ventanas de viajes y actividad), evitando el sobreajuste.

## 4. Interpretación de Coeficientes
Entrenando con la totalidad del Corte A utilizando la regularización seleccionada ($L_2, C=0.01$), los coeficientes que más empujan hacia el abandono (positivos) y retención son:

1. **`dias_desde_ultimo_uso` (+0.6391):** Es el predictor principal de abandono. A mayor cantidad de días transcurridos desde el último uso respecto a la fecha de corte, mayor es la probabilidad de que la tarjeta cese su actividad en los siguientes 30 días.
2. **`viajes_28d` (+0.3018):** Al estar regularizado junto con las variables de recencia y actividad global, actúa controlando la intensidad de uso condicionada al lapso de inactividad reciente.
3. **`proporcion_fin_semana` (+0.0542):** Un mayor porcentaje de uso en sábado/domingo se asocia a usuarios no cautivos (ocio/esporádicos), quienes presentan mayor volatilidad y riesgo de abandono que los pasajeros laborales recurrentes.
4. **`gasto_28d_gtq` (+0.0314):** Representa el volumen monetario transaccionado; usuarios con perfiles de consumo específicos reflejan variaciones en la persistencia del servicio.
5. **`proporcion_hora_pico` (-0.0055):** Coeficiente protector (negativo). Viajar en horas de mayor congestión matutina y vespertina refleja un patrón de movilidad laboral/escolar forzosa, lo que disminuye el riesgo de abandonar la red.

## 5. Insumos para Fase 2
Las predicciones fuera de pliegue (Out-Of-Fold) quedaron almacenadas en `datos_red/p2-14-oof-predicciones-a.csv` para la derivación del umbral óptimo y matriz de costos en la sección 2.2.
