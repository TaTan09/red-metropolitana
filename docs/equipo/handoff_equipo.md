# Handoff del equipo — Proyecto 1 Red Metropolitana

## Estado común listo

La base compartida del proyecto ya incluye:

- estructura Git y repositorio;
- entorno Python;
- Docker;
- PostgreSQL;
- Kafka;
- validación de los nueve archivos Raw;
- ingesta Batch a Bronze;
- streaming Transmetro a Bronze;
- streaming Aerómetro a Bronze;
- CDC Raw → Bronze → Staging;
- pruebas de idempotencia de las cargas implementadas;
- contrato de tablas Staging;
- reconstrucción Bronze → Staging validada;
- modelos Silver y reglas de calidad en dbt;
- SCD Tipo 2 e identidad documentada;
- modelo dimensional Gold con seis dimensiones y dos hechos;
- Prefect para el flujo completo;
- evidencia de dos corridas finales idempotentes de extremo a extremo en [005](../evidencias/005-idempotencia-final-fase2.md), con 003 histórica conservada;
- cuatro marts y seis vistas Gold, features por identidad y documentación de gobernanza/seguridad;
- workbook final versionado en `tableau/workbook/Red_Metropolitana_Fase2.twbx`;
- 70,380 usuarios observados, 36,827 multimodales (52.33 %); 1,393,448 abordajes TM/TU/AM y 295,511 viajes MR; Santa Catarina Pinula sin cobertura catalogada.

## Reparto de trabajo

### Hector — Ingesta, Staging y Orquestación

La rama de integración implementa `Bronze Parquet → Staging` y permite reconstruir las 13 tablas del contrato mediante `python scripts/cargar_tablas_base_pg.py`.

Debe crear/reconstruir:
- `staging.tm_estaciones`
- `staging.tu_paradas`
- `staging.mr_estaciones`
- `staging.am_estaciones`
- `staging.transmetro_validaciones`
- `staging.transurbano_transacciones`
- `staging.metroriel_viajes`
- `staging.aerometro_boardings`
- `staging.usuarios_transurbano_min`
- `staging.usuarios_metroriel_min`
- `staging.usuarios_aerometro_min`

También se reconstruyen:
- `staging.cdc_registro_ambiguo`
- `staging.padron_transmetro_actual`

Criterios:
- Staging se reconstruye desde Bronze.
- No eliminar datos malos en Staging.
- Mantener conteos y evidencia de idempotencia.
- Documentar los usuarios únicos de TU, MR y AM.
- Prefect/orquestación del flujo completo está implementada y validada en `orchestration/flows/fase1_pipeline.py`.
- 003 es evidencia histórica de Fase 1; la validación completa final está en `docs/evidencias/005-idempotencia-final-fase2.md`.
- Nuevas demostraciones requieren `--evidence-prefix`, por ejemplo `006-defensa`; no sobrescribir evidencia existente. Resume usa el mismo prefijo y conserva la primera corrida.

### Alejandro — dbt, Silver, Calidad y SCD2

Silver consume `sources` del contrato de Staging. El historial SCD Tipo 2 se deriva de cada evento CDC, ordenado por `seq`.

Responsabilidades:
- fechas normalizadas;
- dinero en GTQ;
- Aerómetro UTC → hora local;
- zona conformada;
- reglas de calidad;
- cuarentena con motivo;
- duplicados de Transmetro;
- parada nula de Transurbano;
- fecha futura de Transurbano;
- viaje MetroRiel sin salida;
- SCD Tipo 2 del padrón;
- estrategia de identidad / puente de identidad.

No debe cambiar la interfaz Staging sin coordinarlo.

### Jonatán — Diseño dimensional, Gold y Tableau

La rama `feature/gold-dimensional` implementa las seis dimensiones y los dos hechos acordados. El diseño, DDL y métricas están en `docs/arquitectura/modelo_dimensional_gold.md`, `sql/ddl/gold_model.sql` y `docs/metricas/gold_metricas.md`. Tableau está implementado y versionado en `tableau/workbook/Red_Metropolitana_Fase2.twbx`, con cuatro marts y seis vistas Gold disponibles; el TWBX referencia cinco, dejando v_tableau_transbordos como análisis adicional.

Responsabilidades:
- declarar granos;
- matriz del bus;
- diagrama dimensional;
- DDL preliminar;
- dimensiones conformadas;
- `fact_abordajes`;
- `fact_viajes_metroriel`;
- clasificación de medidas;
- dimensión tiempo con día hábil y hora pico;
- materializaciones dimensionales Gold exclusivamente desde Silver;
- mantener las seis vistas Gold disponibles para Tableau y separar abordajes de viajes MR.

## Dependencias

Flujo principal:

Raw → Bronze → Staging → Silver → Gold → Tableau

Hector publica Staging.
Alejandro consume Staging y publica Silver.
Jonatán consume Silver y publica Gold.

Esto no impide trabajo paralelo: Alejandro puede construir la estructura dbt antes de que todas las tablas Staging estén listas, y Jonatán puede diseñar Gold antes de que Silver esté materializado.

## Regla de integración

Antes de hacer merge:
- correr pruebas relevantes;
- revisar conteos;
- no subir `.env`;
- no subir archivos Raw/Bronze;
- mantener commits pequeños y descriptivos;
- comunicar cualquier cambio al contrato de datos.


## Cierre y pendientes manuales

TM/TU/MR comparten una identidad numérica inferida académicamente; Aerómetro permanece aislado y no permite medir enlaces persona-a-persona con otros modos. No presentar el 52.33 % como prevalencia real de personas de toda la red.

La migración manual a tableau_ro está completada: el usuario validó la conexión, guardó y reabrió el workbook. El XML confirma cinco conexiones PostgreSQL tableau_ro, sin contraseñas/token guardados, y la base confirma LOGIN y lectura Gold con denegación Staging/Silver. Revalidar permisos al cambiar de entorno; el procedimiento está en `docs/seguridad/tableau_ro.md`. No se editó binariamente el ZIP durante la comprobación. La defensa oral y su ensayo completo siguen pendientes. La nueva definición Docker asigna 1 GB de shared memory; aplicarla después conservando el volumen.
