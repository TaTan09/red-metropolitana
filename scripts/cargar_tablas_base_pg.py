#!/usr/bin/env python3
"""Reconstruye Staging exclusivamente desde data/bronze/*.parquet."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd
import pyarrow.parquet as pq
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from ingestion.cdc.process_cdc import build_current_tm, classify_key, postgres_engine

BRONZE = ROOT / "data" / "bronze"

CATALOGS = {
    "tm_estaciones": ["estacion_id", "nombre", "linea", "zona", "lat", "lon"],
    "tu_paradas": ["cod_parada", "descripcion", "ruta", "sector"],
    "mr_estaciones": ["id_estacion", "nombre_estacion", "zona_nombre", "km"],
    "am_estaciones": ["station_code", "station_name", "axis", "district"],
}
OPERATIONS = {
    "transmetro_validaciones": ["validacion_id", "tarjeta", "estacion_id", "linea", "fecha_hora", "tarifa", "tipo"],
    "transurbano_transacciones": ["fecha", "hora", "num_tarjeta", "cod_parada", "ruta", "monto_centavos", "cod_estado"],
    "metroriel_viajes": ["trip_id", "card", "entry_station", "entry_ts", "exit_station", "exit_ts", "fare_gtq", "duration_s"],
    "aerometro_boardings": ["boarding_id", "user_hash", "station_code", "axis", "timestamp_utc", "cabin_number", "fare"],
}


def parquet_files(source: str) -> list[Path]:
    files = sorted((BRONZE / source).glob("fecha_ingesta=*/*.parquet"))
    if not files:
        raise FileNotFoundError(f"No hay Parquet Bronze para {source}; ejecute su ingesta primero")
    return files


def read_bronze(source: str, *, latest_batch: bool = False) -> pd.DataFrame:
    files = parquet_files(source)
    if latest_batch:
        files = [max(files, key=lambda p: (p.parent.name, p.stat().st_mtime_ns, str(p)))]
    return pd.concat((pq.read_table(p).to_pandas() for p in files), ignore_index=True)


def source_rows(source: str) -> pd.DataFrame:
    batch = source in CATALOGS or source in {"transurbano_transacciones", "metroriel_viajes"}
    bronze = read_bronze(source, latest_batch=batch)
    if "raw_json" in bronze:
        parsed = bronze["raw_json"].map(json.loads)
        if source == "metroriel_viajes":
            rows = pd.DataFrame([{
                "trip_id": r.get("trip_id"), "card": r.get("card"),
                "entry_station": (r.get("entry") or {}).get("station"),
                "entry_ts": (r.get("entry") or {}).get("ts"),
                "exit_station": (r.get("exit") or {}).get("station"),
                "exit_ts": (r.get("exit") or {}).get("ts"),
                "fare_gtq": r.get("fare_gtq"), "duration_s": r.get("duration_s"),
            } for r in parsed])
        else:
            rows = pd.DataFrame([r.get("data", r) for r in parsed])
    else:
        rows = bronze.copy()
    columns = CATALOGS.get(source, OPERATIONS.get(source))
    missing = set(columns) - set(rows.columns)
    if missing:
        raise ValueError(f"{source}: faltan columnas {sorted(missing)}")
    result = rows[columns].copy()
    if source in OPERATIONS:
        if "_event_id" in bronze:
            result["bronze_record_id"] = bronze["_event_id"].astype(str)
            result["ingesta_timestamp"] = bronze["_consumed_at"].astype(str)
        else:
            result["bronze_record_id"] = bronze["_source_sha256"].astype(str) + ":" + bronze["_record_number"].astype(str)
            result["ingesta_timestamp"] = bronze["_ingestion_ts"].astype(str)
    return result.where(pd.notna(result), None)


def build_tables() -> dict[str, pd.DataFrame]:
    tables = {source: source_rows(source) for source in CATALOGS | OPERATIONS}
    cdc = read_bronze("cdc_padron_usuarios", latest_batch=True)
    cdc["seq"] = pd.to_numeric(cdc["seq"], errors="raise")
    cdc["tipo_llave"] = cdc["tarjeta"].astype(str).map(classify_key)
    tables["cdc_registro_ambiguo"] = cdc
    tables["padron_transmetro_actual"] = build_current_tm(cdc)
    for table, source, key in (
        ("usuarios_transurbano_min", "transurbano_transacciones", "num_tarjeta"),
        ("usuarios_metroriel_min", "metroriel_viajes", "card"),
        ("usuarios_aerometro_min", "aerometro_boardings", "user_hash"),
    ):
        tables[table] = tables[source][[key]].drop_duplicates().reset_index(drop=True)
    return tables


def rebuild(tables: dict[str, pd.DataFrame]) -> None:
    engine = postgres_engine()
    try:
        with engine.begin() as conn:
            conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging"))
            for name, frame in tables.items():
                conn.execute(text(f'DROP TABLE IF EXISTS staging."{name}"'))
                frame.to_sql(name, conn, schema="staging", if_exists="append", index=False, chunksize=5000)
                actual = conn.execute(text(f'SELECT count(*) FROM staging."{name}"')).scalar_one()
                if actual != len(frame):
                    raise RuntimeError(f"{name}: {actual} filas cargadas; {len(frame)} esperadas")
                print(f"staging.{name}: {actual:,} filas")
    finally:
        engine.dispose()


def main() -> int:
    tables = build_tables()  # valida todas las fuentes antes de tocar PostgreSQL
    rebuild(tables)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
