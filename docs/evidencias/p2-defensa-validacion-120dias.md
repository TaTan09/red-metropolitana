# Defensa Proyecto 2 — Validación con datos ampliados de 120 días

**Fecha de revisión documental:** 17 de noviembre de 2026.  
**Ejecutor reportado:** Héctor Pérez.  
**Estado:** evidencia de conteos Raw y **comparación de predicciones C verificable por hashes**; la captura de conteos no sustituye el log completo de la ejecución de todas las etapas.

## 1. Conteos observados con la ampliación

La salida aportada por el equipo muestra que el reporte de la corrida conserva como `filas_esperadas` los conteos oficiales del **dataset previo de 90 días**. Es razonable que, al usar fuentes ampliadas a 120 días, el resultado marque `CON_DIFERENCIAS`: **no interpretar ese estado automáticamente como un error de ingesta**, ni sobrescribir la evidencia histórica anterior para hacer que coincida.

| Fuente | Referencia anterior (90 días) | Conteo capturado (120 días) | Incremento |
|---|---:|---:|---:|
| aerometro_boardings.csv | 387,053 | 524,860 | +137,807 |
| am_estaciones.csv | 14 | 14 | 0 |
| cdc_padron_usuarios.csv | 77,636 | 102,749 | +25,113 |
| metroriel_viajes.jsonl | 590,844 | 799,374 | +208,530 |
| mr_estaciones.csv | 22 | 22 | 0 |
| tm_estaciones.csv | 104 | 104 | 0 |
| transmetro_validaciones.csv | 713,786 | 971,206 | +257,420 |
| transurbano_transacciones.csv | 1,635,788 | 2,206,559 | +570,771 |
| tu_paradas.csv | 328 | 328 | 0 |

**Procedencia:** captura de salida de consola enviada por Héctor al equipo. El reporte indica `filas_cargadas` a partir de los Parquet Bronze, y presenta conteos Raw iguales a esos valores. No se ha adjuntado a Git el log integral de la reconstrucción ni el comando inicial completo; conservarlos localmente y registrarlos si están disponibles.

## 2. Predicciones del corte C con el escenario ampliado

Comando de inferencia **observado en la captura** (PowerShell, desde el clon de prueba `red-metropolitana-120d`):

```powershell
.venv\Scripts\python.exe predecir.py --datos datos_red\entrada-120d --fecha-corte 2026-08-30 --salida datos_red\predicciones-c-120d.csv
Get-FileHash datos_red\p2-24-predicciones-c.csv -Algorithm SHA256
Get-FileHash datos_red\predicciones-c-120d.csv -Algorithm SHA256
```

Salida informada por `predecir.py`:

- **76,420 predicciones** para C.
- **10,412 contactos** marcados.
- SHA-256 de la nueva salida y del CSV entregado:  
  `dfa5126bcb3c67962090016fc55c6d39d9936a3f17aeb2b95224cc26d4e2ed59`.

El hash coincide también con el `csv_sha256` ya publicado en [la evidencia original de C](p2-24-predicciones-c.json). La igualdad de hashes respalda **igualdad exacta de bytes** entre los dos CSV comparados, no solo concordancia aproximada en métricas.

**Límite de esta constatación:** se observaron el comando de inferencia, las salidas y los hashes en capturas proporcionadas por el equipo. Los registros no permiten certificar por sí solos cada paso del pipeline de dos horas, por lo que no se afirma que una auditoría independiente haya reproducido toda la ingesta desde Raw. Para fortalecer la demostración, registrar el comando de ingesta y la señal de finalización exitosa desde el entorno de prueba.

## 3. Estado para el cierre

- [x] Datos ampliados: conteos Raw/Bronze capturados con referencia histórica separada.
- [x] Resultado de inferencia del corte C con la carpeta ampliada y archivo generado por separado.
- [x] CSV original y ampliado comparados con SHA-256 idéntico.
- [ ] Agregar, si está disponible, comando y log/resumen final de la reconstrucción completa de 120 días, sin modificar métricas históricas.
- [ ] Confirmar el estado definitivo de `main` y crear etiqueta **`entrega-final` antes de grabar**.
- [ ] Grabar demostración con los **datos de 90 días** especificados en los lineamientos: `git log -1`, `predecir.py --datos <carpeta> --fecha-corte 2026-08-30`, comparación del CSV y ficha del modelo, en una sola toma de 3–5 minutos.
- [ ] Publicar el enlace del video en el README y entregarlo en Moodle.

**No reejecutar la evaluación de B ni reentrenar para la demostración.** La comparación de C se realiza con el modelo y el umbral previamente congelados.
