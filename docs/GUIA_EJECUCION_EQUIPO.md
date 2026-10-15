# Guía de ejecución del equipo: desde cero

Referencia: `main`, revisado el 14 de octubre de 2026. Sigue el orden desde una terminal situada en la raíz del repositorio.

## 1. Qué vas a conseguir

Clonar el proyecto, preparar Python y `.env`, copiar los nueve Raw, iniciar PostgreSQL/Kafka, ejecutar el flujo completo y abrir el dashboard final. **Los datos Raw no están versionados en GitHub**: solicita el paquete oficial al equipo.

El pipeline de datos es multiplataforma: Docker, PostgreSQL, dbt y Prefect pueden ejecutarse en Windows, Linux y macOS, con instalaciones compatibles. La guía prioriza **Windows 10/11 + PowerShell**; sólo cambia de bloque donde se indique. Después de activar el entorno, los comandos `python ...`, Git y Docker son comunes.

Tableau Desktop requiere un sistema compatible, Windows o macOS según su versión. Los pasos del dashboard se validaron principalmente en Windows. En Linux puedes ejecutar todo el pipeline; para visualizar el TWBX puedes necesitar otra máquina compatible con Tableau Desktop. Consulta los [sistemas compatibles de Tableau](https://www.tableau.com/products/techspecs).

## 2. Requisitos previos

- Git y Python de 64 bits, compatible con [requirements.txt](../requirements.txt). El repo no fija una versión exacta de Python; el entorno local revisado usa 3.13.3, sin convertirla en requisito obligatorio.
- [Docker Desktop](https://docs.docker.com/get-started/get-docker/) iniciado y configurado para contenedores Linux en Windows/macOS. En Linux también puedes usar Docker Engine con el plugin Compose.
- Docker Compose, invocable como `docker compose`.
- Los nueve archivos Raw originales y espacio para Raw, Parquet Bronze y la base persistente.
- Tableau Desktop instalado y con acceso de uso, para el paso de visualización. No necesitas instalar PostgreSQL ni Kafka directamente en el equipo: los aporta Compose.

**Windows:**

```powershell
git --version
python --version
docker --version
docker compose version
```

**Linux/macOS:** mismos comandos, sustituyendo la comprobación inicial de Python por `python3 --version`. La versión de Docker Desktop/Engine y sus requisitos dependen de tu sistema; revisa su instalador oficial.

## 3. Clonar y usar main

```powershell
git clone https://github.com/TaTan09/red-metropolitana.git
cd red-metropolitana
git checkout main
git pull origin main
```

Estos comandos son iguales en Linux/macOS. Mantén esta carpeta como directorio de trabajo para los pasos siguientes.

## 4. Crear y activar Python

**Windows:**

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```

Si PowerShell bloquea `Activate.ps1`, permite scripts sólo en la sesión actual y vuelve a activar:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy RemoteSigned
.\.venv\Scripts\Activate.ps1
```

El alcance `Process` termina al cerrar la terminal; no cambies políticas de todo el sistema. Si una política institucional lo impide, usa `.\.venv\Scripts\python.exe` en lugar de `python` en los comandos siguientes. [Referencia de Microsoft](https://learn.microsoft.com/en-us/powershell/module/microsoft.powershell.security/set-executionpolicy).

**Linux/macOS, con bash/zsh:**

```bash
python3 -m venv .venv
source .venv/bin/activate
```

Debe aparecer `(.venv)` al inicio de la terminal. Desde aquí, **en ambos sistemas**, `python` debe ser el del entorno activado:

```powershell
python -c "import sys; print(sys.executable)"
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
```

La ruta impresa debe apuntar a `.venv`. Si falla una dependencia, revisa el error y la compatibilidad de tu Python antes de continuar.

## 5. Configurar .env privado

En un clon nuevo, copia la plantilla una sola vez; si ya tienes `.env`, edítalo sin sobrescribirlo.

**Windows:**

```powershell
Copy-Item .env.example .env
```

**Linux/macOS:**

```bash
cp .env.example .env
```

Abre `.env` con tu editor y sustituye las plantillas:

| Variable | Qué configurar |
|---|---|
| `POSTGRES_DB` | Conserva `red_metropolitana`: el script de seguridad comprueba este nombre. |
| `POSTGRES_USER` | `red_user` es el administrador local del pipeline, no la cuenta del dashboard. |
| `POSTGRES_PASSWORD` | Contraseña privada del administrador PostgreSQL. |
| `POSTGRES_HOST` | `localhost` si Python y Docker corren en el mismo equipo. |
| `POSTGRES_PORT` | Puerto publicado del equipo; la plantilla usa `5432`. Si está ocupado, elige uno libre y úsalo también en Tableau. |
| `GOLD_PSEUDONYM_KEY` | Clave privada estable de al menos 32 bytes para HMAC de usuarios Gold. No dejar `REEMPLAZAR_...`. |
| `TABLEAU_RO_PASSWORD` | Contraseña privada de al menos 16 caracteres para habilitar LOGIN de `tableau_ro`. La plantilla `REEMPLAZAR_...` se rechaza. |

Genera valores locales con Python; **no copies su salida al repositorio ni a un chat**:

```powershell
python -c "import secrets; print('POSTGRES_PASSWORD=' + secrets.token_urlsafe(32)); print('GOLD_PSEUDONYM_KEY=' + secrets.token_hex(32)); print('TABLEAU_RO_PASSWORD=' + secrets.token_urlsafe(32))"
```

Pega las tres líneas generadas en tu `.env`, reemplazando sus plantillas. Cada compañero puede tener sus propias contraseñas y clave local. Conserva la clave HMAC entre corridas de esa instalación: cambiarla cambia los identificadores Gold. **`.env` nunca se sube a Git**; ya está ignorado. No compartas `dbt/target` ni logs sin revisarlos: el SQL compilado puede contener la clave.

## 6. Copiar los nueve Raw

Coloca el paquete oficial, sin renombrar ni regenerar sus datos, directamente en `data/raw/`:

1. `transmetro_validaciones.csv`
2. `transurbano_transacciones.csv`
3. `metroriel_viajes.jsonl`
4. `aerometro_boardings.csv`
5. `cdc_padron_usuarios.csv`
6. `tm_estaciones.csv`
7. `tu_paradas.csv`
8. `mr_estaciones.csv`
9. `am_estaciones.csv`

`generar_red_metropolitana.py` **no es uno de los nueve Raw**. `datos_red/` es una ruta histórica/local; el flujo oficial lee `data/raw/`. Otras escalas o archivos regenerados pueden no reconciliar con los conteos aprobados.

**Windows:** comprueba los nombres con `Get-ChildItem data/raw -File | Select-Object Name`. **Linux/macOS:** usa `ls data/raw/`. Luego ejecuta la validación común:

```powershell
python scripts/validar_raw.py
```

Debe informar nueve archivos, conteos/esquemas correctos y estado `OK`. Genera `docs/metricas/inventario_raw.json` y `.md`. Corrige cualquier faltante o nombre incorrecto antes de continuar; no incluyas archivos extra, salvo `.gitkeep`.

## 7. Iniciar PostgreSQL y Kafka

```powershell
docker compose up -d
docker compose ps
```

Espera a ver `red_metropolitana_postgres` **healthy** y `red_metropolitana_kafka` **running/Up**. Kafka no declara healthcheck en este Compose. Su puerto local es `9092`; PostgreSQL publica el valor de `POSTGRES_PORT` hacia el puerto interno del contenedor. `shm_size: "1gb"` ya está configurado para PostgreSQL.

La base vive en el volumen persistente `postgres_data`; detener los contenedores no equivale a borrar la base.

> **No ejecutes `docker compose down -v` si quieres conservar la base: elimina los volúmenes.** Para detener los servicios conservándolos puedes usar `docker compose stop`.

## 8. Comprobar PostgreSQL

Con los nombres por defecto de `.env`:

```powershell
docker exec -it red_metropolitana_postgres psql -U red_user -d red_metropolitana
```

Si cambiaste `POSTGRES_USER`, sustituye `red_user`. Este comando entra al contenedor y no depende del puerto externo. Dentro de `psql`:

```text
\dn
\q
```

Con `\dn` deben aparecer `staging`, `silver`, `gold` y `control`; `\q` sale. Los esquemas se inicializan al crear el volumen por primera vez; todavía no tienen por qué contener modelos dbt.

## 9. Ejecutar el proyecto completo con Prefect

Con `.venv` activo, `.env` listo, Raw validado y ambos servicios disponibles:

```powershell
python orchestration/flows/fase1_pipeline.py --evidence-prefix 006-equipo
```

El prefijo debe ser nuevo: también sirven `006-hector`, `006-alejandro` o `007-prueba`. La CLI aborta si un destino existe. No reutilices 003/005 ni uses `--overwrite` para una demostración normal.

El flujo hace **Raw → Bronze → Staging → Silver → Gold → validaciones**, repite la corrida y compara idempotencia. Incluye streaming Kafka, Batch, CDC y dbt build con pruebas; Prefect inicia su servidor temporal local, sin configurar Prefect Cloud. Puede tardar varios minutos: espera a que termine, no ejecutes otra copia en paralelo.

Al completarse, debe indicar **IGUALES; referencia Gold: OK**, sin error de ejecución. Con ese prefijo crea en `docs/evidencias/`:

```text
006-equipo-corrida-1.json
006-equipo-corrida-2.json
006-equipo-idempotencia.md
```

Los JSON guardan conteos, fingerprints y el resumen real de dbt; el total incluye modelos/hook y pruebas, no sólo pruebas. Excluye del fingerprint únicamente `fecha_proceso` del puente y `fecha_deteccion` de cuarentena, auditoría dependiente de ejecución.

Si falla la segunda corrida y ya existe la primera, corrige el problema y usa el mismo prefijo con `--resume-second`. Si también existen la segunda o el reporte, revisa esos resultados antes de decidir cómo continuar; no sobrescribas evidencia a ciegas. Las ingestas actualizan reportes auxiliares de `docs/metricas`: revisa ese diff antes de compartir cambios y preserva las evidencias históricas.

## 10. Validaciones rápidas después del flujo

Comprueba que hay relaciones Silver/Gold; este comando usa el administrador por defecto:

```powershell
docker exec -it red_metropolitana_postgres psql -U red_user -d red_metropolitana -c "select table_schema, table_name from information_schema.tables where table_schema in ('silver','gold') order by 1,2;"
```

Busca `silver.silver_features_usuario`, `gold.fact_abordajes`, `gold.fact_viajes_metroriel` y las seis vistas `v_tableau_*`. **Abordajes TM/TU/AM y viajes completos MetroRiel tienen granos distintos**.

Estas comprobaciones son opcionales si el flujo terminó correctamente; no requieren repetir toda la ingesta:

```powershell
python scripts/run_dbt.py parse
python scripts/run_dbt.py test --threads 1
python scripts/run_dbt.py docs generate
python -m unittest discover -s tests -v
```

El wrapper carga `.env` y el perfil PostgreSQL del proyecto. Los tests Python usan fixtures/mocks, sin requerir Kafka/PostgreSQL para probar la CLI. dbt Docs queda en `dbt/red_metropolitana/target/`, ignorado por Git. La evidencia de referencia [005](evidencias/005-idempotencia-final-fase2.md) documenta la corrida final aprobada; [003](evidencias/003-idempotencia-flujo-completo.md) es histórica de Fase 1.

## 11. Habilitar tableau_ro después de crear Gold

```powershell
python scripts/configurar_tableau_ro.py
```

Lee `TABLEAU_RO_PASSWORD` de tu `.env`/entorno, habilita LOGIN y concede lectura Gold y permisos por defecto del propietario para futuras relaciones. Sin esa variable crea NOLOGIN; con la plantilla o una contraseña corta falla. No usar `red_user` para el dashboard. Más detalles en [seguridad de tableau_ro](seguridad/tableau_ro.md).

## 12. Abrir Tableau y ajustar las cinco conexiones

Abre con Tableau Desktop el archivo `tableau/workbook/Red_Metropolitana_Fase2.twbx`. Fue guardado con Tableau 2026.2.1 en Windows: comprueba la compatibilidad de tu versión, sin tratar esa versión exacta como un requisito del pipeline.

### Driver PostgreSQL

**Si Tableau muestra “Driver required” o “Missing Driver”**, sigue el enlace del aviso al [driver oficial recomendado para tu versión y sistema](https://www.tableau.com/support/drivers), seleccionando PostgreSQL. El [conector PostgreSQL](https://help.tableau.com/current/pro/desktop/en-us/examples_postgresql.htm) requiere un driver instalado; que falte o deba instalarse manualmente depende del equipo, no del repo. No se presupone instalación automática ni copia manual universal.

Si las instrucciones de ese driver JDBC indican copiar un `.jar`, la ruta habitual en Windows es `C:\Program Files\Tableau\Drivers`. Para macOS, la [documentación JDBC general de Tableau](https://help.tableau.com/current/pro/desktop/en-us/jdbc_tableau.htm) indica `/Library/JDBC` o `~/Library/JDBC`; confirma la carpeta en las instrucciones del driver y versión concretos, sin reutilizar la ruta de Windows. Tras instalar/copiar, **cierra Tableau Desktop completamente y vuelve a abrirlo**. No versiones el driver en el repositorio.

### Conexión local

El TWBX contiene cinco conexiones PostgreSQL. Para **cada fuente**, entra en **Data Source / Fuente de datos → Edit Connection / Editar conexión** y configura:

| Campo | Valor en la computadora que acabas de preparar |
|---|---|
| Servidor | `localhost`, si PostgreSQL corre en ese mismo equipo |
| Base | `red_metropolitana` |
| Puerto | El `POSTGRES_PORT` de tu `.env`; no un valor universal |
| Usuario | `tableau_ro` |
| Contraseña | Tu `TABLEAU_RO_PASSWORD` privada |

La copia actual conserva **5433**, mientras que la plantilla `.env` usa **5432**: ajústalo si no coincide. Repite el acceso en las cinco fuentes y comprueba que el dashboard carga. Es normal que Tableau vuelva a pedir credenciales al abrir el TWBX: **no guardes la contraseña dentro del paquete que se comparte o versiona**. Consulta [cómo editar fuentes](https://help.tableau.com/current/pro/desktop/en-us/howto_connect.htm).

**Pipeline en Linux y Tableau en otra máquina:** el servidor debe ser el nombre/IP accesible del equipo que ejecuta PostgreSQL, con acceso de red autorizado y su puerto publicado; `localhost` apuntaría a la máquina equivocada. Usa la contraseña de `tableau_ro` configurada en el equipo de la base. La conectividad y la instalación de Tableau/driver se verifican en esa máquina compatible; no se validaron aquí para cada sistema operativo.

## 13. Qué debes ver en el dashboard

Abre **“Red Metropolitana - Análisis de movilidad”**. El workbook incluye demanda horaria y por zona de abordajes, cobertura, zona sin cobertura, demanda del trazado/viajes por hora MetroRiel, multimodalidad y usuarios por cantidad de modos. Con los datos oficiales, la referencia aprobada incluye **70,380 usuarios observados**, **36,827 multimodales (52.33 %)** y Santa Catarina Pinula sin cobertura catalogada.

TM/TU/MR se vinculan por identidad numérica inferida académicamente; Aerómetro queda aislado y no permite medir usuarios compartidos persona-a-persona con otros modos. La vista `v_tableau_transbordos` es un análisis adicional de pares inferidos: el TWBX no necesita usarla. No modifiques hojas o cálculos para conseguir que cambien los conteos.

## 14. Solución de problemas

| Problema | Qué revisar |
|---|---|
| `ModuleNotFoundError: psycopg` u otra dependencia | Activa `.venv` y ejecuta `python -m pip install -r requirements.txt`; confirma `sys.executable`. |
| PostgreSQL no aparece healthy | `docker compose ps` y `docker compose logs postgres`; espera el arranque o corrige el error mostrado. |
| Kafka no está disponible | Comprueba `docker compose logs kafka` y que el puerto `9092` esté disponible; no repitas el flujo mientras el broker arranca. |
| Puerto PostgreSQL ocupado | Cambia `POSTGRES_PORT` en `.env` a uno libre, vuelve a levantar Compose y actualiza también las cinco conexiones Tableau. |
| Contraseña PostgreSQL rechazada con un volumen previo | Las variables de inicialización no cambian usuarios/contraseñas de una base ya existente; recupera la configuración de esa base. No borres el volumen para probar. |
| Tableau pide contraseña al abrir | Introduce tu contraseña privada de `tableau_ro`; es esperado que no esté almacenada. |
| Tableau indica driver requerido | Instala el driver adecuado siguiendo el aviso y reinicia Tableau por completo. |
| El prefijo de evidencia ya existe | Usa uno nuevo; conserva 003/005 y las demostraciones anteriores. |
| Faltan Raw / inventario REVISAR | Confirma los nueve nombres exactos en `data/raw/`, sin extras ni archivos regenerados de otra escala. |
| `tableau_ro` sin LOGIN o plantilla rechazada | Reemplaza `TABLEAU_RO_PASSWORD` por tu valor privado de al menos 16 caracteres y ejecuta su script después del build. |

## 15. Checklist de equipo

- [ ] Repo clonado y main actualizado.
- [ ] `.venv` activo y requirements instalados.
- [ ] `.env` privado creado, plantillas reemplazadas y clave HMAC conservada.
- [ ] Nueve Raw en `data/raw/`, inventario OK.
- [ ] Docker iniciado, Kafka running y PostgreSQL healthy.
- [ ] Esquemas comprobados y pipeline terminado sin errores.
- [ ] Nuevas evidencias generadas: IGUALES y referencia Gold OK.
- [ ] Silver/Gold presentes y `tableau_ro` configurado con LOGIN.
- [ ] Tableau/driver compatibles y cinco conexiones con el puerto local correcto.
- [ ] Workbook abre y dashboard carga sin guardar contraseñas en él.

Al compartir avances, revisa `git status --short`: no agregues `.env`, datos, drivers ni artefactos dbt. Esta guía documenta el procedimiento; no sustituye comprobar la instalación y apertura de Tableau en cada computadora.
