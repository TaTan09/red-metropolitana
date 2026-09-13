# Contexto compartido — Proyecto 1 de Ciencia de Datos
## Agencia Metropolitana de Transporte

**Versión:** 1.0  
**Estado:** Sprint 0 completado  
**Fecha de actualización:** 12 de septiembre de 2026

> Este documento debe compartirse entre Hector, Alejandro y Jonatán, y puede enviarse a las herramientas de IA que cada integrante utilice.  
> Su propósito es mantener un contexto común, evitar soluciones incompatibles y dejar por escrito las decisiones ya tomadas por el grupo.

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

En Silver se construirá una tabla puente conceptual:

```text
bridge_identidad_usuario
```

Campos previstos:

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

La multimodalidad que involucra Aerómetro puede estar subestimada.

---

# 10. Definición de multimodalidad

No se debe afirmar:

> “X personas reales utilizan varios operadores”

porque la identidad entre operadores no está demostrada.

La métrica se definirá como:

> **Usuario multimodal identificable/inferido:** identidad canónica que, bajo la estrategia documentada de resolución de identidad, presenta actividad en al menos dos modos.

La métrica puede cubrir principalmente combinaciones entre:

- Transmetro
- Transurbano
- MetroRiel

Aerómetro debe reportarse con la limitación correspondiente.

### Implicación para Tableau

La pregunta obligatoria de usuarios que usan más de un sistema se responderá, pero el tablero deberá dejar claro que se trata de:

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

La implementación definitiva se realizará en Silver/dbt.

Nada se elimina silenciosamente.

---

# 16. Dimensiones y Gold previstas

Dimensiones iniciales:

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

## División propuesta del tablero

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

Ejemplos:

- viajes últimos 7 días;
- viajes últimos 30 días;
- viajes últimos 90 días;
- modo más usado;
- cantidad de modos;
- días desde último viaje;
- proporción en hora pico;
- zona de origen frecuente;
- gasto acumulado;
- gasto promedio.

Se deberá declarar una **fecha de corte**.

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

Antes de Gold, el usuario canónico deberá seudonimizarse.

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

## Completado

- ✅ Enunciado revisado.
- ✅ Archivos recibidos.
- ✅ Generador revisado.
- ✅ Inventario inicial.
- ✅ Hallazgos de calidad iniciales.
- ✅ Matriz del bus preliminar.
- ✅ Grano definido.
- ✅ Estrategia de identidad definida.
- ✅ Contradicción del CDC identificada.
- ✅ Tratamiento del CDC acordado.
- ✅ Transurbano decidido como Batch.
- ✅ Bronze decidido como lake + Parquet.
- ✅ PostgreSQL seleccionado.
- ✅ Estructura del repositorio definida.
- ✅ Sprint 0 completado.

## Pendiente de implementación

- ⬜ Crear repositorio Git.
- ⬜ Crear estructura de carpetas.
- ⬜ Crear `docker-compose.yml`.
- ⬜ Levantar PostgreSQL.
- ⬜ Preparar Kafka.
- ⬜ Implementar ingesta Batch.
- ⬜ Implementar ingesta Streaming.
- ⬜ Implementar CDC.
- ⬜ Configurar dbt.
- ⬜ Construir Silver.
- ⬜ Construir Gold.
- ⬜ Configurar Prefect.
- ⬜ Construir Tableau.
- ⬜ Construir tabla de features.
- ⬜ Documentar gobernanza.
- ⬜ Probar idempotencia.
- ⬜ Preparar defensa.

---

# 26. Próximo paso recomendado

El Sprint 0 ya está cerrado.

El siguiente paso debe ser compartido por los tres:

> **Crear físicamente el repositorio y levantar el entorno base reproducible.**

Orden recomendado:

```text
1. Crear repositorio Git
2. Crear estructura de carpetas
3. Crear .gitignore
4. Crear .env.example
5. Crear docker-compose.yml
6. Levantar PostgreSQL
7. Verificar conexión
8. Agregar Kafka
9. Hacer primer commit de infraestructura
```

Después de que el entorno base funcione, cada integrante puede comenzar su responsabilidad principal sin separarse de la arquitectura acordada.

---

# 27. Registro de cambios

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
