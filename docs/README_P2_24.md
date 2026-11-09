# Reproducir 2.4 — MLOps de C

Se utiliza `v1_rf_somero`, ajustado sólo en A con la configuración oficial de
2.1, y el umbral completo `0.311210473799652` de 2.2. La inferencia carga el
Pipeline guardado. Nunca ejecuta búsquedas, entrenamiento ni evaluación B.

## Instalación mínima

Python **3.12** y PostgreSQL **16**. Probado en Windows con Python 3.12.3.
`requirements-inferencia.txt` fija las 18 dependencias directas y transitivas.
No requiere Tableau, Kafka, dbt ni Prefect para inferir desde la carpeta portable.

```powershell
git clone --branch p2/correccion-24 https://github.com/TaTan09/red-metropolitana.git
cd red-metropolitana
python -m venv .venv
.venv\Scripts\python.exe -m pip install -r requirements-inferencia.txt
.venv\Scripts\python.exe -m pip check
if (!(Test-Path .env)) { Copy-Item .env.example .env }
```

Configurar `POSTGRES_HOST`, `POSTGRES_PORT`, `POSTGRES_DB`, `POSTGRES_USER` y
`POSTGRES_PASSWORD` en `.env`. Para Docker local, ajustar una contraseña propia
y un puerto libre y ejecutar `docker compose up -d postgres`. No publicar `.env`.
El usuario de inferencia necesita conexión y permiso TEMP; el motor puede estar
vacío, sin esquema Silver. La carpeta de datos aporta todas las fuentes.

## Preparar los datos de entrada

`--datos` es obligatorio y **se utiliza realmente**. Debe apuntar a una carpeta
con `manifest.json` y seis CSV, o a su carpeta padre con el subdirectorio
`p2-24-entrada/`. No hay fallback a las tablas Silver de una base fija.

Si el equipo ya cargó Silver P2 con el flujo existente:

```powershell
.venv\Scripts\python.exe scripts/datos_p2_24.py --fecha-corte 2026-08-30
```

Esto crea, sin sobrescribir, `datos_red/p2-24-entrada/`: cuatro fuentes de
operaciones, CDC y cuarentena con sólo las columnas utilizadas por 1.2/1.3.
No exporta etiquetas. Operaciones y CDC se recortan antes de C; en MR se
requiere también cierre previo. La cuarentena conserva exclusiones por evento.
El manifest registra columnas implícitas en el contrato, conteos, hashes y una
referencia independiente de identidades/features frente al Silver original.

En otra máquina, copiar **esa carpeta completa** desde el equipo o preparar
Silver con los nueve datasets oficiales usando el flujo ya documentado en el
[README general](../README.md) y luego exportarla. Los datasets no están en Git.
Para una instalación completa del pipeline se necesita además
`requirements-ml.txt`; colocar los nueve archivos en `data/raw/`, validar con
`python scripts/validar_raw.py` y ejecutar
`python orchestration/flows/fase1_pipeline.py --evidence-prefix p2-equipo-nueva-maquina`.
Usar un prefijo nuevo y el PostgreSQL de esa instalación. No ejecutar
`--fresh-start` sobre la base/evidencias oficiales. Este flujo reconstruye
datos y features; no ejecuta el test del modelo B.

## Comando de defensa y salida

Con el venv activado:

```powershell
python predecir.py --datos datos_red --fecha-corte 2026-08-30
```

También se puede ejecutar sin activar:

```powershell
.venv\Scripts\python.exe predecir.py --datos datos_red --fecha-corte 2026-08-30 --salida datos_red/defensa-c.csv
```

La salida predeterminada es `datos_red/p2-24-predicciones-c.csv`, **versionada
en GitHub**: 76,420 filas, 10,412 contactos, orden por `unidad_id`, columnas
exactas `unidad_id,tarjetas,puntaje,contactar`. Cada unidad es una tarjeta por
operador y `tarjetas` contiene su llave original; no hay consolidación personal
ni sustitución por un conteo. Las llaves se preservan como texto.

El programa verifica hashes, headers y conteos de los seis archivos, los carga
en tablas TEMP y ejecuta los SQL originales de 1.2 y 1.3 restringidos a C.
Todas las refs de datos apuntan a TEMP; no lee las features de una tabla fija.
No consulta etiquetas futuras: en C el SQL produce NULL y el SELECT de
inferencia no selecciona esa columna. El estado TEMP se revierte y descarta.

Si ya existe el CSV entregado, el comando **recalcula** y compara todos sus
bytes: conserva el archivo/evidencia cuando coincide. Si difiere, falla y pide
otra `--salida`, preservando la entrega original. Nunca sobrescribe un CSV
ajeno. El JSON compañero registra hashes, fuentes, modelo, umbral y tiempos;
para medir una ejecución nueva usar una ruta nueva.

Para esta entrega sólo se admite `2026-08-30`; fechas inválidas o B se rechazan.
Una carpeta faltante, alterada o de otro corte produce un error explícito.

## Modelo y reajuste reproducible

