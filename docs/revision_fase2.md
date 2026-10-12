# Reporte integral de revision/correccion de Alejandro

Fecha: 12 de octubre de 2026 (America/Guatemala). Rama: `feature/fase2-jonatan`. Base aprobada: `f64a23e8ca89eddc2d39cee482f73f4d645fbe03`. Trabajo revisado: `a4a8112c9e0b438ab0b8d6117d2c4b4ece65287e`.

**Estado listo para revision:** correcciones en working tree, todas las pruebas finales pasan. El checkout inicial estaba en f64a23e, no en a4a8112; se descargo el commit de Alejandro y se recuperaron sus archivos sin mover HEAD. Sus datasets se conservaron localmente; se omitieron sus sobrescrituras historicas. No hubo checkout de otra rama, reset, rebase ni reconstruccion de commits.

## 1. Problemas encontrados

- Nueve archivos Raw agregados a Git por Alejandro; ocho evidencias historicas sobrescritas en ese commit.
- Transbordos usados como sustituto de usuarios multimodales; secuencia sin desempate y clave dependiente de timestamps, sin ambos IDs Bronze.
- Cutoff de marzo inexistente y sin filtro SQL; faltaban ventanas, recencia, hora pico y modo/zona frecuentes.
- Gobernanza equiparaba viajes completos MR con abordajes, publicaba una ventana contradictoria y una consulta sobre tablas inexistentes; faltaban dueños y reglas de calidad.
- Seguridad atribuia a Silver un hash salteado inexistente y mencionaba DuckDB; permisos Tableau declarados como si ya fueran restrictivos.
- Inventario validaba pero no agregaba resultados existentes a la lista; OK con tabla vacia y ruta privada.
- Nuevos modelos/campos ausentes del diccionario/linaje, schema Gold redundante y bloque Markdown sin cierre.
- Adicionales corregidos: definicion MAU recurrente sin implementacion, retencion descrita como aplicada/obligacion legal, afirmacion universal de marts agregados y documento de seguridad demasiado extenso para el resumen solicitado por el enunciado.

## 2. Archivos creados (24)

- `dbt/red_metropolitana/models/gold/mart_multimodalidad.sql`
- `dbt/red_metropolitana/models/gold/v_tableau_multimodalidad.sql`
- `dbt/red_metropolitana/models/gold/vistas/v_tableau_transbordos.sql`
- `dbt/red_metropolitana/models/silver/schema.yml`
- `dbt/red_metropolitana/models/silver/silver_features_usuario.sql`
- `dbt/red_metropolitana/tests/mart_multimodalidad_reglas.sql`
- `dbt/red_metropolitana/tests/mart_multimodalidad_secuencia.sql`
- `dbt/red_metropolitana/tests/silver_features_usuario_integridad.sql`
- `dbt/red_metropolitana/tests/silver_features_usuario_reconciliacion.sql`
- `dbt/red_metropolitana/tests/v_tableau_multimodalidad_reconciliacion.sql`
- `dbt/red_metropolitana/tests/v_tableau_multimodalidad_sin_identidad.sql`
- `dbt/red_metropolitana/tests/v_tableau_transbordos_reconciliacion.sql`
- `docs/features_usuario.md`
- `docs/gobernanza/definiciones_oficiales.md`
- `docs/metricas/validacion_fase2.json`
- `docs/metricas/validacion_fase2.md`
- `docs/revision_fase2.md`
- `docs/seguridad/seguridad_y_datos_personales.md`
- `docs/seguridad/tableau_ro.md`
- `scripts/configurar_tableau_ro.py`
- `scripts/verificar_fase2.py`
- `sql/security/tableau_ro.sql`
- `sql/utilities/eventos_movilidad_mes.sql`
- `tests/test_validar_raw.py`

## 3. Archivos modificados (12)

- `.gitignore`
- `README.md`
- `dbt/red_metropolitana/models/gold/schema.yml`
- `docs/arquitectura/marts_gold.md`
- `docs/decisiones/002-fase2-marts.md`
- `docs/evidencias/003-idempotencia-flujo-completo.md`
- `docs/gobernanza/diccionario_gold.md`
- `docs/gobernanza/linaje_dbt.md`
- `docs/metricas/inventario_raw.json`
- `docs/metricas/inventario_raw.md`
- `docs/metricas/rendimiento_fase2.md`
- `scripts/validar_raw.py`

