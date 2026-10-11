# Linaje de Gold con dbt

## Alcance

Entregable de documentación y linaje del bloque Gold de Jonatán para el punto
3.1. El DAG generado por dbt muestra dependencias reales declaradas mediante
`ref()` y `source()`. El [diccionario Gold](diccionario_gold.md) complementa el
grafo con significado, fuente y transformación de cada una de las 162 columnas
de los 15 modelos Gold actuales.

El DAG muestra linaje **entre modelos y fuentes**; no demuestra por sí solo
linaje por columna, correspondencia de filas, causalidad, calidad de todas las
filas Raw ni identidad real de personas. El catálogo describe las relaciones
físicas existentes en PostgreSQL. Las pruebas validan las reglas que están
implementadas, no todas las posibles reglas de negocio.

## Generar la documentación

Desde la raíz del repositorio, con PostgreSQL levantado, las capas materializadas,
el entorno virtual y `.env` configurados según README:

```powershell
# Si el entorno virtual todavía no está activo:
.\.venv\Scripts\Activate.ps1

python scripts/run_dbt.py parse
python scripts/run_dbt.py docs generate
```

También se puede usar directamente `.\.venv\Scripts\python.exe` en lugar de
`python`, sin activar el entorno. `scripts/run_dbt.py` carga `.env`, comprueba
la clave de seudonimización y utiliza el ejecutable dbt del mismo entorno con
el directorio de proyecto y perfil correctos. No ejecutar un dbt ajeno al entorno.

`docs generate` compila el proyecto y consulta metadatos para crear el catálogo;
no reconstruye las tablas ni cambia métricas. Las relaciones deben existir para
que el catálogo refleje todas sus columnas. Verificar la generación sin omitir
la compilación ni la consulta de catálogo.

Los tres archivos quedan juntos en:

```text
dbt/red_metropolitana/target/manifest.json
dbt/red_metropolitana/target/catalog.json
dbt/red_metropolitana/target/index.html
```

- `manifest.json`: nodos, descripciones, fuentes, dependencias y SQL del proyecto.
- `catalog.json`: modelos/fuentes físicos y columnas/tipos consultados en la base.
- `index.html`: aplicación para navegar documentación y DAG, que carga los JSON.

`target/` y `logs/` están ignorados por Git; no se versionan los artefactos
generados. Se regeneran localmente con los comandos anteriores. El SQL compilado
y el manifest pueden contener la clave HMAC interpolada por la macro
`usuario_sk`; mantener estos artefactos locales y no publicarlos ni compartirlos
sin revisar ese contenido. Esto deriva de la macro existente: esta tarea no
cambia la seudonimización ni la política de acceso del proyecto.

## Abrir la documentación y el DAG

Desde la raíz y con el mismo entorno:

```powershell
python scripts/run_dbt.py docs serve --host 127.0.0.1 --port 8080 --no-browser
```

Abrir `http://127.0.0.1:8080` en el navegador. Mantener el proceso abierto mientras
se consulta; terminarlo con Ctrl+C. Servir los tres archivos juntos evita las
restricciones del navegador al abrir `index.html` directamente con `file://`.

En dbt Docs, buscar un modelo Gold, revisar **Description**, **Columns** y SQL,
abrir el grafo de linaje y expandir sus ancestros. Por ejemplo, comenzar en
`v_tableau_metroriel`, seguir `mart_metroriel_zonas` y expandir dimensiones y
hechos hasta los modelos Silver y las fuentes `staging`.

## Recorridos reales

