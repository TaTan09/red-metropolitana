# Contexto compartido — Proyecto 1 de Ciencia de Datos
## Agencia Metropolitana de Transporte

**Versión:** 1.2
**Estado:** Fase 1 y Fase 2 implementadas; defensa pendiente
**Fecha de actualización:** 12 de octubre de 2026

> Este documento debe compartirse entre Hector, Alejandro y Jonatán, y puede enviarse a las herramientas de IA que cada integrante utilice.  
> Su propósito es mantener un contexto común, evitar soluciones incompatibles y dejar por escrito las decisiones ya tomadas por el grupo.

## Estado actual de implementación

La Fase 1 y la Fase 2 están implementadas e integradas en main:

- Raw → Bronze Parquet por Batch, Kafka y CDC; Bronze → 13 tablas Staging PostgreSQL;
- Silver/dbt con normalización, cuarentena, identidad inferida, SCD2 y features por usuario;
- Gold con seis dimensiones, dos hechos, cuatro marts y seis vistas Tableau;
- dashboard versionado en `tableau/workbook/Red_Metropolitana_Fase2.twbx`;
- diccionario/linaje, definiciones oficiales, dueños, calidad, seguridad y retención documentados;
- flujo Prefect completo ejecutado dos veces en la evidencia 005: IGUALES y referencia Gold OK;
- validación final dbt: consola PASS=189; el artefacto recuperado del segundo build respalda 158 pruebas PASS +30 modelos success +1 hook success.

Resultados aprobados: **70,380 usuarios observados**, **36,827 multimodales (52.33 %)**, **1,393,448 abordajes TM/TU/AM**, **295,511 viajes completos MetroRiel**, y **Santa Catarina Pinula sin cobertura catalogada**. No se equiparan abordajes con viajes puerta-a-puerta ni ausencia catalogada con ausencia de transporte real.

TM/TU/MR se enlazan por patrón numérico como inferencia académica, no identidad personal demostrada. Aerómetro conserva `AM-<hash>` aislado: su multimodalidad persona-a-persona con otros modos no puede medirse; cero enlaces observables no prueba cero transferencias físicas.

[003](docs/evidencias/003-idempotencia-flujo-completo.md) conserva la validación histórica de Fase 1; [005](docs/evidencias/005-idempotencia-final-fase2.md) es la corrida completa final del proyecto/Fase 2. La nueva CLI exige `--evidence-prefix` para futuras demostraciones y rechaza sobrescribir destinos por defecto. El [README](README.md) documenta su uso y los límites de la evidencia antigua.

Seguridad técnica: HMAC-SHA256 antes de Gold y permisos `tableau_ro` provisionados; las cinco conexiones del workbook ya usan `tableau_ro`, con LOGIN verificado; el usuario validó la conexión, guardó y reabrió el archivo. La defensa no está completada. Las secciones de Sprint 0 mantienen sus decisiones como antecedentes; el estado vigente prevalece sobre redacciones históricas en futuro.

---

# 1. Equipo

| Integrante | Carnet | Responsabilidad principal |
|---|---:|---|
| Hector Pérez | 1304223 | Ingesta, Bronze, CDC, orquestación e idempotencia |
| Alejandro Gil | 1187420 | Silver, integración, calidad, cuarentena, features y gobernanza |
| Jonatán Chávez | 1185023 | Diseño dimensional, Gold, DDL, diagramas e integración del tablero |

## Responsabilidades compartidas

Los tres integrantes deben conocer y poder explicar:

- arquitectura completa;
- matriz del bus;
- grano de las tablas de hechos;
- estrategia de identidad;
- reglas de calidad;
- CDC;
- Gold;
- Tableau;
- idempotencia;
- decisiones de gobernanza y seguridad.

**Importante:** durante la defensa oral cualquier integrante debe poder explicar cualquier parte del proyecto.

---

# 2. Fuentes oficiales

El proyecto se basa en:

1. `Proyecto 1 Red Metropolitana (1).pdf` — enunciado oficial.
2. `generar_red_metropolitana(1).py` — generador entregado por el docente.
3. Los nueve archivos de datos producidos/entregados para el proyecto.

Cuando exista una ambigüedad entre el enunciado y el generador:

