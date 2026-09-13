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
- contrato de tablas Staging.

## Reparto de trabajo

### Hector — Ingesta, Staging y Orquestación

Siguiente objetivo inmediato: completar `Bronze → Staging`.

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

Ya existen:
- `staging.cdc_registro_ambiguo`
- `staging.padron_transmetro_actual`

Criterios:
- Staging se reconstruye desde Bronze.
- No eliminar datos malos en Staging.
- Mantener conteos y evidencia de idempotencia.
- Documentar los usuarios únicos de TU, MR y AM.
- Después de cerrar Staging, avanzar con Prefect/orquestación del flujo completo.

### Alejandro — dbt, Silver, Calidad y SCD2

Puede comenzar de inmediato configurando dbt y declarando `sources` sobre las tablas definidas en el contrato de Staging.

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

Puede comenzar con el diseño mientras Silver se desarrolla.

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