Se incluyen el `.joblib` y su JSON en `models/`. El loader verifica su SHA-256,
versiones, clase RF, parámetros, columnas, clases 0/1 y preprocesamiento antes
de inferir. Sólo cargar artefactos joblib de origen confiable.

Para reproducir el ajuste A en una ruta nueva (requiere Silver P2):

```powershell
.venv\Scripts\python.exe scripts/serializar_modelo.py --salida datos_red/modelo_abandono_rf_somero_v1.joblib
```

Se llama a `build_model` de 2.1, con sus once predictores en el mismo orden,
semilla 2026 y un hilo. La entrada A debe coincidir con las huellas de 1.3 y
2.1. No usa B. El artefacto publicado está entrenado con 77,411 filas A.
`--modelo <ruta.joblib>` permite cargar una réplica con su JSON compañero.

## Invariancia temporal, con datos diferentes

```powershell
.venv\Scripts\python.exe scripts/invariancia_p2_24.py --datos datos_red --original datos_red/p2-24-predicciones-c.csv --trabajo datos_red/invariancia-defensa --evidencia datos_red/invariancia-defensa.json
```

Usar rutas nuevas. El CSV original necesita el JSON compañero generado por
`predecir.py`; al clonar, ejecutar primero el comando de defensa para crearlo.
El auditor copia las entradas, conserva sus prefijos originales byte a byte y
agrega registros de prueba en `[2026-08-30,2026-09-29)`:

| Fuente | Registros añadidos |
|---|---:|
| Transmetro | 3,000 |
| Transurbano | 3,000 |
| Aerómetro | 3,000 |
| MetroRiel | 3,001 |
| CDC, DELETE posteriores | 3,000 |
| Cuarentena de eventos nuevos | 30 |

Los 15,031 registros son **sintéticos añadidos sobre las entradas reales del
proyecto**, no datos futuros reales recibidos del profesor. En MR se incluye
además un viaje ingresado un minuto antes del corte y cerrado después, para
probar disponibilidad. Luego se ejecuta `predecir.py` sobre la copia ampliada
y se comparan población, llaves, features y las cuatro columnas de salida sin
tolerancia ni redondeo. El modelo y umbral deben ser idénticos en ambos casos.

Resultado final: **cero diferencias**, 76,420 unidades y CSV idénticos byte a
byte. [Evidencia final](evidencias/p2-24-invariancia-final.json). La prueba
abarca desde Silver operacional/CDC/cuarentena hasta el CSV. La ingestión de
nuevos Raw/Bronze se mantiene en el flujo existente; no se afirma haber probado
un archivo futuro que aún no se recibió. Para la defensa con nuevos archivos,
cargarlos por ese flujo en un entorno separado, volver a exportar las entradas
y comparar el CSV del mismo corte con la entrega.

## Verificaciones y mediciones

```powershell
$env:P2_TEST_POSTGRES='1'
.venv\Scripts\python.exe -m unittest discover -s tests
Get-FileHash models/modelo_abandono_rf_somero_v1.joblib -Algorithm SHA256
Get-FileHash datos_red/p2-24-predicciones-c.csv -Algorithm SHA256
```

Las pruebas usan fixtures, incluidos controles positivos que introducen una
fuga deliberada y alteran datos previos al corte para exigir un cambio. Ninguna
prueba ejecuta el test B real. La bitácora y decisión B se conservaron intactas.
La suite final pasó **123 pruebas, cero omitidas**, incluidas **12 nuevas de
2.4**, en 57.914 segundos con integración PostgreSQL activada.

| Operación medida | Segundos |
|---|---:|
| Exportar entradas Silver | 24.285 |
| Carga y features A antes del ajuste | 27.093 |
| Ajuste RF con todo A | 9.786 |
| Entrenamiento y serialización total | 37.179 |
| Carga de CSV a TEMP, C | 27.058 |
| Features y validación C | 44.086 |
| `predict_proba`, C | 1.305 |
| Primera inferencia C completa | 76.682 |

Son tiempos observados en esta máquina; el JSON de cada corrida conserva los
valores sin redondear. La serialización comprimida puede cambiar sus bytes con
otra versión de Python, aunque se conserve el score; usar el artefacto publicado
y las versiones fijas para contrastar los hashes publicados.

- Modelo: `242b8e76d105327bb9c09822af640b5d3146de45d669b7d818e89774ceb7980d`.
- CSV C: `dfa5126bcb3c67962090016fc55c6d39d9936a3f17aeb2b95224cc26d4e2ed59`.

La inferencia se verificó además en un **venv nuevo**, desde otro directorio,
contra una **base PostgreSQL vacía sin Silver**, posteriormente eliminada:
el CSV fue idéntico. [Evidencia](evidencias/p2-24-otro-entorno.json).
No se afirma haber probado otros sistemas operativos.

Ver [ficha del modelo](modelo_ficha.md), [evidencia C](evidencias/p2-24-predicciones-c.json)
y [tres revisiones y pruebas](evidencias/p2-24-revisiones.json).
