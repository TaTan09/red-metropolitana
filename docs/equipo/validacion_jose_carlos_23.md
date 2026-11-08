cat > docs/equipo/validacion_jose_carlos_23.md <<'EOF'
# Validación independiente del apartado 2.3

**Proyecto:** Red Metropolitana — Ciencia de Datos  
**Responsable de revisión:** José Carlos  
**Apartado:** 2.3 — Segmentación KMeans y PCA  
**Rama:** p2/jose-carlos-23

## 1. Objetivo

Revisar la segmentación previamente implementada,
comprobar su funcionamiento mediante pruebas automatizadas
e interpretar los resultados del corte A, sin modificar
los apartados 2.1 y 2.2.

## 2. Validación ejecutada

Entorno utilizado:
- macOS, Apple Silicon.
- Python 3.12.16.
- Dependencias de requirements-ml.txt.

Comando ejecutado:

    python -m unittest discover -s tests -p "test_p2_23_segmentacion.py" -v

Resultado: 6 pruebas aprobadas, 0 errores.
Duración: 0.488 segundos.

Se comprobaron:
- Carga exclusiva del corte A y rechazo de duplicados.
- Selección de KMeans y repetibilidad.
- Escalado de características.
- Separación de etiquetas respecto del agrupamiento.
- Validación de entradas inválidas.
- Generación de reportes y tres gráficas.

Las pruebas se ejecutaron con datos de prueba.
Los resultados de las 77,411 tarjetas corresponden
a las evidencias oficiales previamente publicadas.

## 3. Selección del número de segmentos

Se evaluaron valores de k entre 2 y 8.

La mayor silueta fue 0.4929469 para k=2,
calculada sobre una muestra fija de 3,000 tarjetas.

El método geométrico del codo sugirió k=4.

Se conserva k=2 porque la regla de selección
prioriza la silueta, que mide separación y
cohesión de los grupos.

La discrepancia entre codo y silueta se reconoce
y no se utiliza la etiqueta de abandono para
seleccionar el número de segmentos.

## 4. Análisis PCA

PC1 explica 50.7014% de la varianza.
PC2 explica 14.6441%.

La varianza acumulada es 65.3454%.

PCA facilita visualizar los segmentos en dos
dimensiones, aunque omite aproximadamente
34.65% de la variabilidad original.

KMeans se ajusta sobre las diez características
numéricas escaladas, no sobre el PCA bidimensional.

## 5. Interpretación de segmentos

| Indicador | S0 | S1 |
|---|---:|---:|
| Tarjetas | 69,027 | 8,384 |
| Viajes en 28 días, mediana | 6 | 40 |
| Recencia, mediana en días | 3.77 | 0.41 |
| Gasto mediano | Q9.00 | Q61.10 |
| Tasa descriptiva de abandono | 16.02% | 1.86% |

S0 representa tarjetas de uso ocasional,
con menor frecuencia y pausas más largas.
Su tasa de abandono observada es superior.

S1 representa tarjetas de uso frecuente y
reciente, con mayor gasto y menor abandono.

Las tasas son asociaciones descriptivas:
no demuestran causalidad.

## 6. Acciones propuestas

**S0:** evaluar recordatorios y un incentivo
de recarga limitado para estimular el retorno.

**S1:** evaluar beneficios de continuidad o
abonos en rutas y puntos de origen habituales.

Estas acciones son hipótesis de intervención;
su eficacia tendría que medirse posteriormente.

## 7. Reproducibilidad y limitaciones

- El código fija la semilla 2026.
- El escalado y KMeans emplean solo el corte A.
- Las etiquetas no participan en el agrupamiento.
- B permanece reservado para la evaluación única
  del modelo supervisado y no fue consultado.
- La unidad analizada es tarjeta por operador,
  no una identidad personal consolidada.
- La silueta se estimó usando 3,000 tarjetas.
- Los conteos oficiales se tomaron de los
  artefactos publicados por el equipo.

## 8. Conclusión y decisión

Las seis pruebas automatizadas ejecutadas en
el entorno local finalizaron correctamente.

La evidencia publicada respalda una segmentación
de dos grupos interpretable y reproducible según
los procedimientos documentados.

Se recomienda conservar k=2 y utilizar la
segmentación como apoyo descriptivo para
diseñar intervenciones diferenciadas,
sin modificar el clasificador ni el umbral
congelado del apartado 2.2.

## 9. Referencias internas

- scripts/segmentar_p2_23.py
- tests/test_p2_23_segmentacion.py
- docs/segmentacion_p2_23.md
- docs/metricas/p2-23-segmentacion/resultados.json
- docs/metricas/p2-23-segmentacion/resumen.md
- docs/metricas/p2-23-segmentacion/segmentos.csv