- no se debe ocultar;
- no se debe “corregir” silenciosamente;
- se debe documentar;
- se debe tomar una decisión defendible;
- el dato original siempre debe conservarse en Bronze.

---

# 3. Objetivo general

El proyecto simula una futura **Agencia Metropolitana de Transporte** que necesita integrar información de:

1. Transmetro
2. Transurbano
3. MetroRiel
4. Aerómetro

Los operadores no comparten:

- llaves de usuario;
- formatos de fecha;
- representación de zonas;
- unidades monetarias;
- definición exacta de una fila.

El objetivo es construir una plataforma de datos que permita responder con evidencia:

> **¿La red integrada de transporte resuelve el problema de movilidad y dónde no?**

---

# 4. Inventario de datos recibido

| Archivo | Tipo | Operador | Registros |
|---|---|---|---:|
| `tm_estaciones(1).csv` | Catálogo | Transmetro | 104 |
| `tu_paradas(1).csv` | Catálogo | Transurbano | 328 |
| `mr_estaciones(1).csv` | Catálogo | MetroRiel | 22 |
| `am_estaciones(1).csv` | Catálogo | Aerómetro | 14 |
| `transmetro_validaciones.csv` | Operación | Transmetro | 363,221 |
| `transurbano_transacciones.csv` | Operación | Transurbano | 832,791 |
| `metroriel_viajes.jsonl` | Operación | MetroRiel | 299,100 |
| `aerometro_boardings(1).csv` | Operación | Aerómetro | 203,554 |
| `cdc_padron_usuarios(1).csv` | CDC | Registro ambiguo / padrón | 31,050 |

Los archivos pesados no deben revisarse manualmente fila por fila. Deben procesarse mediante scripts reproducibles.

---

# 5. Hallazgos iniciales medidos en los archivos reales

Estas cifras ya fueron observadas en los datos entregados y deben conservarse como referencia para las reglas de calidad.

## 5.1 Transmetro

Total:

- **363,221 filas**

Duplicados de torniquete:

- **2,230 filas** pertenecen a grupos duplicados.
- Esto representa aproximadamente **0.614%** del archivo.
- Si se conserva una copia válida de cada evento, existen **1,115 copias adicionales** que deben considerarse duplicados sobrantes.
- Las 1,115 copias sobrantes representan aproximadamente **0.307%** del archivo.

### Convención recomendada

Para el reporte de calidad se deben distinguir dos métricas:

- `filas_involucradas_en_duplicados = 2,230`
- `duplicados_sobrantes = 1,115`

Para cuarentena/deduplicación, se conserva una fila del evento y se separan las **1,115 copias adicionales**.

---

## 5.2 Transurbano

Total:

- **832,791 filas**

Hallazgos:

- **4,189 filas sin `cod_parada`**
- porcentaje aproximado: **0.503%**
- **817 filas con fecha futura**
- porcentaje aproximado: **0.098%**

Estas condiciones serán reglas explícitas de calidad en Silver.

---

## 5.3 MetroRiel

Total:

- **299,100 viajes**

Viajes sin salida:

- **3,589**
- porcentaje aproximado: **1.200%**

Los viajes sin `exit` no deben eliminarse silenciosamente. Deben quedar trazables y clasificarse según la regla de calidad definida.

---

## 5.4 CDC

Total:

- **31,050 operaciones**

Distribución por operación:

| Operación | Cantidad |
|---|---:|
| INSERT | 10,800 |
| UPDATE | 16,200 |
| DELETE | 4,050 |
| **Total** | **31,050** |

Distribución observada por formato de llave:

| Tipo de llave | Cantidad |
|---|---:|
| Transmetro `TC-########` | 22,326 |
| Transurbano `##########` | 5,223 |
| MetroRiel `MR#######` | 1,295 |
| `SIN-TARJETA` | 2,206 |
| Aerómetro | **0** |

### Hallazgo importante

No existe ninguna tarjeta/hash de Aerómetro dentro del CDC.

El generador utiliza prioridad:

```text
Transmetro → Transurbano → MetroRiel → SIN-TARJETA
```

y no utiliza la llave de Aerómetro para el campo `tarjeta`.

Esto limita la resolución de identidad entre Aerómetro y los demás sistemas.

