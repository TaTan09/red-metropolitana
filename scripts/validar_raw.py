#!/usr/bin/env python3
"""
Valida el contenido de data/raw para el Proyecto 1 - Red Metropolitana.

- Verifica que existan los 9 archivos esperados.
- Calcula SHA-256 y tamaño.
- Cuenta registros sin cargar archivos completos en memoria.
- Verifica encabezados CSV / llaves principales JSONL.
- Compara contra los conteos base del dataset entregado.
- Genera evidencia reproducible en docs/metricas/.

Uso:
    python scripts/validar_raw.py
"""

from __future__ import annotations

import csv
import hashlib
import json
from datetime import datetime
from pathlib import Path
from typing import Any

PROJECT_ROOT = Path(__file__).resolve().parents[1]
RAW_DIR = PROJECT_ROOT / "data" / "raw"
REPORT_DIR = PROJECT_ROOT / "docs" / "metricas"

EXPECTED = {
    "tm_estaciones.csv": {
        "type": "csv",
        "columns": ["estacion_id", "nombre", "linea", "zona", "lat", "lon"],
        "expected_rows": 104,
    },
    "tu_paradas.csv": {
        "type": "csv",
        "columns": ["cod_parada", "descripcion", "ruta", "sector"],
        "expected_rows": 328,
    },
    "mr_estaciones.csv": {
        "type": "csv",
        "columns": ["id_estacion", "nombre_estacion", "zona_nombre", "km"],
        "expected_rows": 22,
    },
    "am_estaciones.csv": {
        "type": "csv",
        "columns": ["station_code", "station_name", "axis", "district"],
        "expected_rows": 14,
    },
    "transmetro_validaciones.csv": {
        "type": "csv",
        "columns": [
            "validacion_id", "tarjeta", "estacion_id", "linea",
            "fecha_hora", "tarifa", "tipo",
        ],
        "expected_rows": 363_221,
    },
    "transurbano_transacciones.csv": {
        "type": "csv",
        "columns": [
            "fecha", "hora", "num_tarjeta", "cod_parada",
            "ruta", "monto_centavos", "cod_estado",
        ],
        "expected_rows": 832_791,
    },
    "metroriel_viajes.jsonl": {
        "type": "jsonl",
        "keys": ["trip_id", "card", "entry", "exit", "fare_gtq", "duration_s"],
        "expected_rows": 299_100,
    },
    "aerometro_boardings.csv": {
        "type": "csv",
        "columns": [
            "boarding_id", "user_hash", "station_code", "axis",
            "timestamp_utc", "cabin_number", "fare",
        ],
        "expected_rows": 203_554,
    },
    "cdc_padron_usuarios.csv": {
        "type": "csv",
        "columns": [
            "seq", "commit_ts", "op", "tarjeta",
            "perfil", "zona_residencia", "estado",
        ],
        "expected_rows": 31_050,
    },
}


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def validate_csv(path: Path, expected_columns: list[str]) -> tuple[int, list[str], bool]:
    with path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.reader(f)
        try:
            header = next(reader)
        except StopIteration:
            return 0, [], False

        row_count = sum(1 for _ in reader)

    return row_count, header, header == expected_columns


def validate_jsonl(path: Path, expected_keys: list[str]) -> tuple[int, int, list[str], bool]:
    row_count = 0
    invalid_json = 0
    first_keys: list[str] = []

    with path.open("r", encoding="utf-8") as f:
        for line_no, line in enumerate(f, start=1):
            if not line.strip():
                continue

            row_count += 1
            try:
                obj = json.loads(line)
            except json.JSONDecodeError:
                invalid_json += 1
                continue

            if not first_keys:
                first_keys = list(obj.keys())

    keys_ok = set(expected_keys).issubset(set(first_keys))
    return row_count, invalid_json, first_keys, keys_ok


