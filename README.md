# Red Metropolitana — Proyecto 1 de Ciencia de Datos

Repositorio del proyecto de integración de datos de Transmetro, Transurbano, MetroRiel y Aerómetro.

## Arquitectura acordada

```text
Fuentes
  ↓
Ingesta
  ↓
Raw
  ↓
Bronze / Data Lake (Parquet)
  ↓
Staging / PostgreSQL
  ↓
Silver / dbt
  ↓
Gold / dbt
  ↓
Tableau

Silver
  ↓
Features
```

## Primer arranque: PostgreSQL

### 1. Copiar el archivo de variables

En Windows PowerShell:

```powershell
Copy-Item .env.example .env
```

En Git Bash:

```bash
cp .env.example .env
```

Edita `.env` y cambia `POSTGRES_PASSWORD`.

> `.env` está ignorado por Git y nunca debe subirse.

### 2. Levantar PostgreSQL

```bash
docker compose up -d postgres
```

### 3. Verificar el contenedor

```bash
docker compose ps
```

Debe mostrar `red_metropolitana_postgres` como `healthy`.

### 4. Verificar la base y los esquemas

Git Bash / PowerShell:

```bash
docker exec -it red_metropolitana_postgres psql -U red_user -d red_metropolitana
```

Dentro de `psql`:

```sql
\dn
```

Deben existir al menos:

- `staging`
- `silver`
- `gold`
- `control`

Para salir:

```text
\q
```

## Nota sobre los scripts de inicialización

Los archivos de `sql/init/` se ejecutan automáticamente únicamente cuando PostgreSQL crea un volumen vacío.

Si se modifica un script de `sql/init/` después del primer arranque, no se volverá a ejecutar por sí solo.

## Datos

Los archivos grandes NO se suben al repositorio.

Colocar los datos oficiales en:

```text
data/raw/
```

Luego el pipeline de ingesta generará Bronze en:

```text
data/bronze/
```

## Reglas que no se pueden romper

- Gold nunca lee Bronze directamente.
- Los registros inválidos se conservan con trazabilidad/cuarentena.
- Las features salen de Silver.
- El pipeline debe ser idempotente.
- No subir credenciales reales.
- Seudonimizar la identidad antes de Gold.