---

# 6. Arquitectura acordada

La arquitectura general será:

```text
FUENTES
   ↓
INGESTA
   ↓
RAW
   ↓
BRONZE / DATA LAKE
   ↓
STAGING
   ↓
SILVER
   ↓
GOLD
   ↓
TABLEAU
```

Adicionalmente:

```text
SILVER
   ↓
FEATURES PARA CIENCIA DE DATOS
```

## Reglas obligatorias

1. **Gold nunca lee directamente de Bronze.**
2. Los registros inválidos no se descartan silenciosamente.
3. Los registros malos deben quedar en cuarentena o con trazabilidad equivalente.
4. Bronze conserva el dato recibido y se acumula.
5. Staging puede vaciarse/reconstruirse.
6. Las features salen de Silver, no de Gold.
7. El pipeline debe ser idempotente.
8. La llave del usuario debe seudonimizarse antes de Gold.
9. No se almacenan credenciales reales en Git.
10. Las métricas del tablero deben poder rastrearse hasta los datos crudos.

---

# 7. Tecnologías acordadas

| Componente | Decisión |
|---|---|
| Streaming | Kafka en Docker |
| Raw | Archivos originales |
| Bronze | Data Lake local + Parquet particionado |
| Staging | PostgreSQL |
| Silver | PostgreSQL + dbt |
| Gold | PostgreSQL + dbt |
| CDC | Procesamiento del archivo proporcionado |
| Orquestación | Prefect |
| Visualización | Tableau |
| Versionamiento | Git / GitHub |
| Contenedores | Docker / Docker Compose |

## Razón para PostgreSQL

Se eligió PostgreSQL sobre DuckDB porque:

- facilita una arquitectura cliente-servidor;
- funciona bien con dbt;
- puede ser consumido por Prefect;
- es apropiado para conectar Tableau;
- representa mejor un warehouse compartido por varios usuarios;
- puede levantarse de forma reproducible con Docker.

---

# 8. Sprint 0 — decisiones oficiales

## 8.1 Matriz del bus

Borrador acordado:

| Proceso | Usuario | Tiempo | Zona | Punto de transporte | Modo | Línea/Ruta/Eje | Destino |
|---|:---:|:---:|:---:|:---:|:---:|:---:|:---:|
| Validaciones Transmetro | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Transacciones Transurbano | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |
| Viajes MetroRiel | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ |
| Abordajes Aerómetro | ✓ | ✓ | ✓ | ✓ | ✓ | ✓ | — |

Dimensiones conformadas previstas:

- Usuario
- Tiempo
- Zona
- Punto de transporte
- Modo
- Servicio / Línea / Ruta / Eje

MetroRiel además conserva origen y destino.

---

## 8.2 Grano

Se decidió utilizar **dos tablas de hechos principales**.

### `fact_abordajes`

Grano:

> **Una fila representa un evento operativo válido de acceso/abordaje de un usuario en un punto de transporte y momento determinados.**

Incluye:

- Transmetro
- Transurbano
- Aerómetro

### `fact_viajes_metroriel`

Grano:

> **Una fila representa un viaje completo de MetroRiel realizado por un usuario desde una estación de origen hasta una estación de destino.**

Esto evita:

- inventar destinos para sistemas que no los proporcionan;
- perder la información de origen/destino de MetroRiel.

---

# 9. Estrategia de identidad

No existe una tabla oficial que relacione las llaves de los cuatro operadores.

Los formatos principales son:

```text
Transmetro   TC-00012345
Transurbano  0000012345
MetroRiel    MR0012345
Aerómetro    hash de 12 caracteres
```

## Decisión

En Silver está materializado el puente de identidad:

```text
bridge_identidad_usuario
```

Campos implementados:

- `usuario_canonico_id`
- `sistema_origen`
- `llave_origen`
- `metodo_match`
- `nivel_confianza`
- `fecha_proceso`

## TM ↔ TU ↔ MR

En el dataset académico existe un patrón numérico observable que puede utilizarse como **aproximación de identidad** entre:

- Transmetro
- Transurbano
- MetroRiel

Ejemplo:

```text
TC-00012345
0000012345
MR0012345
      ↓
usuario canónico inferido
```