def human_mb(size_bytes: int) -> float:
    return round(size_bytes / 1024 / 1024, 2)


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 72)
    print("VALIDACIÓN RAW - RED METROPOLITANA")
    print("=" * 72)
    print(f"Proyecto : {PROJECT_ROOT}")
    print(f"Raw      : {RAW_DIR}")
    print()

    if not RAW_DIR.exists():
        print(f"[ERROR] No existe la carpeta: {RAW_DIR}")
        return 1

    results: list[dict[str, Any]] = []
    all_ok = True

    for filename, spec in EXPECTED.items():
        path = RAW_DIR / filename
        print(f"Validando {filename} ...")

        result: dict[str, Any] = {
            "archivo": filename,
            "existe": path.exists(),
            "tipo": spec["type"],
            "esperado_registros": spec["expected_rows"],
        }

        if not path.exists():
            result.update({
                "estado": "ERROR",
                "detalle": "Archivo no encontrado",
            })
            results.append(result)
            all_ok = False
            print("  [ERROR] No encontrado")
            continue

        size_bytes = path.stat().st_size
        result["bytes"] = size_bytes
        result["mb"] = human_mb(size_bytes)
        result["sha256"] = sha256_file(path)

        if spec["type"] == "csv":
            rows, header, schema_ok = validate_csv(path, spec["columns"])
            result["registros"] = rows
            result["columnas"] = header
            result["esquema_ok"] = schema_ok
            result["json_invalidos"] = None

        else:
            rows, invalid_json, keys, schema_ok = validate_jsonl(path, spec["keys"])
            result["registros"] = rows
            result["columnas"] = keys
            result["esquema_ok"] = schema_ok
            result["json_invalidos"] = invalid_json

        result["conteo_ok"] = result["registros"] == spec["expected_rows"]

        file_ok = result["esquema_ok"] and result["conteo_ok"]
        if spec["type"] == "jsonl":
            file_ok = file_ok and result["json_invalidos"] == 0

        result["estado"] = "OK" if file_ok else "REVISAR"

        if not file_ok:
            all_ok = False

        print(
            f"  [{result['estado']}] "
            f"{result['registros']:,} registros | "
            f"{result['mb']:.2f} MB | esquema={'OK' if result['esquema_ok'] else 'REVISAR'}"
        )

    # Detectar extras en data/raw, ignorando .gitkeep
    actual_files = {
        p.name for p in RAW_DIR.iterdir()
        if p.is_file() and p.name != ".gitkeep"
    }
    expected_files = set(EXPECTED)
    extras = sorted(actual_files - expected_files)
    missing = sorted(expected_files - actual_files)

    generated_at = datetime.now().astimezone().isoformat(timespec="seconds")

    report = {
        "fecha_validacion": generated_at,
        "raw_dir": str(RAW_DIR),
        "estado_general": "OK" if all_ok and not extras and not missing else "REVISAR",
        "archivos_esperados": len(EXPECTED),
        "archivos_encontrados": len(actual_files),
        "faltantes": missing,
        "extras": extras,
        "resultados": results,
    }

    json_path = REPORT_DIR / "inventario_raw.json"
    json_path.write_text(
        json.dumps(report, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    md_lines = [
        "# Inventario y validación de Raw",
        "",
        f"- **Fecha de validación:** `{generated_at}`",
        f"- **Estado general:** **{report['estado_general']}**",
        f"- **Archivos esperados:** {len(EXPECTED)}",
        f"- **Archivos encontrados:** {len(actual_files)}",
        "",
        "## Inventario",
        "",
        "| Archivo | Registros | Esperados | Tamaño MB | Esquema | Conteo | SHA-256 |",
        "|---|---:|---:|---:|---|---|---|",
    ]

    for r in results:
        if not r.get("existe"):
            md_lines.append(
                f"| `{r['archivo']}` | — | {r['esperado_registros']:,} | — | ERROR | ERROR | — |"
            )
            continue

        md_lines.append(
            f"| `{r['archivo']}` | {r['registros']:,} | {r['esperado_registros']:,} | "
            f"{r['mb']:.2f} | "
            f"{'OK' if r['esquema_ok'] else 'REVISAR'} | "
            f"{'OK' if r['conteo_ok'] else 'REVISAR'} | "
            f"`{r['sha256']}` |"
        )

    md_lines += [
        "",
        "## Archivos faltantes",
        "",
        "Ninguno." if not missing else "\n".join(f"- `{x}`" for x in missing),
        "",
        "## Archivos extra",
        "",
        "Ninguno." if not extras else "\n".join(f"- `{x}`" for x in extras),
        "",
        "## Interpretación",
        "",
        "Este reporte valida la capa **Raw**. No aplica limpieza, normalización ni reglas de negocio.",
        "Los hashes SHA-256 permiten comprobar que un archivo no cambió entre corridas.",
        "",
    ]

    md_path = REPORT_DIR / "inventario_raw.md"
    md_path.write_text("\n".join(md_lines), encoding="utf-8")

    print()
    print("-" * 72)
    print(f"Estado general: {report['estado_general']}")
    print(f"Reporte JSON   : {json_path.relative_to(PROJECT_ROOT)}")
    print(f"Reporte Markdown: {md_path.relative_to(PROJECT_ROOT)}")
    print("-" * 72)

    return 0 if report["estado_general"] == "OK" else 2


if __name__ == "__main__":
    raise SystemExit(main())