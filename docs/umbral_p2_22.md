# 2.2 — Diseño, revisiones y operación

La decisión se selecciona exclusivamente con `datos_red/p2-21-oof-a.csv` y se
congela en `docs/evidencias/p2-22-decision.json` mediante un commit anterior al
test. El modelo y el preprocesamiento provienen de 2.1. No se seleccionan
modelos ni hiperparámetros, no se recalibran probabilidades.

## Economía y búsqueda exacta

Cada abandono contactado genera Q15 de beneficio esperado (25% × Q60); cada
contacto cuesta Q5. Así, `G = 15 TP - 5(TP + FP) = 10 TP - 5 FP`.
Un contacto con probabilidad real p es rentable si `15p - 5 > 0`, es decir,
`p > 1/3`. En la igualdad el beneficio esperado es cero. El score del bosque
no se supone perfectamente calibrado. El máximo empírico de A puede diferir
del umbral teórico sin que eso pruebe por sí mismo una mala calibración.

Se ordenan los scores OOF y se acumulan TP/FP por grupos de scores idénticos.
Se evalúan todos los conjuntos de contactos alcanzables mediante `p >= t`,
además de 0, 1, 1/3 y `nextafter(1,+inf)` para no contactar. El algoritmo cuesta
O(n log n). Una malla arbitraria podría omitir el máximo. Ante igual ganancia,
se prefieren menos contactos y luego el mayor umbral. Las probabilidades se
leen con `float_precision='round_trip'`; el JSON conserva precisión float64.

La tabla exportada es agregada por umbral, sin identificadores ni predicciones
individuales. La ganancia de A se maximiza sobre esos mismos OOF: tiene sesgo
de selección y no sustituye el test temporal independiente.

## Revisión 1 — Matemáticas y lógica

Se contrastan los acumulados con un cálculo directo por cada umbral y con
`sklearn.metrics` sobre fixtures. Se cubren TP/FP/TN/FN, beneficios positivos,
negativos y nulos, precisión/recall sin denominador, scores 0/1, contactos con
igualdad exacta al umbral, empates indivisibles y la alternativa de no contactar.
El desempate no depende del orden de la tabla. Costos y decisión se vuelven
a verificar con el OOF antes de permitir el test, sin consultar B.

## Revisión 2 — Machine Learning

El SHA-256 del OOF debe coincidir con el indicado por el equipo y con 2.1.
Se comprueban claves únicas, ausencia de nulos, fecha/corte, etiquetas, rango
de probabilidades, modelo, configuración JSON, población, positivos, folds
reconstruidos, hash de asignación y AUC OOF publicado. El orden de los once
predictores se obtiene de la evidencia y se contrasta con `build_model`.

El ajuste final usa todo A y el mismo Pipeline de 2.1: diez variables numéricas
passthrough y OneHotEncoder para operador, ajustado sólo en A. Se ejecuta con
un hilo y la semilla del JSON. La entrada A se recalcula con SQL original 1.3,
se coteja con su huella y con la entrada de 2.1 y se alinea con claves/etiquetas
OOF. B usa el mismo SQL con la población restringida a su corte; se exige la
huella publicada de 1.3 antes de calcular métricas.

Las ventanas de features son anteriores al corte y respetan disponibilidad.
El horizonte de etiquetas de A termina al llegar al corte B; no entra la
etiqueta B al entrenamiento. Tarjetas repetidas entre A y B son admisibles
en un test temporal por tarjeta; no se afirma independencia por persona.
Los datos Silver ya contienen los horizontes necesarios para evaluar.
No se consulta la etiqueta B para elegir umbral, modelo ni preprocesamiento.

## Revisión 3 — Ingeniería y reproducibilidad

`seleccionar-a` no conecta a PostgreSQL. Se exige la rama `p2/hector-22` y
árbol limpio. Los artefactos no se sobrescriben. Se comprueban versiones,
commit y que el código, SQL, requisitos y pruebas no cambien entre selección
y test. El commit que contiene la decisión debe ser ancestro del código
ejecutado y conservar exactamente los mismos bytes de decisión.

`test-b --decision-commit COMMIT` es un comando explícito; no se ejecuta al
importar ni mediante pruebas generales. Una bitácora exclusiva (`open('x')`)
se reserva antes de acceder a los datos y se sincroniza a disco. Registra
inicio, entrenamiento A, acceso posible a etiquetas B, predicción, métricas,
resultado o error. Se conserva incluso si el entrenamiento o la consulta
fallan. Su presencia bloquea repeticiones. No hay flag de sobrescritura ni
reintento. Las métricas quedan registradas antes de generar otros archivos.

El modelo, CSV OOF, predicciones individuales y logs permanecen en
`datos_red/`, ignorado. Sólo se versionan agregados, configuración, gráfica,
pruebas y bitácora. La función `reporte` lee únicamente los JSON guardados;
no vuelve a entrenar, consultar o predecir B. El bloqueo es operacional y
no una protección contra quien borre deliberadamente todos los artefactos.

Las pruebas cubren un flujo completo con Pipeline real y datos sintéticos,
rechazo de OOF corrupto, decisión alterada y reserva previa. No acceden a B
real. Las pruebas PostgreSQL existentes usan tablas TEMP y fixtures.

## Procedimiento y entrega

1. Revisar código y ejecutar pruebas; verificar conexión y hashes sólo de A.
2. Commit de implementación/pruebas; ejecutar `seleccionar-a` con árbol limpio.
3. Verificar nuevamente tabla, máximo, gráfica y reproducibilidad usando A.
4. Commit de decisión y evidencia de A. Conservar su hash.
5. Ejecutar `test-b --decision-commit HASH` una sola vez.
6. Renderizar reporte desde JSON guardados. Versionar resultado y bitácora.

Instalación: `python -m pip install -r requirements-ml.txt`. Se utiliza el
entorno `.venv` existente y PostgreSQL del proyecto; no hace falta reconstruir
Bronze/Gold ni ejecutar el flujo completo. Las credenciales se leen de `.env`
y nunca se escriben en la evidencia. Las versiones exactas quedan en los JSON.

Para Jonatán: consumir `configuracion`, `predictores` y `umbral` del JSON de
decisión; usar `build_model` de 2.1 y ajustar sólo A, o recibir el Pipeline
local ajustado y verificar su hash publicado. Aplicar el mismo `p >= umbral`
a las features C sin etiquetas. No copiar el umbral redondeado de una gráfica.
No se implementa `predecir.py` ni el resto de 2.4 en esta entrega.

El [reporte final](metricas/p2-22/reporte.md) contiene los resultados exactos,
la matriz, las fechas y los commits. La [evidencia de revisiones](evidencias/p2-22-revisiones.json)
registra las comprobaciones realmente ejecutadas.
