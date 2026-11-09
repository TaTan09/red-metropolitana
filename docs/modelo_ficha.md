# Ficha Técnica del Modelo de Predicción de Abandono (MLOps)

## 1. Información General
* **Nombre del Modelo:** Regresión Logística Regularizada ($L_2$) para Predicción de Abandono.
* **Versión:** `v1_logistica_l2`
* **Artefacto Serializado:** `models/modelo_abandono_v1.joblib`
* **Responsable:** Alejandro

## 2. Definición del Problema y Datos
* **Dominio:** Clasificación binaria para predecir el cese de actividad (*churn*) en tarjetas de la Red Metropolitana de Transporte en un horizonte de 30 días.
* **Entrenamiento:** Ajustado con la totalidad de los datos del **Corte A** (77,411 registros).
* **Variables de Entrada (Features):** 
  * Numéricas: `viajes_28d`, `viajes_7d`, `viajes_14d`, `dias_activos_28d`, `dias_desde_ultimo_uso`, `gasto_28d_gtq`, `tarifa_media_gtq`, `puntos_origen_28d`, `proporcion_hora_pico`, `proporcion_fin_semana`.
  * Categóricas: `operador`.

## 3. Rendimiento y Validación Cruzada
* **Estrategia:** Validación cruzada estratificada de 5 pliegues (*Stratified 5-Fold CV*) con semilla fija (`random_state=2026`).
* **Métrica Principal:** ROC-AUC.
* **Resultado Obtenido:** ROC-AUC medio de **$0.8071 \pm 0.0020$** utilizando penalización Ridge ($L_2$) con $C = 0.01$ ($\lambda = 100.0$).

## 4. Inferencia y Producción (Corte C)
* **Script de Producción:** `predecir.py`
* **Umbral de Decisión Óptimo:** `0.311192` (derivado de la optimización de ganancia y costos de la campaña en la Fase 2.2).
* **Resultado en Corte C:** Se procesaron 76,420 registros, generando las probabilidades de abandono y marcando a **9,273 usuarios** para contacto preventivo de retención.
* **Archivo Generado:** `datos_red/p2-24-predicciones-c.csv`

## 5. Reproducibilidad
* Todas las transformaciones (escalado estándar y codificación one-hot) se encuentran encapsuladas dentro del `Pipeline` de scikit-learn serializado en `joblib`, evitando cualquier fuga de datos y garantizando inferencias idénticas ante futuras ejecuciones.
