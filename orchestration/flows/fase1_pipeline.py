#!/usr/bin/env python3
"""Ejecuta dos veces el flujo completo del proyecto y guarda evidencia protegida."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

import pyarrow.parquet as pq
from confluent_kafka.admin import AdminClient, NewTopic
from dotenv import load_dotenv
from prefect import flow, task
from sqlalchemy import text

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from ingestion.cdc.process_cdc import postgres_engine  # noqa: E402
from ingestion.streaming.producer_transmetro import DEFAULT_TOPIC as TM_TOPIC  # noqa: E402
from ingestion.streaming.producer_aerometro import DEFAULT_TOPIC as AM_TOPIC  # noqa: E402
from scripts.validar_raw import EXPECTED, validate_csv, validate_jsonl  # noqa: E402

RAW = ROOT / "data" / "raw"
BRONZE = ROOT / "data" / "bronze"
EVIDENCE = ROOT / "docs" / "evidencias"
SOURCES = (
    "tm_estaciones", "tu_paradas", "mr_estaciones", "am_estaciones",
    "transurbano_transacciones", "metroriel_viajes", "cdc_padron_usuarios",
    "transmetro_validaciones", "aerometro_boardings",
)
STAGING = SOURCES[:-2] + (
    "transmetro_validaciones", "aerometro_boardings",
    "padron_transmetro_actual", "usuarios_transurbano_min",
    "usuarios_metroriel_min", "usuarios_aerometro_min",
)
# CDC Bronze usa otro nombre para la tabla Staging.
STAGING = tuple("cdc_registro_ambiguo" if s == "cdc_padron_usuarios" else s for s in STAGING)
SILVER = (
    "silver_transmetro_validaciones", "silver_transurbano_transacciones",
    "silver_metroriel_viajes", "silver_aerometro_boardings",
    "silver_cuarentena", "silver_padron_transmetro_scd2",
    "bridge_identidad_usuario", "silver_features_usuario",
    "silver_catalogo_puntos", "silver_universo_zonas",
)
GOLD = (
    "dim_usuario", "dim_tiempo", "dim_zona", "dim_punto_transporte",
    "dim_modo", "dim_servicio", "fact_abordajes", "fact_viajes_metroriel",
    "mart_demanda_hora", "mart_cobertura", "mart_metroriel_zonas", "mart_multimodalidad",
)
TABLEAU = (
    "v_tableau_demanda_abordajes", "v_tableau_demanda_viajes_mr",
    "v_tableau_cobertura", "v_tableau_metroriel",
    "v_tableau_multimodalidad", "v_tableau_transbordos",
)
AUDIT_FIELDS = {
    "silver.bridge_identidad_usuario": ["fecha_proceso"],
    "silver.silver_cuarentena": ["fecha_deteccion"],
}
COMPARISON_KEYS = (
    "raw_sha256", "bronze", "staging", "silver", "gold",
    "tableau", "fingerprints_negocio", "gold_abordajes_por_modo",
)
STREAMS = (
    ("transmetro", "transmetro_validaciones", "streaming_transmetro_consumer.json"),
    ("aerometro", "aerometro_boardings", "streaming_aerometro_consumer.json"),
)
GENERATED_DIRS = (
    "data/bronze", "data/quarantine",
    "dbt/red_metropolitana/target", "dbt/red_metropolitana/logs",
)
DATA_SUFFIXES = {".parquet", ".csv", ".json", ".jsonl", ".tmp",
                 ".sqlite", ".sqlite-wal", ".sqlite-shm", ".sqlite-journal"}
# Referencia del LEEME oficial del Proyecto 2; no altera el contrato estructural Raw.
PROJECT2_EXPECTED_ROWS = {
    "aerometro_boardings.csv": 387053,
    "am_estaciones.csv": 14,
    "cdc_padron_usuarios.csv": 77636,
    "metroriel_viajes.jsonl": 590844,
    "mr_estaciones.csv": 22,
    "tm_estaciones.csv": 104,
    "transmetro_validaciones.csv": 713786,
    "transurbano_transacciones.csv": 1635788,
    "tu_paradas.csv": 328,
}


def run_script(stage: str, script: str, *args: str, timeout: int = 1800) -> dict:
    return run_command(stage, [sys.executable, str(ROOT / script), *args], timeout=timeout)[0]


def run_command(stage: str, command: list[str], *, timeout: int = 1800,
                show_output: bool = True) -> tuple[dict, str]:
    started = time.perf_counter()
    print(f"[{stage}] {' '.join(command)}", flush=True)
    try:
        result = subprocess.run(command, cwd=ROOT, encoding="utf-8", errors="replace", capture_output=True,
                                env={**os.environ, "PYTHONIOENCODING": "utf-8"},
                                timeout=timeout, check=False)
    except subprocess.TimeoutExpired as exc:
        raise RuntimeError(f"{stage}: tiempo límite de {timeout} segundos excedido") from exc
    duration = round(time.perf_counter() - started, 2)
    if show_output and result.stdout:
        print(result.stdout[-12000:], flush=True)
    if show_output and result.stderr:
        print(result.stderr[-4000:], file=sys.stderr, flush=True)
    if result.returncode:
        detail = (result.stderr or result.stdout)[-2000:] if show_output else "Salida reservada (puede contener credenciales)"
        raise RuntimeError(f"{stage}: terminó con código {result.returncode}. {detail}")
    outcome = {"segundos": duration, "codigo_salida": result.returncode}
    published = re.search(r"Eventos procesados:\s*([\d,]+)", result.stdout)
    if published:
        outcome["eventos_procesados"] = int(published.group(1).replace(",", ""))
    return outcome, result.stdout


def checked_local_path(path: Path) -> Path:
    """No seguir enlaces/junctions, ni siquiera hacia otra ruta del repositorio."""
    root = ROOT.resolve()
    if not path.absolute().is_relative_to(root) or path.absolute() != path.resolve():
        raise RuntimeError(f"Ruta insegura para fresh-start: {path}")
    current = path
    while current != root:
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise RuntimeError(f"Enlace no permitido para fresh-start: {current}")
        current = current.parent
    return path


def validate_fresh_raw() -> dict:
    """Reutiliza el contrato Raw, sin imponer los volúmenes históricos del P1."""
    started = time.perf_counter()
    checked_local_path(RAW)
    if not RAW.is_dir():
        raise RuntimeError("No existe data/raw; no se limpia ningún dato")
    entries = {path.name: checked_local_path(path) for path in RAW.iterdir()
               if path.name != ".gitkeep"}
    if entries.keys() != EXPECTED.keys() or any(not p.is_file() for p in entries.values()):
        raise RuntimeError("Raw debe contener exactamente las nueve fuentes esperadas. "
                           f"Faltantes: {sorted(EXPECTED.keys() - entries.keys())}; "
                           f"extras: {sorted(entries.keys() - EXPECTED.keys())}")
    inventory = {}
    for name, spec in EXPECTED.items():
        path = entries[name]
        if spec["type"] == "csv":
            rows, _, valid = validate_csv(path, spec["columns"])
        else:
            rows, invalid, _, valid = validate_jsonl(path, spec["keys"])
            valid = valid and not invalid
        if not valid or rows == 0:
            raise RuntimeError(f"Raw inválido o vacío: {name}; no se limpia ningún dato")
        inventory[name] = {"filas": rows, "sha256": sha256_file(path)}
    return {"segundos": round(time.perf_counter() - started, 2), "archivos": inventory}


def cleanup_plan() -> list[Path]:
    """Sólo directorios generados conocidos; nunca borrar archivos versionados."""
    _, tracked_output = run_command("proteger_versionados", ["git", "ls-files", "-z", "--", *GENERATED_DIRS],
                                    show_output=False)
    tracked = set(tracked_output.split("\0"))
    files = []

    def visit(directory: Path) -> None:
        checked_local_path(directory)
        if not directory.exists():
            return
        if not directory.is_dir():
            raise RuntimeError(f"Se esperaba un directorio generado: {directory}")
        for path in sorted(directory.iterdir()):
            checked_local_path(path)
            if path.is_dir():
                visit(path)
            elif path.name != ".gitkeep":
                if path.relative_to(ROOT).as_posix() in tracked:
                    raise RuntimeError(f"Archivo versionado en ruta generada; se conserva y se aborta: {path}")
                if path.is_relative_to(ROOT / "data") and path.suffix.lower() not in DATA_SUFFIXES:
                    raise RuntimeError(f"Archivo no reconocido como dato/estado generado; se conserva y se aborta: {path}")
                files.append(path)

    for relative in GENERATED_DIRS:
        visit(ROOT / relative)
    return files


def clean_generated_files(files: list[Path]) -> dict:
    started = time.perf_counter()
    counts = {relative: 0 for relative in GENERATED_DIRS}
    # Validar el plan completo antes del primer unlink, incluso si viene de otro caller.
    for path in files:
        checked_local_path(path)
        if path.name == ".gitkeep" or not any(path.is_relative_to(ROOT / d) for d in GENERATED_DIRS):
            raise RuntimeError(f"Archivo fuera del alcance de limpieza: {path}")
    for path in files:
        checked_local_path(path)
        path.unlink()
        relative = next(d for d in GENERATED_DIRS if path.is_relative_to(ROOT / d))
        counts[relative] += 1
    # Conservar las raíces y .gitkeep, quitar únicamente subdirectorios vacíos.
    for relative in GENERATED_DIRS:
        directory = ROOT / relative
        if directory.exists():
            for child in sorted(directory.rglob("*"), key=lambda p: len(p.parts), reverse=True):
                checked_local_path(child)
                if child.is_dir() and not any(child.iterdir()):
                    child.rmdir()
    return {"segundos": round(time.perf_counter() - started, 2), "archivos_eliminados": counts}


def compose_command(*args: str) -> list[str]:
    # El archivo explícito evita cargar overrides de otros servicios/volúmenes.
    return ["docker", "compose", "--project-directory", str(ROOT),
            "--file", str(ROOT / "docker-compose.yml"), *args]


def validate_fresh_compose(bootstrap: str) -> dict:
    """Fallar antes de limpiar si el warehouse no corresponde al Compose local."""
    for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD", "POSTGRES_HOST", "POSTGRES_PORT"):
        if not os.getenv(name):
            raise RuntimeError(f"Falta configurar {name} antes de fresh-start")
    if os.environ["POSTGRES_HOST"] not in {"localhost", "127.0.0.1", "::1"} or bootstrap not in {
            "localhost:9092", "127.0.0.1:9092", "[::1]:9092"}:
        raise RuntimeError("fresh-start sólo admite PostgreSQL/Kafka locales de docker-compose.yml")
    key = os.getenv("GOLD_PSEUDONYM_KEY", "")
    if len(key.encode("utf-8")) < 32 or key.startswith("REEMPLAZAR_"):
        raise RuntimeError("Configure GOLD_PSEUDONYM_KEY antes de fresh-start")
    # No imprimir config: Docker expande aquí las contraseñas del .env.
    timing, output = run_command("validar_compose", compose_command("config", "--format", "json"),
                                 timeout=30, show_output=False)
    config = json.loads(output)
    services, volumes = config["services"], config.get("volumes", {})
    if set(services) != {"postgres", "kafka"} or set(volumes) != {"postgres_data"}:
        raise RuntimeError("Compose tiene servicios/volúmenes fuera del alcance autorizado")
    volume = volumes["postgres_data"]
    if set(volume) != {"name"} or volume["name"] != f"{config['name']}_postgres_data":
        raise RuntimeError("No se permite limpiar un volumen externo o con nombre compartido")
    pg = services["postgres"]
    mounts = pg.get("volumes", [])
    data_mounts = [m for m in mounts if m["type"] == "volume" and m["source"] == "postgres_data"
                   and m["target"] == "/var/lib/postgresql/data"]
    init_mounts = [m for m in mounts if m["type"] == "bind" and m.get("read_only")
                   and Path(m["source"]).resolve() == (ROOT / "sql/init").resolve()
                   and m["target"] == "/docker-entrypoint-initdb.d"]
    if len(mounts) != 2 or len(data_mounts) != 1 or len(init_mounts) != 1 or services["kafka"].get("volumes"):
        raise RuntimeError("Montajes Docker no reconocidos; no se limpia ningún dato")
    if any(str(pg["environment"].get(name)) != os.environ[name]
           for name in ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")):
        raise RuntimeError("La configuración PostgreSQL no coincide con la del pipeline")
    ports = pg.get("ports", [])
    if not any(p["target"] == 5432 and str(p.get("published")) == os.environ["POSTGRES_PORT"] for p in ports):
        raise RuntimeError("POSTGRES_PORT no coincide con el puerto publicado por Compose")
    _, context_host = run_command("validar_contexto_docker",
                                  ["docker", "context", "inspect", "--format", "{{.Endpoints.docker.Host}}"],
                                  timeout=30, show_output=False)
    docker_host = os.getenv("DOCKER_HOST") or context_host.strip()
    if not docker_host.startswith(("npipe://", "unix://")):
        raise RuntimeError("fresh-start requiere un daemon Docker local mediante npipe/unix")
    run_command("validar_docker", ["docker", "info", "--format", "{{.ServerVersion}}"], timeout=30)
    return {**timing, "volumen_postgres": volume["name"]}


def wait_for_services(bootstrap: str, *, timeout: float = 180) -> dict:
    started = time.perf_counter()
    while True:
        try:
            result = validate_services.fn(bootstrap)
            return {**result, "segundos": round(time.perf_counter() - started, 2)}
        except Exception as exc:
            if time.perf_counter() - started >= timeout:
                raise RuntimeError("PostgreSQL/Kafka no estuvieron listos dentro del tiempo límite") from exc
            time.sleep(2)


def prepare_fresh_start() -> dict:
    """Destructivo, llamado exclusivamente por la opción CLI explícita y una sola vez."""
    started = time.perf_counter()
    stages = {"validar_raw": validate_fresh_raw()}
    load_dotenv(ROOT / ".env")
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    files = cleanup_plan()
    stages["validar_compose"] = validate_fresh_compose(bootstrap)
    print("[fresh-start] Se reinicia el estado generado local y Docker del proyecto; data/raw se conserva.", flush=True)
    stages["reiniciar_docker"] = run_command("reiniciar_docker", compose_command("down", "--volumes"), timeout=180)[0]
    stages["confirmar_reset_docker"] = verify_docker_reset(stages["validar_compose"]["volumen_postgres"])
    stages["limpiar_local"] = clean_generated_files(files)
    stages["levantar_docker"] = run_command("levantar_docker", compose_command("up", "-d", "postgres", "kafka"), timeout=600)[0]
    stages["esperar_servicios"] = wait_for_services(bootstrap)
    stages["crear_topics"] = create_stream_topics(bootstrap)
    return {"duracion_total_segundos": round(time.perf_counter() - started, 2), "etapas": stages}


def verify_docker_reset(volume: str) -> dict:
    """Compose puede avisar de un volumen ocupado sin retirarlo: nunca reutilizarlo."""
    started = time.perf_counter()
    _, containers = run_command("verificar_contenedores", compose_command("ps", "--all", "--quiet"),
                                 timeout=30, show_output=False)
    _, volumes = run_command("verificar_volumen", ["docker", "volume", "ls", "--filter", f"name={volume}",
                                                    "--format", "{{.Name}}"], timeout=30, show_output=False)
    if containers.strip() or volume in volumes.splitlines():
        raise RuntimeError("Docker conserva contenedores o el volumen anterior; se aborta para evitar mezcla de datos")
    return {"segundos": round(time.perf_counter() - started, 2), "estado": "sin estado Docker anterior"}


def create_stream_topics(bootstrap: str) -> dict:
    started = time.perf_counter()
    admin = AdminClient({"bootstrap.servers": bootstrap})
    topics = admin.create_topics([NewTopic(name, num_partitions=1, replication_factor=1)
                                 for name in (TM_TOPIC, AM_TOPIC)], request_timeout=30)
    for future in topics.values():
        future.result(timeout=30)
    return {"segundos": round(time.perf_counter() - started, 2), "topics": sorted(topics)}


@task(name="validar_servicios", log_prints=True)
def validate_services(bootstrap: str) -> dict:
    started = time.perf_counter()
    engine = postgres_engine()
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1")).scalar_one()
    finally:
        engine.dispose()
    AdminClient({"bootstrap.servers": bootstrap}).list_topics(timeout=15)
    return {"segundos": round(time.perf_counter() - started, 2), "postgres": "OK", "kafka": "OK"}


@task(name="batch_to_bronze", log_prints=True)
def batch_to_bronze() -> dict:
    return run_script("batch_to_bronze", "ingestion/batch/ingest_batch_to_bronze.py")


@task(name="cdc_to_bronze", log_prints=True)
def cdc_to_bronze() -> dict:
    return run_script("cdc_to_bronze", "ingestion/cdc/process_cdc.py")


def streaming(mode: str, source: str, report: str, bootstrap: str) -> dict:
    producer = run_script(f"{mode}_producer", f"ingestion/streaming/producer_{mode}.py",
                          "--bootstrap-server", bootstrap)
    consumer = run_script(f"{mode}_consumer", f"ingestion/streaming/consumer_{mode}.py",
                          "--bootstrap-server", bootstrap, "--idle-seconds", "15")
    summary = json.loads((ROOT / "docs" / "metricas" / report).read_text(encoding="utf-8"))
    if (summary["mensajes_consumidos"] < producer["eventos_procesados"]
            or summary["mensajes_invalidos"]):
        raise RuntimeError(f"streaming_{mode}: consumo menor que publicación o mensajes inválidos: {summary}")
    return {"producer": producer, "consumer": consumer,
            "mensajes_consumidos": summary["mensajes_consumidos"],
            "eventos_nuevos": summary["eventos_nuevos"],
            "duplicados_tecnicos": summary["duplicados_tecnicos"],
            "mensajes_invalidos": summary["mensajes_invalidos"],
            "parquet_creados": summary["parquet_creados"], "fuente": source}


@task(name="streaming_transmetro", log_prints=True, retries=1, retry_delay_seconds=10)
def streaming_transmetro(bootstrap: str) -> dict:
    return streaming(*STREAMS[0], bootstrap)


@task(name="streaming_aerometro", log_prints=True, retries=1, retry_delay_seconds=10)
def streaming_aerometro(bootstrap: str) -> dict:
    return streaming(*STREAMS[1], bootstrap)


@task(name="rebuild_staging", log_prints=True)
def rebuild_staging() -> dict:
    return run_script("rebuild_staging", "scripts/cargar_tablas_base_pg.py")


@task(name="dbt_build", log_prints=True)
def dbt_build() -> dict:
    artifact = ROOT / "dbt" / "red_metropolitana" / "target" / "run_results.json"
    previous_invocation = None
    if artifact.exists():
        previous_invocation = json.loads(artifact.read_text(encoding="utf-8"))["metadata"].get("invocation_id")
    outcome = run_script("dbt_build", "scripts/run_dbt.py", "build")
    summary = summarize_dbt_results(json.loads(artifact.read_text(encoding="utf-8")))
    if summary["comando"] != "build" or summary["invocation_id"] == previous_invocation:
        raise RuntimeError("run_results.json no corresponde al nuevo dbt build")
    if summary["errores"] or summary["skips"] or summary["otros_estados"]:
        raise RuntimeError("El artefacto dbt final contiene errores, skips o estados no reconocidos")
    outcome["resumen_dbt"] = summary
    return outcome


def summarize_dbt_results(artifact: dict) -> dict:
    """Extrae evidencia real sin copiar SQL compilado ni la clave HMAC."""
    counts = {"pruebas_pass": 0, "modelos_success": 0, "hooks_success": 0,
              "warnings": 0, "errores": 0, "skips": 0}
    states, other, results = {}, {}, []
    for item in artifact["results"]:
        status = item["status"]
        node = item["unique_id"]
        kind = node.split(".", 1)[0]
        states[status] = states.get(status, 0) + 1
        results.append({"unique_id": node, "tipo": kind, "status": status})
        if status == "pass" and kind == "test":
            counts["pruebas_pass"] += 1
        elif status == "success" and kind == "model":
            counts["modelos_success"] += 1
        elif status == "success" and kind == "operation":
            counts["hooks_success"] += 1
        elif status == "warn":
            counts["warnings"] += 1
        elif status in ("error", "fail"):
            counts["errores"] += 1
        elif status == "skipped":
            counts["skips"] += 1
        else:
            other[status] = other.get(status, 0) + 1
    metadata = artifact["metadata"]
    return {**counts,
            "modelos_hooks_success": counts["modelos_success"] + counts["hooks_success"],
            "total_resultados": len(results), "estados": states, "otros_estados": other,
            "comando": artifact["args"]["which"],
            "generated_at": metadata["generated_at"],
            "invocation_id": metadata["invocation_id"],
            "duracion_dbt_segundos": artifact["elapsed_time"],
            "fuente": "dbt/red_metropolitana/target/run_results.json",
            "resultados": results}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def table_counts(conn, schema: str, names: tuple[str, ...]) -> dict[str, int]:
    return {name: conn.execute(text(f'SELECT count(*) FROM "{schema}"."{name}"')).scalar_one()
            for name in names}


def relation_fingerprints(conn, schema: str, names: tuple[str, ...]) -> dict:
    """Multiconjunto de filas JSONB, orden independiente y auditoría excluida."""
    fingerprints = {}
    for name in names:
        relation = f"{schema}.{name}"
        excluded = AUDIT_FIELDS.get(relation, [])
        row_hash = "md5((to_jsonb(t) - CAST(:excluded AS text[]))::text)"
        query = text(f'''SELECT count(*) AS filas,
            md5(coalesce(string_agg({row_hash}, '' ORDER BY {row_hash}), '')) AS contenido
            FROM "{schema}"."{name}" t''')
        row = conn.execute(query, {"excluded": excluded}).mappings().one()
        fingerprints[relation] = {"filas": row["filas"], "fingerprint": row["contenido"],
                                  "auditoria_excluida": list(excluded)}
    return fingerprints


@task(name="collect_metrics", log_prints=True)
def collect_metrics() -> dict:
    started = time.perf_counter()
    files = sorted(path for path in RAW.iterdir() if path.is_file() and path.name != ".gitkeep")
    if len(files) != len(SOURCES):
        raise RuntimeError(f"Se esperaban {len(SOURCES)} fuentes Raw; se encontraron {len(files)}")
    raw = {path.name: sha256_file(path) for path in files}
    bronze = {}
    for source in SOURCES:
        parquet = sorted((BRONZE / source).glob("fecha_ingesta=*/*.parquet"))
        if not parquet:
            raise RuntimeError(f"Bronze incompleto: {source} carece de Parquet")
        per_file = {p.relative_to(ROOT).as_posix(): pq.ParquetFile(p).metadata.num_rows for p in parquet}
        bronze[source] = {"filas": sum(per_file.values()), "archivos": len(per_file),
                          "filas_por_parquet": per_file}
    engine = postgres_engine()
    try:
        with engine.connect().execution_options(isolation_level="REPEATABLE READ") as conn:
            conn.execute(text("SET TRANSACTION READ ONLY"))
            conn.execute(text("SET LOCAL TIME ZONE 'America/Guatemala'"))
            staging = table_counts(conn, "staging", STAGING)
            silver = table_counts(conn, "silver", SILVER)
            gold = table_counts(conn, "gold", GOLD)
            tableau = table_counts(conn, "gold", TABLEAU)
            fingerprints = relation_fingerprints(conn, "silver", SILVER)
            fingerprints.update(relation_fingerprints(conn, "gold", GOLD + TABLEAU))
            modes = dict(conn.execute(text(
                'SELECT fuente_evento, count(*) FROM gold.fact_abordajes GROUP BY fuente_evento'
            )).all())
    finally:
        engine.dispose()
    return {"raw_sha256": raw, "bronze": bronze, "staging": staging,
            "silver": silver, "gold": gold, "tableau": tableau,
            "fingerprints_negocio": fingerprints, "gold_abordajes_por_modo": modes,
            "segundos": round(time.perf_counter() - started, 2)}


@flow(name="red_metropolitana_pipeline", log_prints=True)
def fase1_pipeline() -> dict:
    load_dotenv(ROOT / ".env")
    bootstrap = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    started = time.perf_counter()
    stages = {}
    stages["validar_servicios"] = validate_services(bootstrap)
    stages["batch_to_bronze"] = batch_to_bronze()
    stages["cdc_to_bronze"] = cdc_to_bronze()
    stages["streaming_transmetro"] = streaming_transmetro(bootstrap)
    stages["streaming_aerometro"] = streaming_aerometro(bootstrap)
    stages["rebuild_staging"] = rebuild_staging()
    stages["dbt_build"] = dbt_build()
    metrics = collect_metrics()
    stages["collect_metrics"] = {"segundos": metrics["segundos"]}
    return {"fecha_fin": datetime.now().astimezone().isoformat(timespec="seconds"),
            "duracion_total_segundos": round(time.perf_counter() - started, 2),
            "etapas": stages, "metricas": metrics}


def comparable(run: dict) -> dict:
    metrics = run["metricas"]
    return {key: metrics[key] for key in COMPARISON_KEYS}


def gold_matches_silver(metrics: dict) -> bool:
    """Referencia P2 calculada desde Silver; dbt también prueba esta reconciliación."""
    modes = {mode: metrics["silver"][table] for mode, table in (
        ("Transmetro", "silver_transmetro_validaciones"),
        ("Transurbano", "silver_transurbano_transacciones"),
        ("Aerometro", "silver_aerometro_boardings"),
    )}
    return (metrics["gold"]["fact_abordajes"] == sum(modes.values())
            and metrics["gold"]["fact_viajes_metroriel"] == metrics["silver"]["silver_metroriel_viajes"]
            and metrics["gold_abordajes_por_modo"] == {m: n for m, n in modes.items() if n})


def load_count_table(expected_rows: dict[str, int], bronze: dict) -> list[dict]:
    """Compara una referencia de archivos con las filas Parquet ya medidas en Bronze."""
    rows = []
    for filename, expected in sorted(expected_rows.items()):
        loaded = bronze[Path(filename).stem]["filas"]
        rows.append({"archivo": filename, "filas_esperadas": expected,
                     "filas_cargadas": loaded, "diferencia": loaded - expected})
    return rows


def project2_load_evidence(run: dict, raw_inventory: dict) -> dict:
    rows = load_count_table(PROJECT2_EXPECTED_ROWS, run["metricas"]["bronze"])
    return {"referencia": "LEEME oficial del Proyecto 2, requisito 1.1",
            "tabla": rows,
            "conteos_raw": {name: item["filas"] for name, item in sorted(raw_inventory.items())},
            "estado": "CON_DIFERENCIAS" if any(row["diferencia"] for row in rows) else "OK"}


def render_load_evidence(evidence: dict) -> list[str]:
    lines = [f"Referencia: {evidence['referencia']}.", "",
             f"Estado: **{evidence['estado']}**.", "",
             "filas_cargadas suma las filas persistidas en los Parquet Bronze de cada fuente.",
             "diferencia = filas_cargadas - filas_esperadas; no se usan conteos de Silver/Gold ni mensajes Kafka.", "",
             "| archivo | filas_esperadas | filas_cargadas | diferencia |",
             "|---|---:|---:|---:|"]
    for row in evidence["tabla"]:
        lines.append(f"| {row['archivo']} | {row['filas_esperadas']} | {row['filas_cargadas']} | {row['diferencia']} |")
    differences = [row for row in evidence["tabla"] if row["diferencia"]]
    lines.extend(["", "**Diferencias detectadas; requieren explicación en el informe.**" if differences else
                  "Las nueve fuentes coinciden con la referencia oficial del Proyecto 2.", ""])
    for row in differences:
        lines.append(f"- `{row['archivo']}`: {row['diferencia']:+d} filas respecto al LEEME oficial.")
    lines.extend(["", "Conteos Raw adicionales (no sustituyen filas_cargadas):", "",
                  "| archivo | filas_raw |", "|---|---:|"])
    for name, count in evidence["conteos_raw"].items():
        lines.append(f"| {name} | {count} |")
    if not evidence["conteos_raw"]:
        lines.extend(["", "Conteo Raw no disponible en la preparación guardada."])
    return lines + [""]


def load_evidence_path(prefix: str, run_number: int) -> Path:
    evidence_paths(prefix)  # Reutiliza la validación del prefijo antes de construir otra ruta.
    return ROOT / "docs" / "metricas" / f"{prefix}-requisito-1-1-corrida-{run_number}.md"


def write_load_evidence(prefix: str, run_number: int, evidence: dict, *, overwrite: bool = False) -> None:
    path = load_evidence_path(prefix, run_number)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w" if overwrite else "x", encoding="utf-8", newline="\n") as file:
        file.write("\n".join([f"# Proyecto 2 — Requisito 1.1 — Corrida {run_number}", "",
                              *render_load_evidence(evidence)]))
    detail = "; ".join(f"{row['archivo']}: diferencia={row['diferencia']:+d}"
                       for row in evidence["tabla"] if row["diferencia"])
    print(f"Requisito 1.1 corrida {run_number}: {evidence['estado']}" + (f"; {detail}" if detail else ""),
          file=sys.stderr if detail else sys.stdout, flush=True)


def render_table(title: str, first: dict, second: dict) -> list[str]:
    lines = [f"### {title}", "", "| Tabla/fuente | Corrida 1 | Corrida 2 | Comparación |",
             "|---|---:|---:|---|"]
    for name in sorted(first.keys() | second.keys()):
        a, b = first.get(name), second.get(name)
        a = a["filas"] if isinstance(a, dict) else a
        b = b["filas"] if isinstance(b, dict) else b
        av, bv = f"{a:,}" if a is not None else "AUSENTE", f"{b:,}" if b is not None else "AUSENTE"
        lines.append(f"| `{name}` | {av} | {bv} | {'IGUALES' if a == b else 'DIFERENTES'} |")
    return lines + [""]


def write_json(name: str, content: dict, *, overwrite: bool = False) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with (EVIDENCE / name).open("w" if overwrite else "x", encoding="utf-8", newline="\n") as file:
        file.write(json.dumps(content, ensure_ascii=False, indent=2) + "\n")


def evidence_paths(prefix: str) -> tuple[Path, Path, Path]:
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", prefix):
        raise ValueError("El prefijo sólo admite letras ASCII, números, guion y guion bajo")
    return (EVIDENCE / f"{prefix}-corrida-1.json", EVIDENCE / f"{prefix}-corrida-2.json",
            EVIDENCE / f"{prefix}-idempotencia.md")


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--evidence-prefix", required=True,
                        help="Prefijo nuevo obligatorio, por ejemplo 006-defensa; no sobrescribe por defecto")
    parser.add_argument("--resume-second", action="store_true",
                        help="Conserva la primera corrida del mismo prefijo y repite sólo la segunda")
    parser.add_argument("--overwrite", action="store_true",
                        help="Permite reemplazar explícitamente destinos existentes (resume conserva corrida 1)")
    parser.add_argument("--fresh-start", action="store_true",
                        help="Proyecto 2: valida Raw, borra estado generado local y volúmenes Docker del proyecto, "
                             "levanta servicios y ejecuta dos corridas; incompatible con --resume-second")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    if args.fresh_start and args.resume_second:
        parser.error("--fresh-start no se combina con --resume-second: limpiar invalidaría la primera corrida")
    try:
        first_path, second_path, report_path = evidence_paths(args.evidence_prefix)
    except ValueError as exc:
        parser.error(str(exc))
    destinations = (second_path, report_path) if args.resume_second else (first_path, second_path, report_path)
    if args.fresh_start:
        destinations += tuple(load_evidence_path(args.evidence_prefix, number) for number in (1, 2))
    if any(path.is_dir() for path in destinations):
        parser.error("Un destino de evidencia es un directorio; no se ejecuta el flujo")
    if not args.overwrite:
        existing = [path.name for path in destinations if path.exists()]
        if existing:
            parser.error("Evidencia existente; use otro prefijo o --overwrite explícito: " + ", ".join(existing))
    if args.resume_second:
        if not first_path.is_file():
            parser.error(f"No existe {first_path.name} para reanudar")
        first = json.loads(first_path.read_text(encoding="utf-8"))
        if first.get("evidence_prefix") != args.evidence_prefix:
            parser.error("La corrida guardada no corresponde al prefijo solicitado")
        try:
            comparable(first)
            first["etapas"]["dbt_build"]["resumen_dbt"]
        except KeyError:
            parser.error("La primera corrida usa un formato incompleto anterior; genere dos corridas con un prefijo nuevo")
        if "preparacion_fresh_start" in first:
            count_path = load_evidence_path(args.evidence_prefix, 2)
            if count_path.is_dir() or (count_path.exists() and not args.overwrite):
                parser.error("Destino de conteos existente; use --overwrite explícito si es un archivo: " + count_path.name)
            raw = validate_fresh_raw()
            if {name: item["sha256"] for name, item in raw["archivos"].items()} != first["metricas"]["raw_sha256"]:
                parser.error("Raw cambió desde la primera corrida; no se reanuda para evitar mezclar datasets")
            raw_inventory = raw["archivos"]
            # Derivar también para una primera evidencia anterior a este entregable, sin sobrescribirla.
            first["requisito_1_1"] = project2_load_evidence(first, raw_inventory)
    else:
        preparation = prepare_fresh_start() if args.fresh_start else None
        first = fase1_pipeline()
        first["evidence_prefix"] = args.evidence_prefix
        if preparation is not None:
            first["preparacion_fresh_start"] = preparation
            raw_inventory = preparation["etapas"]["validar_raw"].get("archivos", {})
            first["requisito_1_1"] = project2_load_evidence(first, raw_inventory)
        write_json(first_path.name, first, overwrite=args.overwrite)
        if preparation is not None:
            write_load_evidence(args.evidence_prefix, 1, first["requisito_1_1"], overwrite=args.overwrite)
    second = fase1_pipeline()
    second["evidence_prefix"] = args.evidence_prefix
    if "preparacion_fresh_start" in first:
        second["requisito_1_1"] = project2_load_evidence(second, raw_inventory)
    write_json(second_path.name, second, overwrite=args.overwrite)
    if "preparacion_fresh_start" in first:
        write_load_evidence(args.evidence_prefix, 2, second["requisito_1_1"], overwrite=args.overwrite)
    equal = comparable(first) == comparable(second)
    a, b = first["metricas"], second["metricas"]
    reference = {"fact_abordajes": 1393448, "fact_viajes_metroriel": 295511}
    mode_reference = {"Transmetro": 362106, "Transurbano": 827788, "Aerometro": 203554}
    expected = all(run["gold"][name] == count for run in (a, b)
                   for name, count in reference.items())
    expected = expected and all(run["gold_abordajes_por_modo"] == mode_reference
                                for run in (a, b))
    project2 = "preparacion_fresh_start" in first
    if project2:
        expected = all(gold_matches_silver(run) for run in (a, b))
    reference_label = "Gold reconciliado con Silver (fuentes nuevas)" if project2 else "Gold medida en PostgreSQL"
    lines = ["# Idempotencia del flujo completo del proyecto", "",
             "Se ejecutó dos veces el mismo flujo Prefect con los mismos archivos Raw,",
             "sin borrar Bronze, el estado SQLite de deduplicación ni los volúmenes Docker entre corridas.",
             "Idempotencia significa que reprocesar las mismas fuentes no cambia el estado analítico final.", "",
             f"- Corrida 1: {first['duracion_total_segundos']:,.2f} s; terminó {first['fecha_fin']}.",
             f"- Corrida 2: {second['duracion_total_segundos']:,.2f} s; terminó {second['fecha_fin']}.",
             f"- Comparación de SHA-256 Raw, filas Parquet, conteos SQL y fingerprints de negocio: **{'IGUALES' if equal else 'DIFERENTES'}**.",
             f"- Referencia {reference_label}: **{'OK' if expected else 'DIFERENTE'}**.",
             "- Cada corrida ejecutó `python scripts/run_dbt.py build` con sus pruebas.", "",
             "## Conteos de ambas corridas", ""]
    if project2:
        prep = first["preparacion_fresh_start"]
        lines[2:2] = ["Proyecto 2: se validaron las nueve fuentes y se limpió el estado generado una sola vez,",
                      "antes de la corrida 1, mediante --fresh-start. Raw se conservó.", ""]
        lines.extend(["### Preparación fresh-start (antes de corrida 1)", "",
                      f"Duración total: {prep['duracion_total_segundos']:,.2f} s.", "",
                      "| Etapa | Segundos |", "|---|---:|"])
        for name, item in prep["etapas"].items():
            lines.append(f"| `{name}` | {item['segundos']:,.2f} |")
        lines.append("")
        lines.extend(["## Requisito 1.1: conteos oficiales Proyecto 2 contra Bronze", "",
                      "Las diferencias se conservan para su explicación; no detienen las dos corridas.",
                      "El código de salida del flujo sigue evaluando idempotencia y la referencia Gold.", ""])
        for number, run in ((1, first), (2, second)):
            lines.extend([f"### Requisito 1.1 — Corrida {number}", "", *render_load_evidence(run["requisito_1_1"])])
    for title, key in (("Bronze (filas por fuente)", "bronze"),
                       ("Staging PostgreSQL", "staging"), ("Silver dbt", "silver"),
                       ("Gold dbt (granos diferentes)", "gold"), ("Vistas Tableau", "tableau"),
                       ("Gold abordajes por modo", "gold_abordajes_por_modo")):
        lines.extend(render_table(title, a[key], b[key]))
    lines.extend(["## Resumen dbt capturado automáticamente", "",
                  "Los estados proceden del run_results.json del build de cada corrida; no de cifras fijas.", "",
                  "| Corrida | Pruebas PASS | Modelos success | Hooks success | Warnings | Errores | Skips |",
                  "|---|---:|---:|---:|---:|---:|---:|"])
    for label, run in ((1, first), (2, second)):
        item = run["etapas"]["dbt_build"]["resumen_dbt"]
        lines.append(f"| {label} | {item['pruebas_pass']} | {item['modelos_success']} | "
                     f"{item['hooks_success']} | {item['warnings']} | {item['errores']} | {item['skips']} |")
    lines.extend(["", "## Fingerprints de contenido de negocio", "",
                  "MD5 de concatenación ordenada de MD5 de filas JSONB: conserva multiplicidad y no depende del orden físico.",
                  "Se comparan por separado todas las relaciones Silver, Gold y las seis vistas, sin equiparar sus granos.",
                  "Únicamente se excluyen bridge_identidad_usuario.fecha_proceso y silver_cuarentena.fecha_deteccion,",
                  "campos de auditoría no deterministas. No se afirma idempotencia byte a byte de esas tablas.", "",
                  "| Relación | Fingerprint corrida 1 | Fingerprint corrida 2 | Comparación |",
                  "|---|---|---|---|"])
    for name in sorted(a["fingerprints_negocio"].keys() | b["fingerprints_negocio"].keys()):
        one, two = a["fingerprints_negocio"].get(name), b["fingerprints_negocio"].get(name)
        lines.append(f"| `{name}` | {one['fingerprint'] if one else 'AUSENTE'} | "
                     f"{two['fingerprint'] if two else 'AUSENTE'} | {'IGUALES' if one == two else 'DIFERENTES'} |")
    lines.extend(["## Streaming y deduplicación", "",
                  "| Fuente | Corrida | Mensajes consumidos | Nuevos Bronze | Omitidos por `_event_id` |",
                  "|---|---:|---:|---:|---:|"])
    for label, run in ((1, first), (2, second)):
        for mode in ("transmetro", "aerometro"):
            item = run["etapas"][f"streaming_{mode}"]
            lines.append(f"| {mode} | {label} | {item['mensajes_consumidos']:,} | "
                         f"{item['eventos_nuevos']:,} | {item['duplicados_tecnicos']:,} |")
    lines.extend(["", "## Duración de etapas", "",
                  "| Etapa | Corrida 1 (s) | Corrida 2 (s) |", "|---|---:|---:|"])
    for name in first["etapas"]:
        def duration(run: dict) -> float:
            item = run["etapas"][name]
            return (item["producer"]["segundos"] + item["consumer"]["segundos"]
                    if "producer" in item else item["segundos"])
        lines.append(f"| `{name}` | {duration(first):,.2f} | {duration(second):,.2f} |")
    lines.extend(["", "## Hallazgo y corrección", "",
                  "Antes de la orquestación, los productores podían informar entregas Kafka fallidas",
                  "en el callback y aun así terminar con código cero. Ahora contabilizan esas fallas",
                  "y devuelven código distinto de cero para detener Prefect.", "",
                  "Los consumidores esperan la asignación de partición antes de medir inactividad.",
                  "Los productores aplican espera acotada ante presión de la cola Kafka.",
                  "La cantidad consumida puede superar las filas Raw si existen publicaciones",
                  "anteriores; la deduplicación por `_event_id` impide agregar copias a Bronze.", "",
                  "La definición Docker asigna 1 GB de /dev/shm a PostgreSQL para las consultas paralelas.",
                  ("fresh-start recreó los contenedores y el volumen antes de la primera corrida." if project2 else
                   "Aplicar esa definición requiere recrear el contenedor conservando su volumen, fuera de este reporte."), "",
                  f"Los archivos `{first_path.name}` y `{second_path.name}` contienen los SHA-256",
                  "Raw, filas Parquet, conteos, fingerprints, duraciones y resumen dbt de cada corrida.", ""])
    with report_path.open("w" if args.overwrite else "x", encoding="utf-8", newline="\n") as file:
        file.write("\n".join(lines))
    print(f"Comparación: {'IGUALES' if equal else 'DIFERENTES'}; referencia {reference_label}: {'OK' if expected else 'DIFERENTE'}")
    return 0 if equal and expected else 1


if __name__ == "__main__":
    raise SystemExit(main())
