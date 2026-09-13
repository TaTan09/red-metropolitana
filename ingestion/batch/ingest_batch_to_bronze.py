#!/usr/bin/env python3
"""
Ingesta Batch: Raw -> Bronze (Parquet)
Proyecto 1 - Red Metropolitana

Fuentes batch incluidas:
- tm_estaciones.csv
- tu_paradas.csv
- mr_estaciones.csv
- am_estaciones.csv
- transurbano_transacciones.csv
- metroriel_viajes.jsonl

Principios:
- Raw nunca se modifica.
- Bronze agrega metadatos de ingesta.
- CSV se conserva como texto (sin normalizar fechas, moneda, zonas, etc.).
- JSONL de MetroRiel se conserva línea por línea en `raw_json`.
- Idempotencia por SHA-256: el mismo archivo no se ingiere dos veces.
- Bronze queda particionado por fecha de ingesta.

Uso:
    python ingestion/batch/ingest_batch_to_bronze.py

Opcional:
    python ingestion/batch/ingest_batch_to_bronze.py --force
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
CONTROL_DIR = BRONZE_DIR / "_control"
MANIFEST_PATH = CONTROL_DIR / "batch_manifest.json"
REPORT_DIR = PROJECT_ROOT / "docs" / "metricas"

BATCH_SOURCES = {
    "tm_estaciones.csv": {
        "source_name": "tm_estaciones",
        "format": "csv",
    },
    "tu_paradas.csv": {
        "source_name": "tu_paradas",
        "format": "csv",
    },
    "mr_estaciones.csv": {
        "source_name": "mr_estaciones",
        "format": "csv",
    },
    "am_estaciones.csv": {
        "source_name": "am_estaciones",
        "format": "csv",
    },
    "transurbano_transacciones.csv": {
        "source_name": "transurbano_transacciones",
        "format": "csv",
    },
    "metroriel_viajes.jsonl": {
        "source_name": "metroriel_viajes",
        "format": "jsonl",
    },
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def load_manifest() -> dict[str, Any]:
    if not MANIFEST_PATH.exists():
        return {"version": 1, "files": {}}

    with MANIFEST_PATH.open("r", encoding="utf-8") as f:
        return json.load(f)


def save_manifest(manifest: dict[str, Any]) -> None:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    temp = MANIFEST_PATH.with_suffix(".tmp")
    temp.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    temp.replace(MANIFEST_PATH)


def already_ingested(manifest: dict[str, Any], file_hash: str) -> bool:
    item = manifest.get("files", {}).get(file_hash)
    if not item:
        return False

    output = PROJECT_ROOT / item["output_path"]
    return output.exists()


def read_csv_as_strings(path: Path) -> pd.DataFrame:
    """
    Lee CSV sin inferir tipos de negocio.
    Todos los campos se conservan como string.
    """
    return pd.read_csv(
        path,
        dtype=str,
        keep_default_na=False,
        na_filter=False,
        encoding="utf-8-sig",
    )


def read_jsonl_as_raw(path: Path) -> pd.DataFrame:
    """
    Conserva cada línea JSON exactamente como payload textual.
    No aplana entry/exit en Bronze.
    """
    rows: list[dict[str, Any]] = []
    with path.open("r", encoding="utf-8") as f:
        for record_number, line in enumerate(f, start=1):
            raw = line.rstrip("\r\n")
            if not raw:
                continue

            # Validamos que sea JSON válido, pero guardamos el payload original.
            json.loads(raw)

            rows.append({
                "_record_number": record_number,
                "raw_json": raw,
            })

    return pd.DataFrame(rows)


def add_bronze_metadata(
    df: pd.DataFrame,
    *,
    source_file: str,
    source_name: str,
    file_hash: str,
    ingestion_ts: str,
) -> pd.DataFrame:
    result = df.copy()

    if "_record_number" not in result.columns:
        result.insert(0, "_record_number", range(1, len(result) + 1))

    result["_source_file"] = source_file
    result["_source_name"] = source_name
    result["_source_sha256"] = file_hash
    result["_ingestion_ts"] = ingestion_ts

    return result


def write_parquet(df: pd.DataFrame, output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)

    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(
        table,
        output_path,
        compression="snappy",
    )


def count_parquet_rows(path: Path) -> int:
    pf = pq.ParquetFile(path)
    return pf.metadata.num_rows


def ingest_one(
    filename: str,
    spec: dict[str, str],
    manifest: dict[str, Any],
    *,
    force: bool,
) -> dict[str, Any]:
    raw_path = RAW_DIR / filename

    if not raw_path.exists():
        return {
            "archivo": filename,
            "fuente": spec["source_name"],
            "estado": "ERROR",
            "detalle": "Archivo Raw no encontrado",
        }

    file_hash = sha256_file(raw_path)

    if not force and already_ingested(manifest, file_hash):
        item = manifest["files"][file_hash]
        output_path = PROJECT_ROOT / item["output_path"]
        rows = count_parquet_rows(output_path)

        return {
            "archivo": filename,
            "fuente": spec["source_name"],
            "estado": "SKIPPED",
            "detalle": "Mismo SHA-256 ya presente en Bronze",
            "sha256": file_hash,
            "registros": rows,
            "output_path": item["output_path"],
        }

    ingestion_dt = datetime.now().astimezone()
    ingestion_ts = ingestion_dt.isoformat(timespec="seconds")
    ingestion_date = ingestion_dt.date().isoformat()

    if spec["format"] == "csv":
        df = read_csv_as_strings(raw_path)
    elif spec["format"] == "jsonl":
        df = read_jsonl_as_raw(raw_path)
    else:
        raise ValueError(f"Formato no soportado: {spec['format']}")

    df = add_bronze_metadata(
        df,
        source_file=filename,
        source_name=spec["source_name"],
        file_hash=file_hash,
        ingestion_ts=ingestion_ts,
    )

    short_hash = file_hash[:12]
    relative_output = (
        Path("data")
        / "bronze"
        / spec["source_name"]
        / f"fecha_ingesta={ingestion_date}"
        / f"part-{short_hash}.parquet"
    )
    output_path = PROJECT_ROOT / relative_output

    # --force reemplaza únicamente el mismo lote/hash.
    write_parquet(df, output_path)

    bronze_rows = count_parquet_rows(output_path)
    if bronze_rows != len(df):
        raise RuntimeError(
            f"Conteo inconsistente para {filename}: "
            f"DataFrame={len(df)}, Parquet={bronze_rows}"
        )

    manifest.setdefault("files", {})[file_hash] = {
        "source_file": filename,
        "source_name": spec["source_name"],
        "source_sha256": file_hash,
        "source_bytes": raw_path.stat().st_size,
        "ingestion_ts": ingestion_ts,
        "ingestion_date": ingestion_date,
        "rows": bronze_rows,
        "output_path": relative_output.as_posix(),
    }
    save_manifest(manifest)

    return {
        "archivo": filename,
        "fuente": spec["source_name"],
        "estado": "INGESTED",
        "detalle": "Carga Batch completada",
        "sha256": file_hash,
        "registros": bronze_rows,
        "output_path": relative_output.as_posix(),
    }


def write_report(results: list[dict[str, Any]]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    summary = {
        "fecha": generated_at,
        "resultados": results,
        "total_ingested": sum(r.get("registros", 0) for r in results if r["estado"] == "INGESTED"),
        "total_skipped": sum(r.get("registros", 0) for r in results if r["estado"] == "SKIPPED"),
        "errores": sum(1 for r in results if r["estado"] == "ERROR"),
    }

    json_path = REPORT_DIR / "ingesta_batch_bronze.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Evidencia de ingesta Batch a Bronze",
        "",
        f"- **Fecha:** `{generated_at}`",
        "",
        "| Archivo | Fuente | Estado | Registros | Salida Bronze |",
        "|---|---|---|---:|---|",
    ]

    for r in results:
        lines.append(
            f"| `{r['archivo']}` | `{r['fuente']}` | **{r['estado']}** | "
            f"{r.get('registros', 0):,} | "
            f"`{r.get('output_path', '—')}` |"
        )

    lines += [
        "",
        "## Interpretación",
        "",
        "- `INGESTED`: el archivo fue escrito en Bronze.",
        "- `SKIPPED`: el SHA-256 ya había sido ingerido y el Parquet seguía presente.",
        "- `ERROR`: la fuente no pudo procesarse.",
        "",
        "La idempotencia Batch se controla por SHA-256 del archivo Raw.",
        "Una segunda ejecución con los mismos archivos debe producir `SKIPPED` y no crear filas nuevas.",
        "",
    ]

    md_path = REPORT_DIR / "ingesta_batch_bronze.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--force",
        action="store_true",
        help="Reescribe el lote correspondiente al mismo SHA-256.",
    )
    args = parser.parse_args()

    print("=" * 78)
    print("INGESTA BATCH RAW -> BRONZE")
    print("=" * 78)

    BRONZE_DIR.mkdir(parents=True, exist_ok=True)
    manifest = load_manifest()
    results: list[dict[str, Any]] = []

    for filename, spec in BATCH_SOURCES.items():
        print(f"\nProcesando {filename} ...")
        try:
            result = ingest_one(filename, spec, manifest, force=args.force)
        except Exception as exc:
            result = {
                "archivo": filename,
                "fuente": spec["source_name"],
                "estado": "ERROR",
                "detalle": f"{type(exc).__name__}: {exc}",
            }

        results.append(result)

        if result["estado"] in {"INGESTED", "SKIPPED"}:
            print(
                f"  [{result['estado']}] "
                f"{result.get('registros', 0):,} registros -> "
                f"{result.get('output_path', '')}"
            )
        else:
            print(f"  [ERROR] {result['detalle']}")

    write_report(results)

    errors = [r for r in results if r["estado"] == "ERROR"]

    print()
    print("-" * 78)
    print(f"Fuentes procesadas: {len(results)}")
    print(f"Errores           : {len(errors)}")
    print("Reporte           : docs/metricas/ingesta_batch_bronze.md")
    print("-" * 78)

    return 1 if errors else 0


if __name__ == "__main__":
    raise SystemExit(main())