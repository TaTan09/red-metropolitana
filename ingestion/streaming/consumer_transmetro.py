#!/usr/bin/env python3
"""
Consumidor Kafka - Transmetro -> Bronze
Proyecto 1 - Red Metropolitana

Consume el topic:
    transmetro-validaciones

y conserva los mensajes en Bronze como Parquet.

Principios:
- Bronze conserva el mensaje Kafka completo en `raw_json`.
- No elimina duplicados de negocio del torniquete.
- Solo deduplica repeticiones técnicas del pipeline usando `_event_id`.
- El estado de deduplicación se guarda localmente en SQLite dentro de
  data/bronze/_control/ (ignorado por Git).
- Los offsets Kafka se confirman después de persistir el lote.

Prueba inicial:
    python ingestion/streaming/consumer_transmetro.py --max-messages 10

Uso normal:
    python ingestion/streaming/consumer_transmetro.py
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import time
from datetime import datetime
from pathlib import Path
from typing import Any

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from confluent_kafka import Consumer, KafkaError

PROJECT_ROOT = Path(__file__).resolve().parents[2]
BRONZE_DIR = PROJECT_ROOT / "data" / "bronze"
CONTROL_DIR = BRONZE_DIR / "_control"
STATE_DB = CONTROL_DIR / "streaming_state.sqlite"
REPORT_DIR = PROJECT_ROOT / "docs" / "metricas"

DEFAULT_BOOTSTRAP = "localhost:9092"
DEFAULT_TOPIC = "transmetro-validaciones"
DEFAULT_GROUP = "bronze-transmetro-v1"


def init_state_db() -> sqlite3.Connection:
    CONTROL_DIR.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(STATE_DB)
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS processed_events (
            event_id TEXT PRIMARY KEY,
            topic TEXT NOT NULL,
            partition_id INTEGER NOT NULL,
            kafka_offset INTEGER NOT NULL,
            source_file TEXT,
            source_sha256 TEXT,
            processed_at TEXT NOT NULL
        )
        """
    )
    conn.commit()
    return conn


def already_processed(conn: sqlite3.Connection, event_id: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM processed_events WHERE event_id = ? LIMIT 1",
        (event_id,),
    ).fetchone()
    return row is not None


