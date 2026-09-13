#!/usr/bin/env python3
"""
CDC - Raw -> Bronze -> Staging
Proyecto 1 - Red Metropolitana

Procesa cdc_padron_usuarios.csv con dos objetivos:

1) Bronze:
   - Conserva las 31,050 operaciones del archivo.
   - Agrega únicamente metadatos técnicos.
   - Escribe Parquet particionado por fecha de ingesta.
   - Idempotencia por SHA-256 del archivo.

2) PostgreSQL / staging:
   - staging.cdc_registro_ambiguo: conserva todo el CDC.
   - staging.padron_transmetro_actual: deriva el padrón vigente de Transmetro
     usando llaves con patrón TC-########.
   - INSERT/UPDATE activan/actualizan.
   - DELETE NO borra físicamente: marca INACTIVA.
   - Si un DELETE no tiene cuerpo previo visible, conserva la tarjeta con
     perfil/zona NULL.

Uso:
    python ingestion/cdc/process_cdc.py
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dotenv import load_dotenv
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "cdc_padron_usuarios.csv"
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
CONTROL_DIR = BRONZE_DIR / "_control"
MANIFEST_PATH = CONTROL_DIR / "cdc_manifest.json"
REPORT_DIR = PROJECT_ROOT / "docs" / "metricas"

TM_PATTERN = re.compile(r"^TC-\d{8}$")


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1, "files": {}}
    return json.loads(MANIFEST_PATH.read_text(encoding="utf-8"))


def save_manifest(manifest: dict[str, Any]) -> None:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    tmp = MANIFEST_PATH.with_suffix(".tmp")
    tmp.write_text(json.dumps(manifest, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(MANIFEST_PATH)


def bronze_ingest(df: pd.DataFrame, file_hash: str) -> tuple[Path, bool]:
    """Devuelve (ruta_parquet, creado_en_esta_corrida)."""
    manifest = load_manifest()
    existing = manifest.get("files", {}).get(file_hash)

    if existing:
        path = PROJECT_ROOT / existing["output_path"]
        if path.exists():
            return path, False

    ingestion_dt = datetime.now().astimezone()
    ingestion_ts = ingestion_dt.isoformat(timespec="seconds")
    ingestion_date = ingestion_dt.date().isoformat()

    bronze = df.copy()
    bronze.insert(0, "_record_number", range(1, len(bronze) + 1))
    bronze["_source_file"] = RAW_FILE.name
    bronze["_source_name"] = "cdc_padron_usuarios"
    bronze["_source_sha256"] = file_hash
    bronze["_ingestion_ts"] = ingestion_ts

    relative = (
        Path("data")
        / "bronze"
        / "cdc_padron_usuarios"
        / f"fecha_ingesta={ingestion_date}"
        / f"part-{file_hash[:12]}.parquet"
    )
    output = PROJECT_ROOT / relative
    output.parent.mkdir(parents=True, exist_ok=True)

    table = pa.Table.from_pandas(bronze, preserve_index=False)
    pq.write_table(table, output, compression="snappy")

    rows = pq.ParquetFile(output).metadata.num_rows
    if rows != len(bronze):
        raise RuntimeError(f"Conteo Bronze inconsistente: {rows} != {len(bronze)}")

    manifest.setdefault("files", {})[file_hash] = {
        "source_file": RAW_FILE.name,
        "source_sha256": file_hash,
        "rows": rows,
        "ingestion_ts": ingestion_ts,
        "output_path": relative.as_posix(),
    }
    save_manifest(manifest)

    return output, True


def classify_key(card: str) -> str:
    if TM_PATTERN.fullmatch(card or ""):
        return "TRANSMETRO"
    if re.fullmatch(r"\d{10}", card or ""):
        return "TRANSURBANO"
    if re.fullmatch(r"MR\d{7}", card or ""):
        return "METRORIEL"
    if card == "SIN-TARJETA":
        return "SIN_TARJETA"
    return "OTRO"


def build_current_tm(cdc: pd.DataFrame) -> pd.DataFrame:
    """
    Construye padrón vigente de Transmetro aplicando eventos TC-* por seq.
    Last event wins. DELETE conserva atributos previos si existen.
    """
    tm = cdc[cdc["tarjeta"].astype(str).map(lambda x: bool(TM_PATTERN.fullmatch(x)))].copy()
    tm["seq"] = pd.to_numeric(tm["seq"], errors="raise")
    tm = tm.sort_values("seq", kind="stable")

    state: dict[str, dict[str, Any]] = {}

    for row in tm.itertuples(index=False):
        card = str(row.tarjeta)
        op = str(row.op).upper()

        if op in {"INSERT", "UPDATE"}:
            current = state.get(card, {})
            state[card] = {
                "tarjeta": card,
                "perfil": row.perfil if str(row.perfil) != "" else current.get("perfil"),
                "zona_residencia": (
                    row.zona_residencia
                    if str(row.zona_residencia) != ""
                    else current.get("zona_residencia")
                ),
                "estado": "ACTIVA",
                "ultima_seq": int(row.seq),
                "ultimo_commit_ts": row.commit_ts,
                "ultima_operacion": op,
            }

        elif op == "DELETE":
            current = state.get(
                card,
                {
                    "tarjeta": card,
                    "perfil": None,
                    "zona_residencia": None,
                },
            )
            current.update(
                {
                    "estado": "INACTIVA",
                    "ultima_seq": int(row.seq),
                    "ultimo_commit_ts": row.commit_ts,
                    "ultima_operacion": "DELETE",
                }
            )
            state[card] = current
        else:
            raise ValueError(f"Operación CDC no soportada: {op}")

    result = pd.DataFrame(state.values())
    if result.empty:
        return result

    return result.sort_values("tarjeta").reset_index(drop=True)


def postgres_engine():
    # Usamos psycopg 3 (driver SQLAlchemy: postgresql+psycopg).
    # Evita el problema de decodificación observado con psycopg2 en Windows.
    load_dotenv(PROJECT_ROOT / ".env")

    required = [
        "POSTGRES_DB",
        "POSTGRES_USER",
        "POSTGRES_PASSWORD",
        "POSTGRES_HOST",
        "POSTGRES_PORT",
    ]
    missing = [name for name in required if not os.getenv(name)]
    if missing:
        raise RuntimeError(f"Variables .env faltantes: {', '.join(missing)}")

    url = URL.create(
        drivername="postgresql+psycopg",
        username=os.environ["POSTGRES_USER"],
        password=os.environ["POSTGRES_PASSWORD"],
        host=os.environ["POSTGRES_HOST"],
        port=int(os.environ["POSTGRES_PORT"]),
        database=os.environ["POSTGRES_DB"],
    )
    return create_engine(url, future=True)


def load_staging(cdc: pd.DataFrame, current_tm: pd.DataFrame) -> None:
    engine = postgres_engine()

    cdc_stg = cdc.copy()
    cdc_stg["seq"] = pd.to_numeric(cdc_stg["seq"], errors="raise")
    cdc_stg["tipo_llave"] = cdc_stg["tarjeta"].astype(str).map(classify_key)

    # idempotencia en Staging: se reconstruyen ambas tablas desde la fuente.
    with engine.begin() as conn:
        conn.execute(text("DROP TABLE IF EXISTS staging.cdc_registro_ambiguo"))
        conn.execute(text("DROP TABLE IF EXISTS staging.padron_transmetro_actual"))

    cdc_stg.to_sql(
        "cdc_registro_ambiguo",
        engine,
        schema="staging",
        if_exists="replace",
        index=False,
        chunksize=5000,
        method="multi",
    )

    current_tm.to_sql(
        "padron_transmetro_actual",
        engine,
        schema="staging",
        if_exists="replace",
        index=False,
        chunksize=5000,
        method="multi",
    )

    engine.dispose()


def write_report(
    cdc: pd.DataFrame,
    current_tm: pd.DataFrame,
    bronze_path: Path,
    bronze_created: bool,
    file_hash: str,
) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    op_counts = cdc["op"].value_counts().to_dict()
    type_counts = cdc["tarjeta"].astype(str).map(classify_key).value_counts().to_dict()

    tm_events = cdc[cdc["tarjeta"].astype(str).map(lambda x: bool(TM_PATTERN.fullmatch(x)))].copy()
    tm_non_delete_cards = set(
        tm_events.loc[tm_events["op"].isin(["INSERT", "UPDATE"]), "tarjeta"].astype(str)
    )

    active_final = int((current_tm["estado"] == "ACTIVA").sum()) if not current_tm.empty else 0
    inactive_final = int((current_tm["estado"] == "INACTIVA").sum()) if not current_tm.empty else 0
    unique_tm = len(current_tm)
    deletes_only = int(
        (
            (current_tm["estado"] == "INACTIVA")
            & current_tm["perfil"].isna()
            & current_tm["zona_residencia"].isna()
        ).sum()
    ) if not current_tm.empty else 0

    summary = {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "source_file": RAW_FILE.name,
        "source_sha256": file_hash,
        "bronze_path": bronze_path.relative_to(PROJECT_ROOT).as_posix(),
        "bronze_created_this_run": bronze_created,
        "total_cdc": len(cdc),
        "operaciones": {
            "INSERT": int(op_counts.get("INSERT", 0)),
            "UPDATE": int(op_counts.get("UPDATE", 0)),
            "DELETE": int(op_counts.get("DELETE", 0)),
        },
        "tipos_llave": {k: int(v) for k, v in type_counts.items()},
        "tm_tarjetas_no_delete": len(tm_non_delete_cards),
        "tm_tarjetas_unicas_final": unique_tm,
        "tm_activas_final": active_final,
        "tm_inactivas_final": inactive_final,
        "tm_delete_sin_cuerpo_previo_visible": deletes_only,
    }

    (REPORT_DIR / "cdc_metricas.json").write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Métricas CDC y padrón vigente de Transmetro",
        "",
        f"- **Fecha:** `{summary['fecha']}`",
        f"- **Archivo:** `{RAW_FILE.name}`",
        f"- **SHA-256:** `{file_hash}`",
        f"- **Total CDC:** {len(cdc):,}",
        "",
        "## Operaciones",
        "",
        "| Operación | Cantidad |",
        "|---|---:|",
        f"| INSERT | {summary['operaciones']['INSERT']:,} |",
        f"| UPDATE | {summary['operaciones']['UPDATE']:,} |",
        f"| DELETE | {summary['operaciones']['DELETE']:,} |",
        "",
        "## Llaves observadas",
        "",
        "| Tipo | Cantidad |",
        "|---|---:|",
    ]
    for key, value in sorted(summary["tipos_llave"].items()):
        lines.append(f"| {key} | {value:,} |")

    lines += [
        "",
        "## Padrón Transmetro derivado",
        "",
        f"- Tarjetas únicas finales: **{unique_tm:,}**",
        f"- Activas finales: **{active_final:,}**",
        f"- Inactivas finales: **{inactive_final:,}**",
        f"- DELETE sin atributos previos visibles: **{deletes_only:,}**",
        "",
        "## Decisión de arquitectura",
        "",
        "El CDC completo se conserva como `staging.cdc_registro_ambiguo`.",
        "El padrón solicitado de Transmetro se deriva en "
        "`staging.padron_transmetro_actual` usando únicamente llaves `TC-########`.",
        "Los DELETE no eliminan físicamente tarjetas; las dejan `INACTIVA`.",
        "",
        "Las tablas de Staging se reconstruyen desde la fuente en cada corrida, "
        "por lo que repetir el proceso produce el mismo estado final.",
        "",
    ]

    (REPORT_DIR / "cdc_metricas.md").write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    print("=" * 78)
    print("CDC RAW -> BRONZE -> STAGING")
    print("=" * 78)

    if not RAW_FILE.exists():
        print(f"[ERROR] No existe {RAW_FILE}")
        return 1

    file_hash = sha256_file(RAW_FILE)

    # Raw se lee como texto para no perder el formato original de las llaves.
    cdc = pd.read_csv(
        RAW_FILE,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )

    print(f"Archivo      : {RAW_FILE.name}")
    print(f"SHA-256      : {file_hash}")
    print(f"Filas CDC    : {len(cdc):,}")

    bronze_path, bronze_created = bronze_ingest(cdc, file_hash)
    print(
        f"Bronze       : {bronze_path.relative_to(PROJECT_ROOT)} "
        f"({'CREATED' if bronze_created else 'SKIPPED'})"
    )

    current_tm = build_current_tm(cdc)
    load_staging(cdc, current_tm)

    active = int((current_tm["estado"] == "ACTIVA").sum())
    inactive = int((current_tm["estado"] == "INACTIVA").sum())

    write_report(cdc, current_tm, bronze_path, bronze_created, file_hash)

    print("-" * 78)
    print(f"Padrón TM único : {len(current_tm):,}")
    print(f"Activas          : {active:,}")
    print(f"Inactivas        : {inactive:,}")
    print("PostgreSQL       : staging.cdc_registro_ambiguo")
    print("                   staging.padron_transmetro_actual")
    print("Reporte          : docs/metricas/cdc_metricas.md")
    print("Resultado        : OK")
    print("-" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
