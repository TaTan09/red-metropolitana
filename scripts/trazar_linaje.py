#!/usr/bin/env python3
"""Traza un bronze_record_id de Gold hasta su fila en Bronze (Parquet).

Uso:
    python scripts/trazar_linaje.py Transurbano <bronze_record_id>
    python scripts/trazar_linaje.py Transmetro  <bronze_record_id>

Imprime la fila cruda de Bronze, que SI contiene la tarjeta del usuario:
es una herramienta de auditoria, no para analistas.
"""

import argparse
import json
from pathlib import Path

import pyarrow.dataset as ds

ROOT = Path(__file__).resolve().parents[1]
BRONZE = ROOT / "data" / "bronze"
FUENTES = {
    "Transmetro": ("transmetro_validaciones", "streaming"),
    "Aerometro": ("aerometro_boardings", "streaming"),
    "Transurbano": ("transurbano_transacciones", "batch"),
    "MetroRiel": ("metroriel_viajes", "batch"),
}


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("fuente", choices=FUENTES)
    parser.add_argument("bronze_record_id")
    args = parser.parse_args()

    carpeta, via = FUENTES[args.fuente]
    dataset = ds.dataset(str(BRONZE / carpeta), format="parquet", partitioning="hive")

    if via == "streaming":
        filtro = ds.field("_event_id") == args.bronze_record_id
    else:
        sha, _, fila = args.bronze_record_id.partition(":")
        filtro = (ds.field("_source_sha256") == sha) & (ds.field("_record_number") == int(fila))

    filas = dataset.to_table(filter=filtro).to_pylist()
    if not filas:
        print(f"[ERROR] No hay fila en Bronze para {args.bronze_record_id}")
        return 1

    for fila in filas:
        if "raw_json" in fila:
            fila["raw_json"] = json.loads(fila["raw_json"])
        print(json.dumps(fila, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())