Las modificaciones a modelos Gold aprobados se limitan a ampliar schema.yml: se comprobo que las descripciones y pruebas de sus 15 modelos originales son identicas como estructura YAML. No se edito SQL aprobado de Hector/Jonatan ni la macro HMAC. `gold.yml` de Alejandro se consolido en schema.yml, conservando sus pruebas y ampliando documentacion; no se integra el archivo redundante.

## 4. Evidencias identicas a f64a23e

Al partir de la base aprobada se conservaron sin recuperar encima las versiones sobrescritas de Alejandro. Comparacion de bytes contra `git show f64a23e:archivo`: todas identicas; diff vacio.
- `docs/metricas/cdc_metricas.json`
- `docs/metricas/cdc_metricas.md`
- `docs/metricas/ingesta_batch_bronze.json`
- `docs/metricas/ingesta_batch_bronze.md`
- `docs/metricas/streaming_aerometro_consumer.json`
- `docs/metricas/streaming_aerometro_consumer.md`
- `docs/metricas/streaming_transmetro_consumer.json`
- `docs/metricas/streaming_transmetro_consumer.md`

Transmetro historico conserva 363,221 consumidos, 363,211 nuevos y 10 repeticiones tecnicas. No se reejecutaron ingestas que reemplazaran esas evidencias.

## 5. Multimodalidad

`gold.v_tableau_multimodalidad` agrega dim_usuario por modos_observados y metodo_identidad; no expone usuario_sk. Tiene las siete columnas solicitadas. Multimodal = modos_observados >1. Reconciliacion completa por grupo y totales, incluyendo unimodales + multimodales = observados; prueba de ausencia de identificadores individuales en la vista.

Tableau: SUM(usuarios) para distribucion, MAX/MIN de totales repetidos y porcentaje global para KPI. No SUM del KPI y no denominarlo porcentaje filtrado cuando se filtran grupos. La vista resume todo el periodo y no ofrece filtros de personas por hora/zona.

## 6. mart_multimodalidad

Una fila por par consecutivo de una identidad inferida en modos distintos, separado por >0 y <=90 minutos. LAG ordena fecha_hora, modo, bronze_record_id. La clave MD5 usa usuario_sk y los IDs Bronze origen/destino; ambos se preservan. MR aporta ingreso de viaje completo. Pruebas not_null/unique, modos distintos, intervalo, clave, bandera, secuencia completa contra hechos y todos los campos/grupos de v_tableau_transbordos.

Se denomina transbordo inferido: el generador no confirma una cadena puerta-a-puerta y proximidad temporal no demuestra transferencia fisica. Sumar tarifas de pares puede contar un evento en dos pares y no es recaudo.

## 7. silver_features_usuario

Tabla exclusivamente Silver, una fila por usuario_canonico_id con eventos disponibles. 25 columnas documentadas en SQL/YAML/Markdown. Conserva features utiles y agrega ventanas 7/30/90 dias, modo_mas_usado, dias_desde_ultimo_evento, proporcion_eventos_hora_pico y zona_origen_frecuente. Empates: conteo DESC y nombre ASC. Pico: lunes-viernes, horas 06/07/08/17/18/19. Zonas del punto TM/TU/AM y origen MR; fallback ZONA_DESCONOCIDA si falta catalogo. No usa Gold.

Resultado real: 70,380 filas, 70,380 IDs unicos, 0 nulos en las 25 columnas, 36,827 es_multimodal=true. MR cuenta viajes completos; los demas, abordajes. Uso predictivo documentado: inactividad futura de una identidad enlazable, con etiquetas posteriores al corte y validacion temporal.

## 8. Cutoff real

Minimo global **2026-06-01 04:00:00**. Maximo/cutoff **2026-07-15 23:44:33**, local Guatemala UTC-6; incluye salida MR. Maximo de eventos de abordaje/ingreso sin salidas: 2026-07-15 22:59:56. El SQL calcula y guarda el corte real; filtra fecha_evento <=cutoff y salida MR <=cutoff, evitando usar un viaje antes de su cierre. Puede fijarse con features_cutoff para repetir un snapshot. Ventanas: (cutoff -N dias, cutoff].

