# Guia tecnica de permisos Tableau

## Provisionar `tableau_ro`

Ejecutar al terminar las materializaciones dbt, sin builds concurrentes: una tabla creada antes del GRANT/default privileges pero intercambiada despues puede requerir reaplicar el provisionamiento.

`sql/security/tableau_ro.sql` concede CONNECT a `red_metropolitana`, USAGE Gold, SELECT sobre tablas/vistas Gold actuales y default privileges para futuras relaciones creadas por el propietario ejecutor de dbt. No otorga acceso a Staging/Silver/control. El script aborta si el rol ya tiene privilegios elevados, membresías o accesos heredados incompatibles, sin revocar derechos de otros usuarios. No cambia permisos PUBLIC.

```powershell
python scripts/configurar_tableau_ro.py
```

Sin `TABLEAU_RO_PASSWORD` crea un rol **NOLOGIN**, con permisos provisionados y comprobables mediante SET ROLE. Para habilitar conexión, suministrar una contraseña privada de al menos 16 caracteres en esa variable de entorno y ejecutar de nuevo; se transmite usando composición SQL segura, nunca se imprime ni escribe en un archivo versionado. La plantilla `REEMPLAZAR_CON_PASSWORD_SEGURO_DE_16_O_MAS_CARACTERES` se rechaza. Si copias `.env.example`, reemplázala o elimina la línea de `.env` hasta habilitar LOGIN. No pasar contraseñas por línea de comandos ni guardarlas en el script SQL. Si ya existe un rol LOGIN y no se suministra contraseña, conserva ese estado sin rotación.

La concesión es a **todo Gold**, incluyendo hechos seudonimizados y el mart con filas de identidad, no sólo agregados. La recomendación operativa para el tablero es usar vistas. Default privileges cubre al propietario que ejecuta el script; otro propietario futuro necesita provisionamiento equivalente. Las verificaciones finales comprueban acceso actual, denegación en otras capas y herencia SELECT en una tabla Gold temporal que se elimina por rollback.


## Estado comprobado: migración completada

El TWBX versionado contiene **cinco conexiones PostgreSQL**, todas con `username=tableau_ro`, servidor `localhost`, puerto `5433`, base `red_metropolitana`. Referencia v_tableau_demanda_abordajes, v_tableau_demanda_viajes_mr, v_tableau_cobertura, v_tableau_metroriel y v_tableau_multimodalidad. No referencia v_tableau_transbordos. No contiene extractos .hyper ni atributos password/token no vacíos en el XML inspeccionado.

**Confirmación del 12 de octubre de 2026:** el usuario realizó la migración manual, validó la conexión desde Tableau Desktop, guardó y reabrió correctamente el workbook. La revisión automática confirmó los cinco usuarios guardados y el rol con **LOGIN** en PostgreSQL, sin privilegios elevados, con CONNECT, USAGE Gold y SELECT de todas las relaciones Gold actuales. Una consulta con SET ROLE devuelve 70,380 usuarios observados y 36,827 multimodales; Staging/Silver rechazan lectura y carecen de USAGE. Estas comprobaciones no sustituyen la validación interactiva realizada por el usuario.

El cleanup anterior verificó ausencia de CREATE Gold e INSERT/UPDATE/DELETE/TRUNCATE, además de SELECT en una tabla/vista futuras revertidas por rollback. La evidencia histórica `docs/metricas/validacion_fase2.json` describe el estado anterior NOLOGIN y no se modifica retrospectivamente. ADR 002, decisión 5, queda completada. La revisión actual no cambió credenciales ni escribió el TWBX; el cambio binario visible en Git corresponde al guardado manual del usuario.

## Procedimiento para repetir la migración en otro entorno

1. Configura una contraseña privada en `TABLEAU_RO_PASSWORD` en tu entorno o `.env` local, y ejecuta `python scripts/configurar_tableau_ro.py` después de los builds. No copies el placeholder ni guardes el secreto en Git.
2. Abre `tableau/workbook/Red_Metropolitana_Fase2.twbx` en Tableau Desktop. Para cada una de las cinco fuentes con conexión PostgreSQL, abre su pestaña **Fuente de datos / Data Source**, selecciona la conexión y **Editar conexión / Edit Connection**.
3. Conserva servidor, puerto y base del entorno; en esta copia son `localhost`, `5433`, `red_metropolitana`. Usa autenticación de usuario/contraseña, cambia el usuario a `tableau_ro` e introduce la contraseña privada. No cambiar relaciones ni cálculos del dashboard.
4. Repite en todas las conexiones. Para fuentes **Live**, verifica las hojas al consultar; para fuentes con **Extract**, realiza el refresco desde la base usando la nueva cuenta. Un extracto ya almacenado no demuestra permisos de conexión actuales.
5. Guarda desde Tableau con **Archivo → Guardar como / File → Save As**, tipo **Tableau Packaged Workbook (*.twbx)**. Evita incorporar credenciales guardadas al archivo que se versionará. Reabre y verifica las cinco fuentes y las hojas del dashboard.
6. Antes de versionarlo, inspecciona de nuevo el XML del `.twb` dentro del paquete: todas las conexiones PostgreSQL deben indicar `tableau_ro`, sin contraseñas/token; confirma además la prueba de conexión/refresco. Registra la validación del nuevo entorno; ADR 002 ya recoge la migración completada en el entorno actual.

Referencias oficiales: [editar fuentes y conexiones](https://help.tableau.com/current/pro/desktop/en-us/howto_connect.htm), [conector PostgreSQL](https://help.tableau.com/current/pro/desktop/en-us/examples_postgresql.htm) y [guardar un workbook empaquetado](https://help.tableau.com/current/pro/desktop/en-us/save_savework_packagedworkbooks.htm). El TWBX puede incluir datos y valores de filtros; cambiar su conexión no retira automáticamente extractos ya empaquetados. Revisarlos al compartir el archivo.
