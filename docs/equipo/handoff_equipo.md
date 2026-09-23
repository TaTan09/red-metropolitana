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
- evidencia de dos corridas idempotentes de extremo a extremo.

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
- La evidencia de dos corridas idénticas está en `docs/evidencias/003-idempotencia-flujo-completo.md`.

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

La rama `feature/gold-dimensional` implementa las seis dimensiones y los dos hechos acordados. El diseño, DDL y métricas están en `docs/arquitectura/modelo_dimensional_gold.md`, `sql/ddl/gold_model.sql` y `docs/metricas/gold_metricas.md`. Tableau sigue pendiente.

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
- luego materializar Gold exclusivamente desde Silver;
- preparar las vistas/tablas que consumirá Tableau.

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
