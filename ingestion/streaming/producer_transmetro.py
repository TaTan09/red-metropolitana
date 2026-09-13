#!/usr/bin/env python3
"""
Productor Kafka - Transmetro
Proyecto 1 - Red Metropolitana

Publica transmetro_validaciones.csv línea por línea al topic:
    transmetro-validaciones

Características:
- Lee el CSV sin transformar los valores de negocio.
- Genera un event_id determinístico usando SHA-256 del archivo + número de fila.
- Usa event_id como key de Kafka.
- Agrega únicamente metadatos técnicos.
- Permite dry-run y límite de filas para pruebas.
- No elimina los duplicados reales del archivo: Bronze debe recibirlos.

Uso de prueba SIN publicar:
    python ingestion/streaming/producer_transmetro.py --dry-run --limit 5

Uso de prueba publicando 10 eventos:
    python ingestion/streaming/producer_transmetro.py --limit 10

Uso completo:
    python ingestion/streaming/producer_transmetro.py
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import time
from datetime import datetime
from pathlib import Path

from confluent_kafka import Producer

PROJECT_ROOT = Path(__file__).resolve().parents[2]
RAW_FILE = PROJECT_ROOT / "data" / "raw" / "transmetro_validaciones.csv"

DEFAULT_BOOTSTRAP = "localhost:9092"
DEFAULT_TOPIC = "transmetro-validaciones"


def sha256_file(path: Path, chunk_size: int = 1024 * 1024) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as f:
        while chunk := f.read(chunk_size):
            digest.update(chunk)
    return digest.hexdigest()


def make_event_id(file_hash: str, record_number: int) -> str:
    raw = f"{file_hash}:{record_number}".encode("utf-8")
    return hashlib.sha256(raw).hexdigest()


def delivery_report(err, msg):
    if err is not None:
        print(f"[ERROR ENTREGA] {err}")


def build_event(
    row: dict[str, str],
    *,
    record_number: int,
    file_hash: str,
    published_at: str,
) -> dict:
    return {
        "_event_id": make_event_id(file_hash, record_number),
        "_record_number": record_number,
        "_source_file": RAW_FILE.name,
        "_source_name": "transmetro_validaciones",
        "_source_sha256": file_hash,
        "_published_at": published_at,
        "data": row,
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--bootstrap-server", default=DEFAULT_BOOTSTRAP)
    parser.add_argument("--topic", default=DEFAULT_TOPIC)
    parser.add_argument(
        "--limit",
        type=int,
        default=None,
        help="Publica solo N filas. Útil para pruebas.",
    )
    parser.add_argument(
        "--sleep-ms",
        type=float,
        default=0.0,
        help="Pausa entre eventos para simular streaming más lento.",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Lee y muestra eventos sin enviarlos a Kafka.",
    )
    args = parser.parse_args()

    if not RAW_FILE.exists():
        print(f"[ERROR] No existe: {RAW_FILE}")
        return 1

    file_hash = sha256_file(RAW_FILE)
    published_at = datetime.now().astimezone().isoformat(timespec="seconds")

    producer = None
    if not args.dry_run:
        producer = Producer({
            "bootstrap.servers": args.bootstrap_server,
            "client.id": "red-metropolitana-transmetro-producer",
            "acks": "all",
            "enable.idempotence": True,
        })

    sent = 0

    print("=" * 78)
    print("PRODUCTOR KAFKA - TRANSMETRO")
    print("=" * 78)
    print(f"Archivo         : {RAW_FILE}")
    print(f"SHA-256         : {file_hash}")
    print(f"Topic           : {args.topic}")
    print(f"Bootstrap       : {args.bootstrap_server}")
    print(f"Modo            : {'DRY-RUN' if args.dry_run else 'PUBLICACIÓN'}")
    print(f"Límite          : {args.limit if args.limit is not None else 'TODO EL ARCHIVO'}")
    print("-" * 78)

    with RAW_FILE.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)

        for record_number, row in enumerate(reader, start=1):
            if args.limit is not None and sent >= args.limit:
                break

            event = build_event(
                row,
                record_number=record_number,
                file_hash=file_hash,
                published_at=published_at,
            )

            payload = json.dumps(event, ensure_ascii=False).encode("utf-8")
            key = event["_event_id"].encode("utf-8")

            if args.dry_run:
                if sent < 5:
                    print(json.dumps(event, ensure_ascii=False))
            else:
                # poll(0) permite atender callbacks sin bloquear.
                producer.poll(0)
                producer.produce(
                    args.topic,
                    key=key,
                    value=payload,
                    on_delivery=delivery_report,
                )

                # Backpressure básica si la cola local se llena.
                if len(producer) > 100_000:
                    producer.flush(5)

            sent += 1

            if args.sleep_ms > 0:
                time.sleep(args.sleep_ms / 1000.0)

            if sent % 50_000 == 0:
                print(f"  Procesados: {sent:,}")

    if producer is not None:
        remaining = producer.flush(30)
        if remaining != 0:
            print(f"[ERROR] Quedaron {remaining} mensajes sin confirmar.")
            return 2

    print("-" * 78)
    print(f"Eventos procesados: {sent:,}")
    print("Resultado          : OK")
    print("-" * 78)

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
