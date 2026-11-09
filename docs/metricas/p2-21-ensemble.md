# Proyecto 2 · 2.1 Ensemble y sesgo-varianza

Se recomienda **rf_somero**. Su ROC-AUC medio cambia +0.009503 frente a logistica_l2.

Corte A del 1 de julio de 2026. 77,411 tarjetas, 11,211 positivas. Cinco folds estratificados con mezcla y semilla 2026.

Se leyó A desde SQL original de 1.3 en CTE de solo lectura. La huella de todas las filas y etiquetas coincide con la publicada para A en 1.3.

La ejecución reportada utilizó Python 3.13.3 con `scikit-learn==1.9.1`, `numpy==2.5.3`, `pandas==2.3.3`, `scipy==1.18.1`, `threadpoolctl==3.7.0`, `joblib==1.6.0`. Las versiones quedan registradas en [la evidencia JSON](../evidencias/p2-21-ensemble.json).

Se ordenó por unidad_id antes de separar los folds. Se recalcularon los dos baselines y las configuraciones seleccionadas de 1.4 (L1 C=0.1, L2 C=0.01). El orden estable puede cambiar la asignación de la corrida histórica, cuya consulta carecía de ORDER BY.

| Modelo | AUC entrenamiento, media ± DE | AUC validación, media ± DE | Brecha, media ± DE |
|---|---:|---:|---:|
| baseline_tasa | 0.500000 ± 0.000000 | 0.500000 ± 0.000000 | 0.000000 ± 0.000000 |
| baseline_recencia | 0.795402 ± 0.001136 | 0.795401 ± 0.004516 | 0.000000 ± 0.005652 |
| logistica_l1 | 0.807063 ± 0.000809 | 0.806806 ± 0.003093 | 0.000257 ± 0.003899 |
| logistica_l2 | 0.807208 ± 0.000788 | 0.806967 ± 0.003134 | 0.000241 ± 0.003917 |
| rf_somero | 0.821443 ± 0.000527 | 0.816470 ± 0.002437 | 0.004974 ± 0.002900 |
| rf_regularizado | 0.854489 ± 0.000365 | 0.816965 ± 0.002168 | 0.037524 ± 0.002486 |
| rf_flexible | 0.936477 ± 0.000495 | 0.806287 ± 0.002741 | 0.130190 ± 0.003186 |

La DE es descriptiva sobre los cinco folds (ddof=0). Brecha = AUC de entrenamiento menos AUC de validación en cada fold. El AUC evalúa ordenamiento de riesgo.

## Sesgo y varianza observados

- Tasa constante. AUC 0.500000. El puntaje igual para todas las tarjetas del fold carece de discriminación.
- Recencia. AUC 0.795401 con una regla fija de una variable. La diferencia entre conjuntos refleja su composición.
- L1 y L2. Sus brechas son 0.000257 y 0.000241. La regularización limita el ajuste a patrones particulares de entrenamiento. L1 puede anular coeficientes y L2 los contrae.
- rf_somero. Profundidad 6, hoja mínima 50, brecha 0.004974 y AUC validación 0.816470.
- rf_regularizado. Profundidad 12, hoja mínima 20, brecha 0.037524 y AUC validación 0.816965.
- rf_flexible. Profundidad None, hoja mínima 5, brecha 0.130190 y AUC validación 0.806287.

El bosque con mayor brecha fue rf_flexible. El mejor AUC de validación entre bosques fue el de rf_regularizado. Del bosque somero al flexible el AUC cambia +0.115033 en entrenamiento y -0.010183 en validación. El límite de profundidad y el mínimo por hoja restringen el ajuste del somero, mientras que las hojas pequeñas permiten interacciones más específicas. Mantener cien árboles y el mismo muestreo por árbol concentra la comparación en profundidad y tamaño de hoja. La brecha y la DE entre folds describen optimismo y dispersión empíricos. La descomposición matemática de sesgo y varianza requeriría otro diseño.

## Decisión

La recomendación de `rf_somero` equilibra el ROC-AUC de validación, la complejidad del modelo y la brecha de generalización. `rf_regularizado` alcanzó un AUC ligeramente mayor (0.816965 frente a 0.816470) y presentó una brecha mayor (0.037524 frente a 0.004974). La menor profundidad y la menor brecha del bosque somero justifican recomendarlo pese a esa pequeña diferencia de AUC.

En esta implementación, un bosque es elegible si supera a la mejor logística convergente por al menos 0.002 de AUC medio, gana al menos 4 de 5 folds y mantiene su DE y su brecha dentro de 0.002 y 0.020 adicionales, respectivamente. Entre los bosques elegibles, se prefiere el menos complejo cuyo AUC medio quede a una distancia de hasta 0.001 del mejor. Si ningún bosque cumple los criterios, se recomienda la mejor logística convergente.

