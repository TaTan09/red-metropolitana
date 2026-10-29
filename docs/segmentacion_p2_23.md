# Requisito 2.3: KMeans y PCA

Se implementó después de publicar la tabla y la auditoría oficial de 1.3.
La fuente es `silver.silver_p2_features_tarjeta`, **sólo corte A**, con 77411
tarjetas. La huella SHA-256 de A coincide con el resumen oficial de 1.3:
`9ad9b2ac9edd1c6d2bf5ed898163df7973dde5d14e0bbe794c9128af5e1634c8`.
No se consultan B ni C.

## Variables y método

Se usan las diez features numéricas del [diccionario de 1.3](features_p2_13.md).
Se excluyen identificadores, fechas y `operador`, que es categórica; no se
impone una distancia euclídea artificial entre categorías de operador.
Las variables numéricas sí contienen diferencias de tarifa y uso observadas.
`etiqueta` sólo participa al describir tasas después de elegir y ajustar los
segmentos: nunca entra a StandardScaler, KMeans, PCA, nombres ni selección de k.

1. Ordenar A por unidad y fecha y comprobar clave única y etiqueta válida.
2. Ajustar `StandardScaler` con todo A para que quetzales, conteos y proporciones
   sean comparables en distancia. No se ajusta nada con datos B/C.
3. Evaluar k=2..8 con KMeans, `n_init=20`, `max_iter=300`, algoritmo Lloyd y
   semilla 2026. Se usa un hilo numérico para reproducir los resultados.
4. Graficar la inercia sobre las 77411 filas. El codo geométrico es la mayor
   distancia vertical entre la curva normalizada y la recta de sus extremos.
5. Comparar silueta en una **misma muestra uniforme fija de 3000 tarjetas** para
   cada k. Es una estimación sobre esa muestra, no la silueta exacta de todo A.
6. Elegir la máxima silueta; un empate favorece el menor k. La regla está en el
   código y no mira etiquetas. PCA usa las mismas diez features escaladas,
   con dos componentes y `svd_solver='full'`.

## Resultados y elección de k

Se elige **k=2**, silueta **0.4929469**. El codo sugiere **k=4**, cuya silueta
es **0.2279534**. No se afirma que ambos criterios coinciden: k=4 reduce inercia
y subdivide el comportamiento, pero k=2 ofrece mayor separación según la regla
previa y una interpretación sencilla de frecuencia/recencia. La inercia baja
al agregar clusters, de modo que su mínimo no es por sí solo el criterio de k.

PCA explica **50.7014 %** con PC1 y **14.6441 %** con PC2: **65.3454 %** en total.
KMeans se ajusta en diez dimensiones, no sobre esta proyección; la figura 2D
omite parte de la variación y no representa todas las distancias originales.

| Segmento | Nombre | Tamaño | Viajes 28d, mediana | Recencia, mediana (días) | Gasto Q, mediana | Abandono descriptivo A |
|---|---|---:|---:|---:|---:|---|
| S0 | Uso ocasional y con pausa mayor | 69027 | 6 | 3.7669 | 9.00 | 11055 / 69027 = 16.0155 % |
| S1 | Uso frecuente y reciente | 8384 | 40 | 0.4111 | 61.10 | 156 / 8384 = 1.8607 % |

Los nombres comparan medianas de frecuencia y recencia con las medianas
globales de A. “Pausa mayor” es una comparación relativa, no un DELETE ni una
declaración de abandono. Las diez medianas por grupo están en el CSV/JSON.
Los positivos suman 11211, iguales al total de A de 1.2.

Acciones distintas:

- **S0:** recarga de retorno de monto limitado y recordatorio tras una pausa de uso.
- **S1:** beneficio por continuidad o abono de viajes en puntos de origen habituales.

Son propuestas para explorar; las tasas son descriptivas y no prueban que el
segmento cause abandono ni que esas acciones funcionen. El umbral de contacto
y su ganancia corresponden a 2.2 y no se eligieron aquí.

## Entregables

- [Resultados, gráficos y tabla resumida](metricas/p2-23-segmentacion/resumen.md).
- [Tabla con todas las medianas y acciones](metricas/p2-23-segmentacion/segmentos.csv).
- [Curvas, parámetros, versiones y procedencia](metricas/p2-23-segmentacion/resultados.json).
- [Prueba de repetibilidad real](evidencias/p2-23-repetibilidad.json).
- Asignaciones completas y coordenadas PCA: `datos_red/p2-23-asignaciones.csv`,
  generado localmente y excluido de Git. Los resultados agregados y PNG se versionan.

## Reproducción

Con Python 3.12, PostgreSQL y 1.3 ya construido:

```powershell
python -m pip install -r requirements-ml.txt
python scripts/segmentar_p2_23.py --output-dir docs/metricas/p2-23-segmentacion
```

Se fijan versiones de las dependencias numéricas y de gráficos en
`requirements-ml.txt`; el JSON registra las versiones efectivamente usadas.
Los destinos deben ser nuevos, para conservar la evidencia. Para repetir:

```powershell
python scripts/segmentar_p2_23.py --output-dir datos_red/p2-23-repeticion --assignments datos_red/p2-23-repeticion.csv
```

Se ejecutaron ambas corridas completas: métricas, segmentos, CSV de asignaciones
y coordenadas PCA coinciden exactamente; los tres PNG también tienen el mismo
contenido binario. Sólo el tiempo de ejecución se excluye al comparar JSON.
La primera lectura, ajuste y descripción numérica tardó 60.393 s, sin contar
la escritura y renderizado finales.

## Revisiones y pruebas

- Funcional: se comprobaron tamaños, diez medianas por grupo, suma de población
  y positivos, varianza explicada y generación de las tres figuras.
- ML: StandardScaler y PCA sólo usan A; la función de ajuste no recibe etiqueta.
  Cambiar etiquetas sólo cambia la descripción de abandono. La silueta usa el
  mismo subconjunto para todos los k. Se documenta la discrepancia con el codo.
- Ingeniería: se corrigió una escritura de caché Matplotlib fuera del workspace;
  ahora usa `datos_red/.matplotlib`. Se rechazan nulos, infinitos, muestras no
  válidas, diversidad insuficiente y destinos existentes. Los gráficos se
  inspeccionaron visualmente sin texto recortado ni solapamiento de etiquetas.
- Suite completa: **87 pruebas correctas, sin omitidas**, incluidas seis nuevas
  para 2.3 y las ocho pruebas temporales en PostgreSQL de 1.3.

Los conteos, gasto y días activos están correlacionados; su redundancia puede
dar más peso al volumen de uso en la distancia. La solución es exploratoria
y no demuestra que exista una única segmentación verdadera. Los datos son
simulados y la unidad sigue siendo tarjeta, con la limitación de identidad
entre operadores documentada en 1.2.

El segmento no se incorpora como feature del clasificador. Si se incorpora
después, el escalado y KMeans deberán ajustarse dentro de cada fold de A.
No se entrenó ni evaluó el clasificador de 2.2.