## 9. Limite exacto de Aerometro

`AM-<hash>` no enlaza persona-a-persona con `USR-<numero inferido>` TM/TU/MR. Aerometro puede contarse localmente, pero no medir sus usuarios compartidos ni sus transbordos con otros modos. PostgreSQL devuelve 0 pares incluye_aerometro=true; no se forzo el resultado. No equivale a cero personas transferidas. Los 14,496 IDs HASH_AISLADO se incluyen en el universo; el 52.33% describe multimodalidad observable, no prevalencia real de personas de toda la red. Tambien TM/TU/MR son una inferencia academica de identidad.

## 10. Gobernanza

Definiciones separadas de abordaje, viaje MR, evento registrado, usuario observado/activo en periodo, multimodal y transbordo inferido. Se elimino la consulta ficticia y se agrego SQL canonico de julio 2026; diferencia granos y aclara que julio esta incompleto. Dueños para los nueve dominios solicitados y autorizacion/versionado de cambios. Calidad describe condiciones y acciones implementadas DUPLICADO_TORNIQUETE, COD_PARADA_NULO, FECHA_FUTURA y VIAJE_SIN_EXIT en Silver, con ID hacia Raw; no se inventaron reglas. Se declara el limite real de parseo de fechas/horas y el umbral TU fijo de calidad.

## 11. Seguridad y RBAC

Silver tiene identidad canonica enlazable; Gold aplica HMAC-SHA256 con GOLD_PSEUDONYM_KEY. No anonimizar por afirmacion, no SHA salteado Silver, no DuckDB. Matriz RBAC y retencion de 12 meses como politica objetivo, no purga ni mandato legal aplicado. Resumen de decisiones en seguridad_y_datos_personales.md y guia operativa separada tableau_ro.md.

tableau_ro provisionado sin contraseña ni LOGIN; CONNECT, USAGE Gold, SELECT sobre todas las 18 relaciones actuales y default privileges del propietario red_user. Verificados SELECT futuro mediante tabla de prueba revertida, SET ROLE, lectura Gold y denegacion Staging/Silver. Sin privilegios elevados ni membresias. Script transaccional aborta ante roles/ACL incompatibles, sin cambiar otros usuarios ni PUBLIC. Con contraseña externa TABLEAU_RO_PASSWORD puede habilitarse LOGIN; esto y el cambio manual de conexion Tableau siguen pendientes. El workbook usa red_user y se conserva intacto. El rol cubre todo Gold, incluidos hechos seudonimizados; no se afirma que restrinja a agregados solamente.

## 12. Inventario Raw

Causa: faltaba results.append(result) en la rama de archivos presentes. Reparado; tambien se comprueban llaves JSONL en todas las filas, falta de directorio produce resultados ERROR y OK requiere inventario completo no vacio. Se añade --raw-dir para validar datos_red sin mover/borrar fuentes. Regeneracion real: 9 archivos, todos con registros esperados, bytes/MB, esquema/conteo y SHA-256; sin ruta personal absoluta. Tres pruebas de regresion pasan.

| Archivo | Registros |
|---|---:|
| tm_estaciones.csv | 104 |
| tu_paradas.csv | 328 |
| mr_estaciones.csv | 22 |
| am_estaciones.csv | 14 |
| transmetro_validaciones.csv | 363,221 |
| transurbano_transacciones.csv | 832,791 |
| metroriel_viajes.jsonl | 299,100 |
| aerometro_boardings.csv | 203,554 |
| cdc_padron_usuarios.csv | 31,050 |

## 13. Markdown/YAML

Cerrados los bloques SQL de gobernanza y movido pg_column_size dentro del bloque PowerShell de rendimiento sin alterar cifras historicas. Silver usa data_tests conservando las pruebas previas y ampliandolas. Schemas consolidados, 18 modelos Gold y 197 campos; catalogo PostgreSQL y documentacion coinciden exactamente. Todos los bloques Markdown de los archivos intervenidos cierran.

## 14. dbt parse

Final: codigo 0, 6.382 s de proceso; sin errores. Comando: `python scripts/run_dbt.py parse`.