| Destino Gold | Ancestros inmediatos | Continuación hacia Silver/Staging |
|---|---|---|
| `dim_usuario` | `bridge_identidad_usuario` | Las cuatro operaciones Silver válidas → tablas operacionales Staging; el puente no consume CDC ni padrón SCD2 |
| `dim_tiempo` | Cuatro operaciones Silver; MR aporta ingreso y salida | Tablas operacionales Staging; AM convierte UTC a Guatemala en Silver |
| `dim_zona` | `silver_universo_zonas` | Universo literal del generador + `silver_catalogo_puntos` → cuatro catálogos Staging |
| `dim_punto_transporte`, `dim_modo` | `silver_catalogo_puntos` | `staging.tm_estaciones`, `tu_paradas`, `mr_estaciones`, `am_estaciones` |
| `dim_servicio` | Cuatro operaciones Silver | Línea TM, ruta TU, eje AM; servicio MR literal, sin campo Raw de línea |
| `fact_abordajes` | Operaciones Silver TM/TU/AM, puente y catálogo Silver | Tablas operacionales y catálogos Staging; un abordaje por registro válido |
| `fact_viajes_metroriel` | Operación Silver MR, puente y catálogo Silver | `staging.metroriel_viajes` y catálogo MR; un viaje cerrado por fila |
| `mart_demanda_hora` | Ambos hechos, `dim_tiempo`, `dim_zona`, `dim_modo` | Ancestros Silver anteriores; MR usa tiempo de ingreso y zona de origen |
| `mart_cobertura` | `mart_demanda_hora`, `dim_zona` | Actividad de hechos + oferta del catálogo y universo Silver |
| `mart_metroriel_zonas` | `dim_punto_transporte`, `dim_modo`, ambos hechos, `dim_zona` | Oferta MR + abordajes TM/TU/AM + viajes MR por origen; ranking previo al filtro del trazado |
| `v_tableau_demanda_abordajes`, `v_tableau_demanda_viajes_mr` | `mart_demanda_hora` | Separan por tipo de evento y explicitan unidad |
| `v_tableau_cobertura` | `mart_cobertura` | Separa abordajes y viajes; recalcula participación/rankings específicos |
| `v_tableau_metroriel` | `mart_metroriel_zonas` | Proyección de métricas y ranking global; no suma abordajes con viajes |

Las dimensiones y hechos de base consumen solo Silver. Los marts consumen Gold,
y las vistas consumen sus marts. Las claves foráneas lógicas se documentan y
prueban con `relationships`, pero esas relaciones no crean flechas `ref()` entre
hechos y dimensiones cuando el SQL del hecho calcula la clave desde Silver.
Por eso el DAG de construcción y el diagrama dimensional no son el mismo grafo.

En el DAG, `source('staging', ...)` es el límite externo de dbt: las flechas de
Raw → Bronze → Staging las implementan los scripts de ingesta/carga, no dbt.
No se añaden fuentes ficticias de Raw/Bronze para simular que dbt las lee.

## Continuar al registro físico de Bronze y a Raw

El recorrido completo de una métrica consumida por Tableau es:

```text
Tableau → v_tableau_* → mart → hechos Gold contribuyentes
        → bronze_record_id (conservado desde Silver/Staging)
        → registro físico Bronze
        → _source_file + _source_sha256 + _record_number
        → archivo Raw verificado por SHA-256 y registro/fila original
```

Ambos hechos conservan `bronze_record_id` de Silver, que viene de Staging.
`fuente_evento` identifica la operación y la tabla Staging que corresponde.
Una fila agregada requiere recuperar **todos** sus hechos contribuyentes por
zona/modo/fecha/hora; MetroRiel se filtra por ingreso y zona de origen, no destino.
Para auditar un ranking o porcentaje se necesita además el conjunto de toda la
red que define el ranking/denominador, incluidas áreas sin actividad.

| Modo | Tabla Staging y carpeta Bronze | Identificador físico |
|---|---|---|
| Transmetro | `transmetro_validaciones` | `_event_id = SHA256(_source_sha256 + ':' + _record_number)` |
| Transurbano | `transurbano_transacciones` | `_source_sha256 + ':' + _record_number` |
| Aerometro | `aerometro_boardings` | `_event_id = SHA256(_source_sha256 + ':' + _record_number)` |
| MetroRiel | `metroriel_viajes` | `_source_sha256 + ':' + _record_number` |