### Regla de gobernanza

Esta relación debe documentarse como:

> **Identidad inferida para el dataset académico, no como prueba de identidad real.**

Nunca se debe afirmar que el patrón demostraría identidad en un sistema productivo real.

## Aerómetro

Aerómetro conserva una identidad independiente porque:

- utiliza un hash;
- no existe tabla de correspondencia;
- no aparece dentro del CDC;
- no hay evidencia oficial que permita unir su llave con otro operador.

### Consecuencia

La multimodalidad persona-a-persona de Aerómetro con los otros modos no puede medirse con las llaves disponibles. Un cero observable no demuestra ausencia real de transferencias.

---

# 10. Definición de multimodalidad

No se debe afirmar:

> “X personas reales utilizan varios operadores”

porque la identidad entre operadores no está demostrada.

La métrica implementada se define como:

> **Usuario multimodal identificable/inferido:** identidad canónica que, bajo la estrategia documentada de resolución de identidad, presenta actividad en al menos dos modos.

La métrica puede cubrir principalmente combinaciones entre:

- Transmetro
- Transurbano
- MetroRiel

Aerómetro debe reportarse con la limitación correspondiente.

### Implicación para Tableau

La vista `gold.v_tableau_multimodalidad` responde la pregunta obligatoria con `modos_observados > 1`; el tablero debe comunicar que se trata de:

**multimodalidad observable/inferida bajo las reglas del proyecto**.

---

# 11. Contradicción del CDC y decisión oficial

Existe una contradicción intencional:

## Enunciado

El PDF solicita construir el padrón vigente de **Transmetro** y afirma que los otros operadores no tienen padrón.

## Generador

El generador mezcla dentro de `tarjeta` identificadores de:

- Transmetro
- Transurbano
- MetroRiel
- `SIN-TARJETA`

y lo describe como una ambigüedad deliberada.

## Decisión del grupo

No se escogerá una interpretación ignorando la otra.

### Bronze

Se conservan **las 31,050 operaciones completas**, exactamente como llegaron.

### Staging

Se crea un modelo conceptual como:

```text
stg_cdc_registro_ambiguo
```

que preserva la naturaleza mixta del archivo.

### Padrón solicitado de Transmetro

A partir del registro ambiguo se deriva:

```text
stg_padron_transmetro_actual
```

utilizando llaves con patrón:

```text
TC-########
```

### Otras llaves

Las llaves:

- Transurbano
- MetroRiel
- `SIN-TARJETA`

se conservan y documentan.

No se utilizarán para inventar atributos de los catálogos de otros operadores.

Los catálogos mínimos de usuario para Transurbano, MetroRiel y Aerómetro se construirán desde sus archivos operativos, como pide el enunciado.

---

# 12. Reglas del CDC

El CDC debe procesarse por:

```text
seq ASC
```

Operaciones:

```text
INSERT
UPDATE
DELETE
```

## DELETE

Un DELETE:

- no elimina físicamente al usuario;
- marca la tarjeta como inactiva;
- conserva el historial.

Si aparece un DELETE y no existe cuerpo previo visible dentro de la ventana observada:

- se conserva la llave;
- `estado = INACTIVA`;
- los atributos no conocidos quedan como `NULL`;
- no se inventan perfil ni zona.

## Diferencia entre Staging y SCD Tipo 2

### Staging

Mantiene el padrón vigente:

```text
stg_padron_transmetro_actual
```

### Silver

Historiza cambios mediante SCD Tipo 2.

---

# 13. Ingesta por fuente

| Fuente | Vía decidida |
|---|---|
| Validaciones Transmetro | Streaming / Kafka |
| Boardings Aerómetro | Streaming / Kafka |
| Transacciones Transurbano | **Batch** |
| Viajes MetroRiel | Batch |
| Catálogos | Batch |
| Padrón / CDC | CDC |

## Decisión sobre Transurbano

Se utilizará **Batch**.

### Justificación

Aunque las transacciones ocurren continuamente, el escenario se modelará como una entrega periódica de un archivo consolidado del operador.

Ventajas:

- menor complejidad operacional;
- reprocesamiento sencillo;
- mejor control de idempotencia;
- adecuado para un tablero analítico/histórico.