## 15. dbt docs generate

Final: codigo 0, 9.808 s de proceso; catalogo con 18 modelos Gold/197 columnas. Se regeneraron manifest.json, catalog.json e index.html en target ignorado. No publicarlos sin revisar contenido HMAC compilado.

## 16. Builds

| Corrida | Resultado | Tiempo dbt |
|---|---|---:|
| Inicial con dependencias | PASS=104, ERROR=1, SKIP=28; cancelado el modelo lento de features | 445.73 s |
| Corregido: cuatro modelos | PASS=72 (4 modelos +67 pruebas +hook), sin errores/warnings/skips | 53.85 s |
| Repeticion incluyendo bridge/cuarentena | PASS=74 (6 modelos +67 pruebas +hook), sin errores/warnings/skips | 63.50 s |

Comando inicial: `python scripts/run_dbt.py build --select +silver_features_usuario +mart_multimodalidad v_tableau_transbordos +v_tableau_multimodalidad --threads 1`. Dependencias se rematerializaron desde sus SQL aprobados sin editar su logica. Tras corregir el plan se construyeron los cuatro modelos usando las dependencias actualizadas.

Error inicial: `canceling statement due to user request`, provocado al cancelar una consulta cuyo plan hacia nested loop costoso por estimaciones de rn=1. Se cambio a DISTINCT ON con mismo desempate; features se materializo en 13.95 s, 70,380 filas.

Otras incidencias resueltas: Docker detenido y acceso localhost bloqueado en sandbox (iniciado/verificado con permisos de ejecucion); lectura pypdf inicial con Python incorrecto/codificacion cp1252 (usado entorno virtual UTF-8); load_dotenv sin ruta en stdin (ruta explicita); pruebas de inventario con temporales fuera del workspace (movidas a target ignorado); verificacion RBAC inicial durante reconstruccion del hecho perdio la concesion en ese objeto (reaplicada despues del build; default futuro verificado); auditoria inicial asumio raw_json en Batch CSV (usa ahora sus columnas texto reales). Estos intentos no se presentan como verificaciones correctas. La captura de evidencia final no tiene fallos pendientes.

## 17. Pruebas Silver

`test --select path:models/silver --indirect-selection cautious --threads 1`: 28 PASS, 0 errores, 21.80 s; PASS de consola 29 incluye hook. SCD2 referencia fuentes Staging y queda fuera de cautious: ejecutados explicitamente padron_scd2_integridad y padron_scd2_intervalos, 2 PASS, 1.57 s, consola PASS=3 con hook. Total relevante Silver: **30 pruebas correctas**.

## 18. Pruebas Gold

`python scripts/run_dbt.py test --select path:models/gold --threads 1`: **128 pruebas PASS**, 0 errores/warnings/skips, 28.31 s. PASS=129 en consola incluye hook. Contiene todas las pruebas aprobadas y nuevas de clave, secuencia, reconciliacion y ausencia de identidad individual en la vista.

## 19. Metricas finales e idempotencia

| Metrica | Valor real |
|---|---:|
| Filas features / identidades unicas | 70,380 / 70,380 |
| Nulos en cualquier columna de features | 0 |
| Gold usuarios observados | 70,380 |
| Gold multimodales | 36,827 |
| Gold unimodales | 33,553 |
| Porcentaje multimodal | 52.33% |
| 1 / 2 / 3 modos (Silver y Gold) | 33,553 / 26,831 / 9,996 |
| HASH_AISLADO / PATRON_NUMERICO_INFERIDO | 14,496 / 55,884 |
| Pares inferidos | 41,565 |
| Tiempo minimo / maximo / promedio en minutos | 0.02 / 90.00 / 42.343430 |
| Pares con Aerometro | 0 |
| Eventos ventanas 7 / 30 / 90 dias | 264,871 / 1,132,630 / 1,688,959 |
| Julio: abordajes / viajes MR / eventos registrados | 468,037 / 100,275 / 568,312 |

| Combinacion inferida | Pares |
|---|---:|
| Transurbano -> Transmetro | 9,585 |
| Transmetro -> Transurbano | 9,581 |
| MetroRiel -> Transurbano | 7,933 |
| Transurbano -> MetroRiel | 7,651 |
| Transmetro -> MetroRiel | 3,447 |
| MetroRiel -> Transmetro | 3,368 |