En batch, `bronze_record_id` contiene el SHA-256 del archivo y el número de
registro separados por `:`. En streaming usa `_event_id`; el registro Bronze
conserva también `_source_file`, `_source_sha256` y `_record_number`, necesarios
para continuar hasta Raw sin intentar invertir el hash del evento.

Elegir ejemplos y verificar el enlace a Staging mediante los SQL existentes:

```powershell
Get-Content sql/utilities/linaje_ids.sql | docker exec -i red_metropolitana_postgres psql -U red_user -d red_metropolitana
Get-Content sql/utilities/linaje_gold_staging.sql | docker exec -i red_metropolitana_postgres psql -U red_user -d red_metropolitana
```

El segundo SQL es el ejemplo Transurbano. Las otras operaciones también unen
Gold/Silver/Staging por `bronze_record_id`. Adaptar usuario y base si la
configuración local usa otros nombres.

Para cada modo, copiar un identificador del primer SQL y ejecutar, sustituyendo
el valor de ejemplo:

```powershell
python scripts/trazar_linaje.py Transmetro 'ID_COPIADO_DE_GOLD'
python scripts/trazar_linaje.py Transurbano 'ID_COPIADO_DE_GOLD'
python scripts/trazar_linaje.py Aerometro 'ID_COPIADO_DE_GOLD'
python scripts/trazar_linaje.py MetroRiel 'ID_COPIADO_DE_GOLD'
```

`scripts/trazar_linaje.py` filtra Parquet por `_event_id` en streaming o por
hash/número de registro en batch, y muestra el payload original de Bronze.
Ese payload puede incluir llaves personales: es una herramienta de auditoría,
no una vista para Tableau. El script **no abre Raw**: la continuación utiliza
`_source_file`, `_source_sha256` y `_record_number` del Parquet para localizar el
archivo conservado, verificar su SHA-256 y consultar el registro. En CSV, el
número se cuenta sin encabezado; en JSONL identifica la línea. Verificar hash
antes de atribuir la fila a un archivo que pudo haber cambiado.

## Prueba práctica de trazabilidad

Se verificaron dos registros reales de PostgreSQL mediante consultas de solo
lectura, `scripts/trazar_linaje.py` y lectura de los archivos locales Raw.
Tableau todavía no tiene workbook: el punto de entrada comprobado es la vista
Gold que consumirá. Los ejemplos son **una contribución** a cada agregado, no
la totalidad de sus registros.

| Comprobación | Abordaje Transmetro (streaming) | Viaje MetroRiel (batch) |
|---|---|---|
| Vista de entrada | `gold.v_tableau_demanda_abordajes` | `gold.v_tableau_demanda_viajes_mr` |
| Agregado elegido | 2026-06-04, hora 9, Transmetro, Zona 12 | 2026-07-13, hora 16, MetroRiel, Zona 8 (origen) |
| Vista = `mart_demanda_hora` = suma de hechos contribuyentes | **36 abordajes** | **90 viajes iniciados** |
| Hecho elegido | `gold.fact_abordajes` | `gold.fact_viajes_metroriel` |
| Clave técnica Gold | `1094f9c5b8b46f4063eacf97375ec5fd` | `63c9a775389d8e9fa7df8f29d2521a4c` |
| `bronze_record_id` real | `11f07ffaf5c061f140e1e178c5aa060ad79b913f6458f6c4a37a9b5bd2ab0659` | `23feb4a3a55ce506bf34de5faf7834f9c390b7ca70499cc9fb3ec1c3650ebede:281314` |
| Coincidencias por ID en Silver / Staging | 1 / 1 en `silver_transmetro_validaciones` / `transmetro_validaciones` | 1 / 1 en `silver_metroriel_viajes` / `metroriel_viajes` |
| `_source_file` → archivo Raw | `data/raw/transmetro_validaciones.csv` | `data/raw/metroriel_viajes.jsonl` |
| `_record_number` | **34942**, registro CSV sin encabezado (línea 34943 en este archivo) | **281314**, línea JSONL |
| `_source_sha256` = SHA-256 recalculado del archivo Raw | `5f88356e427d0ec19b193f6aaafedc288d9bf3fbad1881f011a7d9ea912730d2` | `23feb4a3a55ce506bf34de5faf7834f9c390b7ca70499cc9fb3ec1c3650ebede` |
| Payload original | `raw_json.data` de Bronze coincide íntegramente con el registro CSV | `raw_json` de Bronze coincide íntegramente con el objeto de la línea JSONL |

