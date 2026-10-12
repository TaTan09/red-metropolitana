# Guia tecnica de permisos Tableau

## Provisionar `tableau_ro`

Ejecutar al terminar las materializaciones dbt, sin builds concurrentes: una tabla creada antes del GRANT/default privileges pero intercambiada despues puede requerir reaplicar el provisionamiento.

`sql/security/tableau_ro.sql` concede CONNECT a `red_metropolitana`, USAGE Gold, SELECT sobre tablas/vistas Gold actuales y default privileges para futuras relaciones creadas por el propietario ejecutor de dbt. No otorga acceso a Staging/Silver/control. El script aborta si el rol ya tiene privilegios elevados, membresías o accesos heredados incompatibles, sin revocar derechos de otros usuarios. No cambia permisos PUBLIC.

```powershell
python scripts/configurar_tableau_ro.py
```

Sin `TABLEAU_RO_PASSWORD` crea un rol **NOLOGIN**, con permisos provisionados y probables mediante SET ROLE. Para habilitar conexión, suministrar una contraseña privada de al menos 16 caracteres en esa variable de entorno y ejecutar de nuevo; se transmite usando composición SQL segura, nunca se imprime ni escribe en un archivo versionado. No pasar contraseñas por línea de comandos ni guardarlas en el script SQL. Si ya existe un rol LOGIN y no se suministra contraseña, conserva ese estado sin rotación.

La concesión es a **todo Gold**, incluyendo hechos seudonimizados y el mart con filas de identidad, no sólo agregados. La recomendación operativa para el tablero es usar vistas. Default privileges cubre al propietario que ejecuta el script; otro propietario futuro necesita provisionamiento equivalente. Las verificaciones finales comprueban acceso actual, denegación en otras capas y herencia SELECT en una tabla Gold temporal que se elimina por rollback.


Estado de la ejecucion local y verificaciones: `docs/metricas/validacion_fase2.json`. La conexion del workbook sigue en red_user y no se modifica en esta revision.