Reconciliacion completa de ambas vistas y conteos contra modelos fuente: correcta. Prueba mensual ejecutada dos veces: identica. Un par Transurbano -> MetroRiel auditado hasta Bronze y dos registros Raw, hash y payload coincidentes; no se afirma auditoria exhaustiva.

Dos builds corregidos conservan conteos y fingerprints de contenido en features, mart, vistas, dim_usuario, bridge y cuarentena. Se excluyen solo fecha_proceso y fecha_deteccion de sus respectivas tablas; no igualdad byte a byte de auditoria. Pruebas de claves y reglas verificadas en ambos builds. La evidencia historica Prefect se conserva y se aclara su alcance; no se reejecuto el flujo completo de ingesta en esta revision. Ver validacion_fase2.json para resultados individuales y fingerprints.

## 20. Estado Git completo

HEAD sigue en f64a23e; rama original conservada. 24 archivos nuevos marcados con intent-to-add para que aparezcan en diff; no hay contenido staged (`git diff --cached --name-status` vacio). Los Raw de a4a8112 no se agregaron al indice y datos_red esta ignorado. El workbook permanece untracked, fuera de la lista de commit.

```text
 M .gitignore
 M README.md
 A dbt/red_metropolitana/models/gold/mart_multimodalidad.sql
 M dbt/red_metropolitana/models/gold/schema.yml
 A dbt/red_metropolitana/models/gold/v_tableau_multimodalidad.sql
 A dbt/red_metropolitana/models/gold/vistas/v_tableau_transbordos.sql
 A dbt/red_metropolitana/models/silver/schema.yml
 A dbt/red_metropolitana/models/silver/silver_features_usuario.sql
 A dbt/red_metropolitana/tests/mart_multimodalidad_reglas.sql
 A dbt/red_metropolitana/tests/mart_multimodalidad_secuencia.sql
 A dbt/red_metropolitana/tests/silver_features_usuario_integridad.sql
 A dbt/red_metropolitana/tests/silver_features_usuario_reconciliacion.sql
 A dbt/red_metropolitana/tests/v_tableau_multimodalidad_reconciliacion.sql
 A dbt/red_metropolitana/tests/v_tableau_multimodalidad_sin_identidad.sql
 A dbt/red_metropolitana/tests/v_tableau_transbordos_reconciliacion.sql
 M docs/arquitectura/marts_gold.md
 M docs/decisiones/002-fase2-marts.md
 M docs/evidencias/003-idempotencia-flujo-completo.md
 A docs/features_usuario.md
 A docs/gobernanza/definiciones_oficiales.md
 M docs/gobernanza/diccionario_gold.md
 M docs/gobernanza/linaje_dbt.md
 M docs/metricas/inventario_raw.json
 M docs/metricas/inventario_raw.md
 M docs/metricas/rendimiento_fase2.md
 A docs/metricas/validacion_fase2.json
 A docs/metricas/validacion_fase2.md
 A docs/revision_fase2.md
 A docs/seguridad/seguridad_y_datos_personales.md
 A docs/seguridad/tableau_ro.md
 A scripts/configurar_tableau_ro.py
 M scripts/validar_raw.py
 A scripts/verificar_fase2.py
 A sql/security/tableau_ro.sql
 A sql/utilities/eventos_movilidad_mes.sql
 A tests/test_validar_raw.py
?? tableau/workbook/Red_Metropolitana_Fase2.twbx
```

`git check-ignore datos_red/transmetro_validaciones.csv` devuelve esa ruta; `git ls-files datos_red` vacio. Ocho evidencias historicas: diff vacio y bytes iguales. `git diff --check` sin errores. Se ejecutan ademas status completo, diff --stat f64a23e, diff --name-status f64a23e y diff --cached --name-status para la revision final. No se incluyen .env, contraseñas, tokens, target/, logs/, temporales ni rutas personales en el cambio.

## 21. Lista EXACTA para el commit limpio respecto de f64a23e