### Consecuencia

La información de Transurbano tendrá más latencia que las fuentes de streaming.

Esto deberá declararse en la documentación.

---

# 14. Raw y Bronze

## Raw

Conservará exactamente los archivos originales.

Ejemplo:

```text
data/raw/
```

No se aplican transformaciones.

## Bronze

Se implementará como **Data Lake local** usando:

- carpetas;
- Parquet;
- partición por fecha de ingesta.

Ejemplo:

```text
data/bronze/
├── transmetro/
│   └── fecha_ingesta=YYYY-MM-DD/
├── transurbano/
├── metroriel/
├── aerometro/
├── catalogos/
└── cdc/
```

## Regla de Bronze

Cambiar el formato físico a Parquet no significa aplicar reglas de negocio.

NO se debe hacer en Bronze:

```text
Z10 → Zona 10
130 centavos → Q1.30
UTC → hora local
```

Estas transformaciones pertenecen a Silver.

---

# 15. Calidad y cuarentena

Las reglas conocidas inicialmente incluyen:

| Fuente | Problema | Tratamiento esperado |
|---|---|---|
| Transmetro | Duplicado de torniquete | conservar una fila válida y registrar copia adicional |
| Transurbano | `cod_parada` nulo | cuarentena / regla documentada |
| Transurbano | fecha futura | cuarentena / regla documentada |
| MetroRiel | viaje sin salida | cuarentena o tratamiento explícito documentado |
| CDC | llave fuera del dominio esperado de TM | preservar como parte del registro ambiguo y documentar |

Estas reglas están implementadas en Silver/dbt y documentadas en las definiciones oficiales.

Nada se elimina silenciosamente.

---

# 16. Dimensiones y Gold implementadas

Dimensiones implementadas:

```text
dim_usuario
dim_tiempo
dim_zona
dim_punto_transporte
dim_modo
dim_servicio
```

Hechos:

```text
fact_abordajes
fact_viajes_metroriel
```

Gold solo puede construirse desde Silver.

---

# 17. Tableau

El tablero debe responder al menos:

1. demanda por modo, zona y hora;
2. cobertura: zonas con y sin servicio;
3. multimodalidad observable/inferida;
4. caso MetroRiel en zonas 12, 8, 1, 6 y 17.

El tablero final está versionado en `tableau/workbook/Red_Metropolitana_Fase2.twbx` y consume cinco de las seis vistas Gold disponibles; v_tableau_transbordos queda como análisis adicional no referenciado en el TWBX actual. Sus cinco conexiones PostgreSQL usan `tableau_ro`; la migración manual fue validada por el usuario, con guardado y reapertura correctos, y confirmada mediante lectura del XML.

## Reparto del tablero

### Hector

- demanda por modo/zona/hora;
- cobertura.

### Alejandro

- multimodalidad / usuarios que utilizan más de un sistema.

### Jonatán

- análisis de MetroRiel;
- integración del dashboard final.

---

# 18. Features

Las features deben salir de **Silver**, nunca de Gold.

Entidad:

> una fila por usuario.

Features implementadas en `silver.silver_features_usuario`:

- eventos de movilidad registrados en los últimos 7 días;
- eventos de movilidad registrados en los últimos 30 días;
- eventos de movilidad registrados en los últimos 90 días;
- modo más usado;
- cantidad de modos;
- días desde último viaje;
- proporción en hora pico;
- zona de origen frecuente;
- gasto acumulado;
- gasto promedio.

Cutoff real aplicado: **2026-07-15 23:44:33**, hora local Guatemala, incluyendo salida MR; eventos y viajes cerrados se filtran hasta ese instante. Una fila por identidad, 70,380 filas. Ver `docs/features_usuario.md` para las 25 columnas y sus límites.

---

# 19. Estructura del repositorio