Además, se recalcularon correctamente el ID streaming como
`SHA256(sha_archivo + ':' + número)` y ambas claves Gold como
`MD5(modo + ':' + bronze_record_id)`. Para TM coinciden estación `TM-L1-08` y
timestamp `2026-06-04 09:38:30` entre Raw y Staging. Para MR coinciden `trip_id`
281314 y estaciones de ingreso 7 y salida 2; Staging representa la salida como
`2.0`, numéricamente igual al valor original, sin cambiar el identificador.
No se publican tarjetas ni identidades operacionales en esta evidencia.

Repetir la localización Bronze y el hash Raw desde la raíz:

```powershell
python scripts/trazar_linaje.py Transmetro '11f07ffaf5c061f140e1e178c5aa060ad79b913f6458f6c4a37a9b5bd2ab0659'
python scripts/trazar_linaje.py MetroRiel '23feb4a3a55ce506bf34de5faf7834f9c390b7ca70499cc9fb3ec1c3650ebede:281314'
Get-FileHash -Algorithm SHA256 data/raw/transmetro_validaciones.csv
Get-FileHash -Algorithm SHA256 data/raw/metroriel_viajes.jsonl
```

Seleccionar el registro CSV 34942 con un lector que excluya el encabezado y la
línea JSONL 281314, y comparar sus campos con el payload devuelto por el script.
La comprobación realizada comparó todo el contenido original, no solo los campos
no personales mostrados arriba. Es una prueba de funcionamiento con dos muestras,
no una auditoría exhaustiva de Raw.

## Límites y evidencia

- El universo geográfico y su tipo proceden de código (`silver_universo_zonas`,
  basado en `ZONAS` del generador), sin fila Raw geográfica equivalente.
- Modos, servicios generales MR, cantidades unitarias, tipos de evento, banderas
  temporales y franjas son reglas derivadas; no se inventan campos Raw para ellas.
- Catálogos Gold no conservan identificador físico Bronze. Es posible seguir
  atributos por fuente/código natural, pero no asegurar un enlace físico único
  persistido por fila de dimensión. Usuario y tiempo derivan de conjuntos; no
  representan una única fila Raw. HMAC no demuestra identidad real.
- Marts/vistas son agregados: el DAG y diccionario describen la derivación; los
  hechos contribuyentes permiten el recorrido físico cuando existe
  `bronze_record_id`. No se afirma auditoría exhaustiva de todas las filas Raw.
- `gold_conteos_hechos` y `gold_conteos_modo` reconcilian Gold con Silver;
  `not_null`/`unique` de `bronze_record_id` comprueban identificadores presentes
  y únicos, pero no comprueban por sí solos el contenido del archivo Raw.
  Las pruebas de marts/vistas reconcilian agregados y rankings con sus fuentes.

### Validación local de este bloque

- `python scripts/run_dbt.py parse`: correcto.
- `python scripts/run_dbt.py docs generate`: correcto; creados `manifest.json`,
  `catalog.json` e `index.html` en el directorio ignorado `target/`.
- `python scripts/run_dbt.py test --select path:models/gold --threads 1`:
  **89 pruebas correctas**, `PASS=90`, `WARN=0`, `ERROR=0`, `SKIP=0`, contando
  el hook de proyecto; duración de la validación final dbt **16.21 s**.

No se ejecuta build ni se modifican modelos SQL, métricas o materializaciones.
La documentación es reproducible; generar de nuevo al cambiar modelos o datos.