Estos son los 36 archivos que integrarian el commit limpio (A=nuevo, M=modificado). No incluye datos_red, gold.yml redundante, ocho evidencias protegidas ni workbook. La lista no implica que se haya hecho un commit.

| Estado | Archivo |
|---|---|
| M | `.gitignore` |
| M | `README.md` |
| A | `dbt/red_metropolitana/models/gold/mart_multimodalidad.sql` |
| M | `dbt/red_metropolitana/models/gold/schema.yml` |
| A | `dbt/red_metropolitana/models/gold/v_tableau_multimodalidad.sql` |
| A | `dbt/red_metropolitana/models/gold/vistas/v_tableau_transbordos.sql` |
| A | `dbt/red_metropolitana/models/silver/schema.yml` |
| A | `dbt/red_metropolitana/models/silver/silver_features_usuario.sql` |
| A | `dbt/red_metropolitana/tests/mart_multimodalidad_reglas.sql` |
| A | `dbt/red_metropolitana/tests/mart_multimodalidad_secuencia.sql` |
| A | `dbt/red_metropolitana/tests/silver_features_usuario_integridad.sql` |
| A | `dbt/red_metropolitana/tests/silver_features_usuario_reconciliacion.sql` |
| A | `dbt/red_metropolitana/tests/v_tableau_multimodalidad_reconciliacion.sql` |
| A | `dbt/red_metropolitana/tests/v_tableau_multimodalidad_sin_identidad.sql` |
| A | `dbt/red_metropolitana/tests/v_tableau_transbordos_reconciliacion.sql` |
| M | `docs/arquitectura/marts_gold.md` |
| M | `docs/decisiones/002-fase2-marts.md` |
| M | `docs/evidencias/003-idempotencia-flujo-completo.md` |
| A | `docs/features_usuario.md` |
| A | `docs/gobernanza/definiciones_oficiales.md` |
| M | `docs/gobernanza/diccionario_gold.md` |
| M | `docs/gobernanza/linaje_dbt.md` |
| M | `docs/metricas/inventario_raw.json` |
| M | `docs/metricas/inventario_raw.md` |
| M | `docs/metricas/rendimiento_fase2.md` |
| A | `docs/metricas/validacion_fase2.json` |
| A | `docs/metricas/validacion_fase2.md` |
| A | `docs/revision_fase2.md` |
| A | `docs/seguridad/seguridad_y_datos_personales.md` |
| A | `docs/seguridad/tableau_ro.md` |
| A | `scripts/configurar_tableau_ro.py` |
| M | `scripts/validar_raw.py` |
| A | `scripts/verificar_fase2.py` |
| A | `sql/security/tableau_ro.sql` |
| A | `sql/utilities/eventos_movilidad_mes.sql` |
| A | `tests/test_validar_raw.py` |

## Revision final contra el enunciado

| Punto | Resultado y limite de lo comprobado |
|---|---|
| 2.1 Tableau / multimodalidad | Vista Gold especifica, agregada y reconciliada. Incorporacion manual al workbook queda para el usuario; no se verifico ni modifico el tablero |
| 2.3 Features | Exclusivamente Silver, una fila por identidad, 25 columnas, cutoff real filtrado, diccionario y uso predictivo defendible |
| 3.1 Gobernanza | Definiciones por grano, usuario observado, dueños, calidad real, prueba mensual reproducible, 197 campos/18 modelos y linaje hasta Raw |
| 3.3 Seguridad | HMAC Gold real, no credenciales, matriz/retencion honestas, permisos tableau_ro probados; LOGIN y cambio de conexion manual pendientes. Resumen de decisiones separado de guia tecnica |
| 1.5 Idempotencia | Evidencia historica intacta y dos builds finales comparados por claves, conteos y contenido de negocio; excepciones de auditoria explicitas. Repetir el flujo Prefect completo sigue siendo la demostracion de defensa prevista |

Restricciones cumplidas: Raw preservado, nueve archivos datos_red y data/raw identicos por hash; workbook sin modificar (SHA-256 0cbe3f4cd9026fe973285cc01449cecfb5a98203859a39cd8a0b783fe72c2f74). SQL aprobado de Hector/Jonatan intacto. No se inventaron cifras ni identidad AM.

**No hice commit.**

**No hice push.**

**No reescribi historia Git.**