```text
red-metropolitana/
│
├── README.md
├── CONTEXTO_PROYECTO_1_CIENCIA_DATOS.md
├── .gitignore
├── .env.example
├── docker-compose.yml
│
├── data/
│   ├── raw/
│   │   └── .gitkeep
│   ├── bronze/
│   │   └── .gitkeep
│   └── quarantine/
│       └── .gitkeep
│
├── ingestion/
│   ├── batch/
│   ├── streaming/
│   ├── cdc/
│   └── common/
│
├── dbt/
│   └── red_metropolitana/
│       ├── models/
│       │   ├── staging/
│       │   ├── silver/
│       │   └── gold/
│       ├── tests/
│       ├── seeds/
│       └── macros/
│
├── orchestration/
│   └── flows/
│
├── sql/
│   ├── ddl/
│   └── utilities/
│
├── tableau/
│   ├── workbook/
│   └── exports/
│
├── docs/
│   ├── arquitectura/
│   ├── decisiones/
│   ├── gobernanza/
│   ├── seguridad/
│   ├── metricas/
│   └── evidencias/
│
├── scripts/
└── tests/
```

---

# 20. Git y reproducibilidad

No se debe realizar un único commit al final.

Ejemplos de commits adecuados:

```text
feat: crea carga batch de catalogos
feat: agrega productor kafka de transmetro
feat: implementa procesamiento cdc
feat: normaliza zonas en silver
test: agrega reglas de calidad dbt
feat: crea fact_abordajes
docs: documenta estrategia de identidad
```

Los archivos pesados de datos y los archivos generados no deben subirse al repositorio.

---

# 21. Seguridad

## `.env.example`

Sí se sube.

Debe contener únicamente nombres de variables, por ejemplo:

```text
POSTGRES_DB=red_metropolitana
POSTGRES_USER=TU_USUARIO
POSTGRES_PASSWORD=TU_PASSWORD
POSTGRES_HOST=localhost
POSTGRES_PORT=5432
```

## `.env`

NO se sube.

Debe agregarse a `.gitignore`.

## Gold

Gold aplica HMAC-SHA256 al ID canónico Silver mediante `GOLD_PSEUDONYM_KEY`; Silver conserva un ID enlazable y no aplica SHA-256 salteado a tarjetas. `tableau_ro` sólo recibe permisos Gold, con contraseña externa opcional; el workbook ya usa tableau_ro y su migración manual está validada. Ver `docs/seguridad/seguridad_y_datos_personales.md`.

Tableau no necesita conocer las tarjetas originales.

---

# 22. Métricas que deben medirse durante el desarrollo

## Volumen

- filas ingeridas por fuente;
- filas que llegan a Silver;
- filas en Gold.

## Calidad

- registros por regla de calidad;
- porcentaje por regla;
- duplicados detectados;
- registros en cuarentena.

## CDC

- INSERT;
- UPDATE;
- DELETE;
- tarjetas activas antes/después.

## Rendimiento

- duración de cada etapa;
- tamaño de Raw;
- tamaño de Bronze;
- tamaño de warehouse;
- tiempo de consulta del tablero.

## Idempotencia

```text
Primera corrida → conteos
Segunda corrida → mismos conteos
```

## Cobertura

- zonas con servicio;
- zonas sin servicio.

## Multimodalidad

- usuarios inferidos que utilizan más de un modo;
- limitaciones de cobertura de identidad.

---

# 23. División de trabajo consolidada

## Hector — Ingesta / Bronze / CDC / Orquestación

Responsabilidades principales:

- Docker y servicios de ingesta;
- productores y consumidores Kafka;
- carga Batch;
- Raw;
- Bronze;
- procesamiento inicial CDC;
- padrón vigente de Transmetro;
- Prefect;
- pruebas de idempotencia;
- métricas de ingesta.

## Alejandro — Silver / Calidad / Features / Gobernanza

Responsabilidades principales:

- modelos Staging/Silver en dbt;
- normalización de fechas;
- normalización monetaria;
- zonas conformadas;
- calidad;
- cuarentena;
- SCD Tipo 2;
- bridge de identidad;
- features;
- diccionario y gobernanza.

## Jonatán — Gold / Modelo dimensional / Tableau

Responsabilidades principales:

- dimensiones conformadas;
- dos tablas de hechos;
- matriz del bus final;
- DDL;
- diagrama dimensional;
- Gold;
- clasificación de medidas;
- Tableau;
- integración visual del dashboard.

---

# 24. Reglas para cualquier IA que colabore

Cualquier IA que reciba este documento debe respetar estas reglas:

1. No cambiar decisiones del Sprint 0 sin indicarlo.
2. No inventar columnas que no existen.
3. No inventar relaciones entre usuarios.
4. Distinguir identidad real de identidad inferida.
5. No afirmar que Aerómetro puede unirse a otros usuarios si no hay evidencia.
6. Mantener: `Fuente → Raw → Bronze → Staging → Silver → Gold`.
7. Gold nunca lee Bronze.
8. Las features salen de Silver.
9. Los malos registros no se eliminan silenciosamente.
10. No hardcodear credenciales.
11. Producir código reproducible.
12. Explicar dónde guardar cada archivo creado.
13. Mantener idempotencia.
14. Documentar cualquier ambigüedad.
15. Priorizar el enunciado y los archivos oficiales.
16. Cuando enunciado y generador entren en tensión, preservar ambas evidencias y explicar la decisión tomada.
17. No presentar la estrategia de patrón numérico TM/TU/MR como identidad real.
18. No cambiar el grano sin revisar el impacto en Gold y Tableau.

---

# 25. Estado del proyecto

## Implementado y validado

- Ingesta por vías, Bronze Parquet, reconstrucción Staging y CDC.
- Silver: normalización, cuarentena, SCD2, puente de identidad y tabla de features.
- Gold: seis dimensiones, dos hechos, cuatro marts y seis vistas finales.
- Tableau final versionado, con demanda, cobertura, multimodalidad y caso MetroRiel.
- Gobernanza: diccionario de 18 modelos/197 campos, definiciones, dueños, reglas y linaje.
- Seguridad: HMAC Gold, credenciales fuera de Git, matriz de roles y retención; tableau_ro con LOGIN y permisos Gold verificados, migración del workbook completada.
- Prefect completo: dos corridas finales iguales en 005 y referencia Gold OK; 003 histórica preservada.
- Cleanup de reproducibilidad: prefijo obligatorio, no sobrescritura por defecto, resumen dbt automático y cobertura ampliada para nuevas evidencias.

## Pendientes manuales

- Aplicar posteriormente shm_size de PostgreSQL recreando sólo el contenedor y preservando el volumen; no se ejecutó esa recreación durante el cleanup.
- Preparar y realizar la defensa oral, incluida la demostración completa con un prefijo nuevo. **Defensa pendiente**.
- Opcionalmente crear un tag en el commit histórico validado antes de futuras demostraciones; no se creó ni publicó ningún tag automáticamente.

---

# 26. Próximo paso recomendado

Revisar el cleanup en `fix/cierre-fase2` y ensayar la defensa con una evidencia nueva; la migración manual de las cinco conexiones Tableau a tableau_ro ya fue validada:

```powershell
python orchestration/flows/fase1_pipeline.py --evidence-prefix 006-defensa
```

Si existe ese prefijo, elegir otro. No reutilizar 003/005 ni rellenar retroactivamente sus métricas ausentes. El tag sugerido y cualquier commit/push/integración posterior requieren una decisión del equipo; este cleanup deja los cambios sin commit.

---

# 27. Registro de cambios

## v1.2 — Cierre de Fase 2 (12 de octubre de 2026)

Fases implementadas, workbook final, evidencia 005 y resultados aprobados incorporados. Nueva protección de evidencia con prefijo obligatorio, resumen dbt desde artefactos, cobertura de marts/vistas y excepción de auditoría. Seguridad/RBAC refleja la migración validada de las cinco conexiones del workbook a tableau_ro, con LOGIN y acceso Gold comprobados. La defensa sigue pendiente.


## v1.0 — Sprint 0 cerrado

Se incorporó:

- decisión definitiva de Transurbano por Batch;
- Bronze como Data Lake local + Parquet;
- PostgreSQL como warehouse;
- dos tablas de hechos;
- estrategia de identidad inferida;
- limitación de Aerómetro;
- definición de multimodalidad observable/inferida;
- contradicción del CDC;
- tratamiento doble del CDC como registro ambiguo + padrón derivado de Transmetro;
- conteos reales de calidad aportados/revisados durante el Sprint 0;
- estructura definitiva inicial del repositorio;
- próximo paso de implementación.

## v0.1

Documento inicial previo al Sprint 0.
