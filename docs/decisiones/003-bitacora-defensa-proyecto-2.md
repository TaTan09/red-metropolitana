# Bitácora consolidada de decisiones — Proyecto 2

**Proyecto:** Agencia Metropolitana de Transporte — Ciencia de Datos, Universidad Rafael Landívar  
**Propósito:** respaldar la defensa en video con la decisión, su responsable y una cifra verificable.  
**Fuente:** código, commits e informes previamente integrados en `main`. Esta bitácora es una **consolidación documental**: no vuelve a entrenar, no consulta las etiquetas de B ni ejecuta nuevas evaluaciones.

## Responsabilidades verificables

- **Jonatán Chávez (1185023):** implementación inicial de población y etiqueta por TARJETA (1.2), trabajo de ingesta y comparación ensemble / sesgo-varianza (2.1).
- **Héctor Pérez (1304223):** ejecución e idempotencia de los datos nuevos (1.1), features y auditoría de fuga (1.3), umbral y test B (2.2); implementación inicial de KMeans/PCA y correcciones finales de MLOps (2.4).
- **Alejandro Gil (1187420):** baselines y logística regularizada (1.4), primera implementación del componente MLOps (2.4).
- **José Carlos Avalos Pérez (1315918):** revisión y validación independiente de KMeans/PCA (2.3), incluida la ratificación documentada de `k=2`.

La atribución separa **implementación inicial**, **decisión respaldada por la evidencia** y **validación posterior**, cuando participaron integrantes diferentes. El proyecto es un trabajo de equipo.

## Decisiones y números de respaldo

| ID | Requisito | Qué se decidió y por qué | Responsables documentados | Número que lo respalda | Evidencia |
|---|---|---|---|---|---|
| D01 | 1.1, datos | **Reutilizar la arquitectura del Proyecto 1** para reconstruir los datos nuevos, sin sustituirla por un pipeline diseñado solo para la entrega. | Héctor (ejecución final y validación), Jonatán (trabajo de ingesta). | **9/9 archivos** con diferencia de conteos **0**; dos corridas documentadas con resultados equivalentes. | [Corrida 2](../metricas/p2-hector-001-requisito-1-1-corrida-2.md), [idempotencia](../evidencias/p2-hector-001-idempotencia.md). |
| D02 | 1.2, unidad | Elegir **TARJETA por operador** en lugar de afirmar una identidad personal universal. Mantener explícito el costo de observar abandono aparente cuando hay actividad en otra tarjeta aproximadamente vinculada. | Jonatán (implementación original); Héctor (ampliación y verificación). | A: **11,211 / 77,411 = 14.482438 %**; B: **10,312 / 76,378 = 13.501270 %**. En A, **2,394 / 11,211 = 21.354027 %** de positivos tienen actividad vinculada en otro operador. | [Población, definición y costo](../metricas/p2-12-tarjeta.md). |
| D03 | 1.3, features y fuga | Usar ventanas de **7, 14 y 28 días**, límites superiores exclusivos, disponibilidad de viajes cerrados y exclusiones de cuarentena/CDC por fecha. No introducir información posterior al corte. | Héctor. | Auditoría A: **77,411 filas**, **11 predictores**, **0 diferencias** al recortar fuentes; C: **76,420 etiquetas NULL**. | [Diccionario y auditoría](../features_p2_13.md), [resultado](../evidencias/p2-13-auditoria-p2.json). |
| D04 | 1.4, modelos base | Usar **ROC-AUC** para comparar ordenamiento de riesgo sin fijar previamente un umbral; seleccionar **logística L2, C=0.01** entre las logísticas iniciales, conservando dos baselines. | Alejandro. | CV inicial A: tasa constante **0.5000**, recencia **0.7954**, logística L1 **0.8069** y L2 **0.8071**. En la comparación posterior de 2.1, L2 re-evaluada en folds ordenados registró **0.806967**. | [Comparación inicial](../metricas/p2-14-modelos.md), [comparación común 2.1](../metricas/p2-21-ensemble.md). |
| D05 | 2.1, producción | Recomendar **Random Forest `rf_somero`** (100 árboles, profundidad 6, mínimo 50 por hoja), no el bosque más flexible ni el de máxima AUC por una diferencia mínima, por equilibrio entre discriminación y brecha entrenamiento-validación. | Jonatán. | AUC validación **0.816470**; mejora de **+0.009503** frente a L2 re-evaluada; brecha **0.004974**. `rf_regularizado`: AUC **0.816965** pero brecha **0.037524**; `rf_flexible`: brecha **0.130190**. | [Análisis de 2.1](../metricas/p2-21-ensemble.md), [JSON](../evidencias/p2-21-ensemble.json). |
| D06 | 2.1, interpretación | Calcular importancia de variables por **permutación sobre validación**, no sobre entrenamiento, y reconocer las correlaciones entre ventanas de uso. | Jonatán. | La mayor caída media de AUC fue **0.054008** para `dias_desde_ultimo_uso`; siguió `viajes_7d` con **0.016639**. | [Importancias 2.1](../metricas/p2-21-ensemble.md). |
| D07 | 2.2, política | Elegir y **congelar el umbral con predicciones fuera de fold de A** según ganancia esperada, antes de abrir B; no asumir calibración perfecta. | Héctor. | Contacto **Q5**; retención supuesta **25 %**; valor **Q60**. **G = 10 TP − 5 FP**; umbral teórico **p > 1/3**, elegido **0.311210473799652**; estimación OOF A **Q16,835**. | [Reporte 2.2](../metricas/p2-22/reporte.md), [decisión congelada](../evidencias/p2-22-decision.json). |
| D08 | 2.2, prueba B | Evaluar **una sola vez** B con el modelo ajustado en todo A y el umbral congelado; conservar la diferencia de desempeño sin reajustar parámetros. | Héctor. | **7/11/2026 16:53:50 −06:00**, commit **`9d84ad3fc88277fbb2ed94592fcba3dea6eb5eda`**; **9,844** contactos, **4,070 TP**, **5,774 FP**, precisión **41.35 %**, recall **39.47 %**, AUC **0.813388**, ganancia esperada **Q11,830**. | [Resultado B](../evidencias/p2-22-test-b.json), [bitácora del acceso B](../evidencias/p2-22-test-b-bitacora.jsonl), [explicación](../metricas/p2-22/reporte.md). |
| D09 | 2.3, segmentación | Aplicar KMeans sobre **10 features numéricas escaladas de A**; elegir **`k=2` por silueta**, documentando que el codo proponía `k=4`. No usar etiquetas para ajustar ni seleccionar los segmentos. | Héctor (implementación); José Carlos (validación independiente y recomendación de conservar `k=2`). | Silueta `k=2`: **0.4929469**, `k=4`: **0.2279534**; PCA dos componentes: **65.3454 %**. Validación independiente: **6 pruebas** aprobadas. | [Método y resultados](../segmentacion_p2_23.md), [revisión José Carlos](../equipo/validacion_jose_carlos_23.md). |
| D10 | 2.3, acciones | Proponer intervenciones **distintas por perfil**, sin afirmar que ya se probó su eficacia: incentivo/recordatorio de retorno para S0; continuidad/abono habitual para S1. | José Carlos (interpretación y validación); Héctor (análisis inicial). | **S0:** 69,027 tarjetas, **11,055 / 69,027 = 16.02 %** abandono; **S1:** 8,384 tarjetas, **156 / 8,384 = 1.86 %**. | [Segmentos](../metricas/p2-23-segmentacion/resumen.md), [validación independiente](../equipo/validacion_jose_carlos_23.md). |
| D11 | 2.4, inferencia | Mantener el **mismo `rf_somero` y umbral de 2.2** en un Pipeline versionado; `predecir.py` carga el artefacto y **no reentrena**. Usar `--datos` y `--fecha-corte` con llaves originales y cuatro columnas exactas. | Alejandro (implementación inicial); Héctor (correcciones definitivas y prueba). | Corte C **30/08/2026**: **76,420** filas, **10,412** contactos, **0 duplicados**. Modelo `v1_rf_somero`; regla `puntaje >= 0.311210473799652`. | [Ficha](../modelo_ficha.md), [guía 2.4](../README_P2_24.md), [evidencia de C](../evidencias/p2-24-predicciones-c.json). |
| D12 | 2.4, invariancia | Demostrar que datos posteriores a C **no deben alterar** población, features ni predicciones de ese corte. Distinguir alcance de la prueba realizada y la prueba adicional del docente. | Héctor (prueba final y corrección); revisión del equipo pendiente con el set oficial ampliado. | **15,031 registros sintéticos futuros** agregados a copias de Silver; **0 diferencias** entre resultados; CSV idéntico byte a byte. La suite final registrada reportó **123 pruebas** y **0 omitidas**. | [Invariancia final](../evidencias/p2-24-invariancia-final.json), [revisiones 2.4](../evidencias/p2-24-revisiones.json). |