| Bosque | Delta AUC medio | Folds ganados | Estabilidad | Brecha | Elegible |
|---|---:|---:|---|---|---|
| rf_somero | +0.009503 | 5/5 | Sí | Sí | Sí |
| rf_regularizado | +0.009998 | 5/5 | Sí | No | No |
| rf_flexible | -0.000681 | 3/5 | Sí | No | No |

```json
{
  "familia": "bosque",
  "parametros": {
    "n_estimators": 100,
    "max_features": "sqrt",
    "bootstrap": true,
    "criterion": "gini",
    "random_state": 2026,
    "n_jobs": 1,
    "max_depth": 6,
    "min_samples_leaf": 50
  }
}
```

## Importancia por permutación

Se permuta cada columna original antes del Pipeline ajustado en el fold. Se registra la caída de ROC-AUC de validación con cinco permutaciones por variable. El promedio pondera igual los folds. La DE entre folds usa sus medias y la DE de permutación promedia la dispersión de las cinco repeticiones en cada fold. Una importancia negativa se conserva. Variables correlacionadas pueden compartir o sustituir señal.

Se utilizaron 4000/15483, 4000/15482, 4000/15482, 4000/15482, 4000/15482 filas de validación en los folds 0–4.
Para un bosque se limita el cálculo a 4,000 filas estratificadas por fold cuando se supera ese tamaño. Esto acota el costo de las predicciones repetidas en cien árboles. La comparación de AUC y la exportación OOF utilizan todos los registros.

| Variable original | Caída AUC media | DE entre folds | DE media de permutación |
|---|---:|---:|---:|
| dias_desde_ultimo_uso | +0.054008 | 0.003650 | 0.004669 |
| viajes_7d | +0.016639 | 0.002718 | 0.003334 |
| viajes_14d | +0.008063 | 0.002197 | 0.001599 |
| viajes_28d | +0.004585 | 0.001235 | 0.001360 |
| dias_activos_28d | +0.002125 | 0.001132 | 0.000939 |
| operador | +0.001001 | 0.000220 | 0.000297 |
| gasto_28d_gtq | +0.000943 | 0.000446 | 0.000763 |
| tarifa_media_gtq | +0.000476 | 0.000265 | 0.000247 |
| puntos_origen_28d | +0.000289 | 0.000187 | 0.000295 |
| proporcion_fin_semana | +0.000181 | 0.000180 | 0.000207 |

## Resumen de implementación y continuidad

El requisito 2.1 completó la comparación de baselines, logísticas y bosques en A, el análisis de las brechas de generalización, la importancia por permutación en validación y la generación de predicciones OOF para `rf_somero`, el modelo recomendado.

Héctor debe usar las probabilidades OOF y las etiquetas de A para fijar el umbral de 2.2, junto con la configuración del modelo y el orden de predictores registrados en la evidencia. El CSV local `datos_red/p2-21-oof-a.csv` está ignorado por Git. Debe compartirse directamente o regenerarse con el comando de abajo. [Evidencia JSON](../evidencias/p2-21-ensemble.json).

Después de que Héctor fije el umbral, Alejandro deberá reutilizar en 2.4 la configuración definitiva del modelo, su preprocesamiento y ese umbral.

## Reproducción

Desde la raíz, con el entorno de requirements-ml.txt y PostgreSQL configurado mediante POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER y POSTGRES_PASSWORD en .env.

```powershell
python scripts/entrenar_p2_21_ensemble.py --recalcular-a
```

El comando sin opciones lee la tabla materializada de 1.3. La opción `--recalcular-a` ejecuta el SQL original de 1.3 sobre Silver y la población A de 1.2 en una transacción de solo lectura. Exige coincidencia con la huella publicada de A antes de entrenar.

El CSV contiene una predicción de validación por tarjeta, con fold 0–4 y configuración. El JSON conserva hashes, versiones, métricas y permutaciones por fold. Para el reajuste posterior en todo A, usar `build_model(recomendado['configuracion'])` con el orden de predictores del JSON.

El AUC OOF agrupado fue 0.816293. El AUC medio de folds es la métrica principal. La selección y el AUC se calcularon en los mismos folds de A. La evaluación final del modelo elegido requiere un conjunto separado.

El SHA-256 del CSV OOF es `52427568e65f76ccfbab0e5d27cd9e905467759ce421e48f009deffe0b7dc8a0`.