def write_batch(
    rows: list[dict[str, Any]],
    conn: sqlite3.Connection,
    ingestion_date: str,
) -> Path | None:
    if not rows:
        return None

    # Para este proyecto el topic se creó con una partición.
    partitions = {r["_kafka_partition"] for r in rows}
    if len(partitions) != 1:
        raise RuntimeError(
            "El buffer contiene múltiples particiones; este consumidor "
            "esperaba una sola partición por lote."
        )

    partition = next(iter(partitions))
    first_offset = min(r["_kafka_offset"] for r in rows)
    last_offset = max(r["_kafka_offset"] for r in rows)

    output_dir = (
        BRONZE_DIR
        / "transmetro_validaciones"
        / f"fecha_ingesta={ingestion_date}"
    )
    output_dir.mkdir(parents=True, exist_ok=True)

    output_path = output_dir / (
        f"part-p{partition}-{first_offset:012d}-{last_offset:012d}.parquet"
    )
    temp_path = output_path.with_suffix(".tmp.parquet")

    df = pd.DataFrame(rows)
    table = pa.Table.from_pandas(df, preserve_index=False)
    pq.write_table(table, temp_path, compression="snappy")
    temp_path.replace(output_path)

    parquet_rows = pq.ParquetFile(output_path).metadata.num_rows
    if parquet_rows != len(rows):
        raise RuntimeError(
            f"Conteo inconsistente: buffer={len(rows)}, parquet={parquet_rows}"
        )

    processed_at = datetime.now().astimezone().isoformat(timespec="seconds")

    try:
        conn.execute("BEGIN")
        for row in rows:
            conn.execute(
                """
                INSERT OR IGNORE INTO processed_events (
                    event_id,
                    topic,
                    partition_id,
                    kafka_offset,
                    source_file,
                    source_sha256,
                    processed_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    row["_event_id"],
                    row["_kafka_topic"],
                    row["_kafka_partition"],
                    row["_kafka_offset"],
                    row.get("_source_file"),
                    row.get("_source_sha256"),
                    processed_at,
                ),
            )
        conn.commit()
    except Exception:
        conn.rollback()
        raise

    return output_path


def write_report(summary: dict[str, Any]) -> None:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)

    json_path = REPORT_DIR / "streaming_transmetro_consumer.json"
    json_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    lines = [
        "# Evidencia de consumo Streaming — Transmetro",
        "",
        f"- **Fecha:** `{summary['fecha']}`",
        f"- **Topic:** `{summary['topic']}`",
        f"- **Consumer group:** `{summary['group_id']}`",
        f"- **Mensajes consumidos:** {summary['mensajes_consumidos']:,}",
        f"- **Eventos nuevos escritos a Bronze:** {summary['eventos_nuevos']:,}",
        f"- **Repeticiones técnicas omitidas:** {summary['duplicados_tecnicos']:,}",
        f"- **Mensajes inválidos:** {summary['mensajes_invalidos']:,}",
        f"- **Archivos Parquet creados:** {summary['parquet_creados']:,}",
        "",
        "## Interpretación",
        "",
        "La deduplicación del consumidor usa `_event_id`, generado de forma "
        "determinística por el productor.",
        "",
        "Esto evita duplicación técnica del pipeline, pero **no elimina** "
        "duplicados reales del torniquete presentes en el archivo fuente. "
        "Esos registros deben llegar a Bronze y serán tratados como calidad "
        "de negocio posteriormente en Silver.",
        "",
    ]

    md_path = REPORT_DIR / "streaming_transmetro_consumer.md"
    md_path.write_text("\n".join(lines), encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-server", default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument("--group-id", default=DEFAULT_GROUP)
    parser.add_argument(
        "--max-messages",
        type=int,
        default=None,
        help="Detiene la ejecución después de consumir N mensajes.",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=5000,
        help="Cantidad de eventos nuevos por archivo Parquet.",
    )
    parser.add_argument(
        "--idle-seconds",
        type=float,
        default=5.0,
        help="Finaliza si no llegan mensajes durante este tiempo.",
    )
    args = parser.parse_args()

    conn = init_state_db()

    consumer = Consumer(
        {
            "bootstrap.servers": args.bootstrap_server,
            "group.id": args.group_id,
            "auto.offset.reset": "earliest",
            "enable.auto.commit": False,
        }
    )

    consumer.subscribe([args.topic])

    ingestion_dt = datetime.now().astimezone()
    ingestion_date = ingestion_dt.date().isoformat()

    buffer: list[dict[str, Any]] = []
    buffer_ids: set[str] = set()

    consumed = 0
    new_events = 0
    technical_duplicates = 0
    invalid_messages = 0
    parquet_paths: list[str] = []

    last_message_at = time.monotonic()

    print("=" * 78)
    print("CONSUMIDOR KAFKA - TRANSMETRO -> BRONZE")
    print("=" * 78)
    print(f"Topic       : {args.topic}")
    print(f"Group       : {args.group_id}")
    print(f"Bootstrap   : {args.bootstrap_server}")
    print(f"Batch size  : {args.batch_size}")
    print(f"Max mensajes: {args.max_messages if args.max_messages is not None else 'sin límite'}")
    print("-" * 78)

    try:
        while True:
            msg = consumer.poll(1.0)

            if msg is None:
                if time.monotonic() - last_message_at >= args.idle_seconds:
                    break
                continue

            if msg.error():
                if msg.error().code() == KafkaError._PARTITION_EOF:
                    continue
                print(f"[ERROR KAFKA] {msg.error()}")
                invalid_messages += 1
                continue

            last_message_at = time.monotonic()
            consumed += 1

            try:
                raw_json = msg.value().decode("utf-8")
                event = json.loads(raw_json)
                event_id = event["_event_id"]
            except Exception as exc:
                print(
                    f"[MENSAJE INVÁLIDO] partition={msg.partition()} "
                    f"offset={msg.offset()} -> {exc}"
                )
                invalid_messages += 1

                if args.max_messages is not None and consumed >= args.max_messages:
                    break
                continue

            # Dedupe técnica: estado persistente + mismo buffer.
            if event_id in buffer_ids or already_processed(conn, event_id):
                technical_duplicates += 1
            else:
                row = {
                    "_event_id": event_id,
                    "_record_number": event.get("_record_number"),
                    "_source_file": event.get("_source_file"),
                    "_source_name": event.get("_source_name"),
                    "_source_sha256": event.get("_source_sha256"),
                    "_published_at": event.get("_published_at"),
                    "_kafka_topic": msg.topic(),
                    "_kafka_partition": msg.partition(),
                    "_kafka_offset": msg.offset(),
                    "_kafka_key": (
                        msg.key().decode("utf-8", errors="replace")
                        if msg.key() is not None
                        else None
                    ),
                    "_consumed_at": datetime.now()
                    .astimezone()
                    .isoformat(timespec="seconds"),
                    "raw_json": raw_json,
                }
                buffer.append(row)
                buffer_ids.add(event_id)
                new_events += 1

            if len(buffer) >= args.batch_size:
                output_path = write_batch(buffer, conn, ingestion_date)
                if output_path:
                    parquet_paths.append(
                        output_path.relative_to(PROJECT_ROOT).as_posix()
                    )
                    print(
                        f"  Parquet: {output_path.name} "
                        f"({len(buffer):,} eventos nuevos)"
                    )
                buffer.clear()
                buffer_ids.clear()

                # Solo confirmar offsets tras persistir el lote.
                consumer.commit(asynchronous=False)

            if args.max_messages is not None and consumed >= args.max_messages:
                break

        if buffer:
            output_path = write_batch(buffer, conn, ingestion_date)
            if output_path:
                parquet_paths.append(
                    output_path.relative_to(PROJECT_ROOT).as_posix()
                )
                print(
                    f"  Parquet: {output_path.name} "
                    f"({len(buffer):,} eventos nuevos)"
                )
            buffer.clear()
            buffer_ids.clear()

        # Confirmamos también mensajes duplicados/técnicos ya evaluados.
        if consumed > 0:
            consumer.commit(asynchronous=False)

    finally:
        consumer.close()
        conn.close()

    summary = {
        "fecha": datetime.now().astimezone().isoformat(timespec="seconds"),
        "topic": args.topic,
        "group_id": args.group_id,
        "mensajes_consumidos": consumed,
        "eventos_nuevos": new_events,
        "duplicados_tecnicos": technical_duplicates,
        "mensajes_invalidos": invalid_messages,
        "parquet_creados": len(parquet_paths),
        "parquet_paths": parquet_paths,
    }

    write_report(summary)

    print("-" * 78)
    print(f"Mensajes consumidos          : {consumed:,}")
    print(f"Eventos nuevos en Bronze     : {new_events:,}")
    print(f"Repeticiones técnicas omitidas: {technical_duplicates:,}")
    print(f"Mensajes inválidos           : {invalid_messages:,}")
    print(f"Parquet creados              : {len(parquet_paths):,}")
    print("Resultado                    : OK")
    print("-" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