## Límites de lo demostrado

1. **Datos simulados:** el abandono y la ganancia son resultados del ejercicio; Q11,830 no son ingresos reales ni retenciones causalmente observadas.
2. **Identidad:** una tarjeta no representa necesariamente a una persona. El vínculo entre operadores es una aproximación del dataset; Aerómetro no tiene enlace personal verificable.
3. **Test B:** el resultado oficial se registró una sola vez. Esta bitácora lo lee, **no lo recalcula**.
4. **Invariancia:** la prueba de 15,031 registros tiene alcance desde fuentes **Silver operacionales/CDC/cuarentena hasta CSV**. **No sustituye** la prueba del flujo completo con los datos oficiales ampliados de la defensa. No declarar esa prueba superada hasta contar con un registro nuevo de Héctor y Alejandro.
5. **Versión final:** existe el tag histórico `fase-2`. El nuevo lineamiento exige **`entrega-final`**, que deberá crearse sobre el commit definitivo **antes de la demostración grabada**. No reutilizar ni mover `fase-2`.

## Cierre de la defensa (pendiente)

- [ ] Héctor registra la prueba de ingesta del set oficial ampliado en un entorno aislado, sin borrar evidencia previa.
- [ ] Alejandro registra la ejecución de inferencia y la comparación exacta con el CSV C entregado; si encuentra diferencias, documentarlas y resolverlas **sin cambiar el modelo o umbral con B**.
- [ ] Integrar cualquier corrección necesaria, verificar integridad del CSV, modelo, script y ficha; congelar con tag `entrega-final`.
- [ ] Registrar la toma continua de la demostración: commit, comando de inferencia, comparación y ficha.
- [ ] Añadir el enlace accesible del video al README de entrega y al README principal; entregar URL en Moodle.

**Referencia de entrega original:** [`fase-2`](https://github.com/TaTan09/red-metropolitana/tree/fase-2).
