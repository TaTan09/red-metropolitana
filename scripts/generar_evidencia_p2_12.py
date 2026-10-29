#!/usr/bin/env python3
"""Verifica y exporta el requisito 1.2 desde PostgreSQL en transacción READ ONLY.

No construye modelos, no ingiere datos y no ejecuta Docker ni el pipeline.
"""
from __future__ import annotations

import argparse
import csv
import json
import os
import re
from datetime import datetime, timedelta
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_CUTS = {"A": datetime(2026, 7, 1), "B": datetime(2026, 7, 31)}

# Recalcular el universo completo, no sólo revisar las filas ya seleccionadas.
# Los SUM condicionales son independientes de los CTE previos/futuros del modelo.
VALIDATION_SQL = """
with cortes as (
    select corte, fecha_corte from silver.silver_p2_costo_tarjeta
), conteos as (
    select c.corte, c.fecha_corte, u.operador, u.llave_operacional,
        sum(case when u.fecha_uso < c.fecha_corte and u.disponible_desde < c.fecha_corte
                 then 1 else 0 end) as previos,
        sum(case when u.fecha_uso >= c.fecha_corte then 1 else 0 end) as futuros
    from cortes c
    join silver.silver_p2_usos_tarjeta u
      on u.fecha_uso >= c.fecha_corte - interval '28 days'
     and u.fecha_uso < c.fecha_corte + interval '30 days'
     and u.disponible_desde < c.fecha_corte + interval '30 days'
    group by c.corte, c.fecha_corte, u.operador, u.llave_operacional
), esperado as (
    select * from conteos n
    where n.previos >= 2
      and not exists (
          select 1 from silver.silver_padron_transmetro_scd2 d
          where n.operador = 'Transmetro' and d.tarjeta_id = n.llave_operacional
            and d.operacion = 'DELETE' and d.valid_from < n.fecha_corte
      )
)
select count(*) as diferencias
from esperado e
full join silver.silver_p2_poblacion_tarjeta p
  on p.corte = e.corte and p.operador = e.operador and p.llave_operacional = e.llave_operacional
where e.corte is null or p.corte is null
   or p.fecha_corte is distinct from e.fecha_corte
   or p.unidad_id is distinct from md5(e.operador || ':' || e.llave_operacional)
   or p.eventos_previos_28d is distinct from e.previos
   or p.eventos_futuros_30d is distinct from e.futuros
   or p.etiqueta is distinct from case when e.futuros = 0 then 1 else 0 end
"""

COST_VALIDATION_SQL = """
with identidades_futuras as (
    select c.corte, b.usuario_canonico_id, array_agg(distinct u.operador) as operadores
    from silver.silver_p2_costo_tarjeta c
    join silver.silver_p2_usos_tarjeta u
      on u.fecha_uso >= c.fecha_corte and u.fecha_uso < c.fecha_corte + interval '30 days'
     and u.disponible_desde < c.fecha_corte + interval '30 days'
    join silver.bridge_identidad_usuario b
      on b.sistema_origen = u.operador and b.llave_origen = u.llave_operacional
    where b.metodo_match = 'PATRON_NUMERICO_INFERIDO'
      and b.usuario_canonico_id like 'USR-%' and b.sistema_origen <> 'Aerometro'
    group by c.corte, b.usuario_canonico_id
)
select p.corte, count(*) filter (
    where cardinality(array_remove(f.operadores, p.operador)) > 0
      and origen.metodo_match = 'PATRON_NUMERICO_INFERIDO'
      and p.operador <> 'Aerometro'
) as costo_recalculado
from silver.silver_p2_poblacion_tarjeta p
left join silver.bridge_identidad_usuario origen
  on origen.sistema_origen = p.operador and origen.llave_origen = p.llave_operacional
left join identidades_futuras f
  on f.corte = p.corte and f.usuario_canonico_id = origen.usuario_canonico_id
where p.etiqueta = 1
group by p.corte
"""

COVERAGE_SQL = """
select c.corte, u.operador, min(u.fecha_uso) as primer_uso, max(u.fecha_uso) as ultimo_uso,
       count(distinct u.fecha_uso::date) filter (
           where u.fecha_uso >= c.fecha_corte - interval '28 days'
             and u.fecha_uso < c.fecha_corte and u.disponible_desde < c.fecha_corte
       ) as dias_con_usos_previos,
       count(distinct u.fecha_uso::date) filter (
           where u.fecha_uso >= c.fecha_corte
             and u.fecha_uso < c.fecha_corte + interval '30 days'
             and u.disponible_desde < c.fecha_corte + interval '30 days'
       ) as dias_con_usos_futuros
from silver.silver_p2_costo_tarjeta c cross join silver.silver_p2_usos_tarjeta u
group by c.corte, u.operador order by c.corte, u.operador
"""


def collect_evidence(conn) -> dict:
    if conn.execute("show transaction_read_only").fetchone()["transaction_read_only"] != "on":
        raise RuntimeError("La evidencia requiere una transacción de sólo lectura")
    summary = conn.execute("select * from silver.silver_p2_costo_tarjeta order by corte").fetchall()
    if {r["corte"]: r["fecha_corte"] for r in summary} != EXPECTED_CUTS or len(summary) != 2:
        raise RuntimeError("El warehouse no contiene exactamente los cortes A/B solicitados")
    validation = conn.execute(VALIDATION_SQL).fetchone()["diferencias"]
    if validation:
        raise RuntimeError(f"El recálculo independiente detectó {validation} diferencias de población/etiqueta")
    costs = {r["corte"]: r["costo_recalculado"] for r in conn.execute(COST_VALIDATION_SQL).fetchall()}
    cost_differences = sum(costs.get(r["corte"], 0) != r["positivos_con_actividad_otro_operador"] for r in summary)
    if cost_differences:
        raise RuntimeError("El costo no coincide con el recálculo por operadores futuros de cada identidad inferida")
    operators = conn.execute("""select corte, operador, count(*) as poblacion,
        count(*) filter(where etiqueta=1) as positivos
        from silver.silver_p2_poblacion_tarjeta group by 1,2 order by 1,2""").fetchall()
    for row in summary:
        own = [r for r in operators if r["corte"] == row["corte"]]
        if (sum(r["poblacion"] for r in own) != row["poblacion"]
                or sum(r["positivos"] for r in own) != row["positivos"]
                or not 0 <= row["positivos_con_actividad_otro_operador"] <= row["positivos"]):
            raise RuntimeError("Resumen inconsistente con la población materializada")
    coverage = conn.execute(COVERAGE_SQL).fetchall()
    full_coverage = (len(coverage) == 8 and all(r["dias_con_usos_previos"] == 28
                                             and r["dias_con_usos_futuros"] == 30 for r in coverage))
    return {"requisito": "1.2", "unidad": "(operador, llave_operacional)",
            "verificado_en": conn.execute("select current_timestamp at time zone 'America/Guatemala' as fecha").fetchone()["fecha"],
            "verificacion": {"transaccion_solo_lectura": True, "diferencias_recalculo": validation,
                             "diferencias_costo": cost_differences,
                             "cobertura_diaria_28_y_30_dias": full_coverage},
            "politica_cdc": "Cualquier DELETE Transmetro con valid_from < fecha_corte excluye; reactivación no anula exclusión.",
            "metroriel": "Un uso por viaje cerrado, fechado por ingreso y disponible desde salida; cierre anterior al límite de cada ventana.",
            "limitacion_identidad": "Costo por patrón numérico inferido P1; no identidad personal verificada. Aerómetro aislado; cero enlaces detectables no significa cero actividad real cruzada.",
            "resultados": summary, "por_operador": operators, "cobertura": coverage}


def fraction(numerator, denominator) -> str:
    return f"{numerator} / {denominator}"


def percent(value) -> str:
    return "No definida" if value is None else f"{100 * value:.6f} %"


def render_markdown(evidence: dict) -> str:
    lines = ["# Proyecto 2 — Requisito 1.2: TARJETA", "",
             f"Verificado contra PostgreSQL: {evidence['verificado_en']} (America/Guatemala).", "",
             "Grano: tarjeta operacional `(operador, llave_operacional)` por corte. El ID no es usuario_canonico_id.",
             "Cada fila conserva unidad_id, operador, llave_operacional, corte, fecha_corte y etiqueta en silver.silver_p2_poblacion_tarjeta.", "",
             "## Ventanas y reglas", "",
             "| Corte | fecha_corte | Población: intervalo previo | Etiqueta: intervalo futuro |",
             "|---|---|---|---|"]
    for row in evidence["resultados"]:
        cut = row["fecha_corte"]
        lines.append(f"| {row['corte']} | {cut} | [{cut - timedelta(days=28)}, {cut}) | [{cut}, {cut + timedelta(days=30)}) |")
    lines.extend(["", "Población: al menos 2 usos válidos disponibles antes del corte en los 28 días previos. No se usan usos futuros ni la etiqueta para incluir tarjetas.",
                  "Etiqueta: 1 si hay 0 usos válidos de esa tarjeta en los siguientes 30 días; 0 si hay uno o más. El extremo superior de ambas ventanas es exclusivo.",
                  evidence["politica_cdc"], evidence["metroriel"],
                  "Sólo Silver; los IDs presentes en silver_cuarentena se excluyen por operador y registro Bronze. No se usa el estado vigente actual del padrón.", "",
                  "## Población y etiqueta", "",
                  "| Corte | Población | Positivos | Cuenta completa | Tasa positiva |",
                  "|---|---:|---:|---|---:|"])
    for row in evidence["resultados"]:
        lines.append(f"| {row['corte']} | {row['poblacion']} | {row['positivos']} | {fraction(row['positivos'], row['poblacion'])} | {percent(row['tasa_positiva'])} |")
    lines.extend(["", "## Costo observable de elegir TARJETA", "", evidence["limitacion_identidad"],
                  "Se cuenta cada positivo una sola vez si otra llave de la identidad inferida tiene uso futuro válido en un operador distinto, aunque esa otra llave no pertenezca a la población.",
                  "Esta métrica no modifica etiquetas. B se reporta exclusivamente como entregable; no se usa para decisiones de modelado ni se entrenó un modelo.", "",
                  "| Corte | Positivos totales | Con actividad en otro operador | Cuenta completa | Proporción | Positivos Aerómetro sin enlace medible |",
                  "|---|---:|---:|---|---:|---:|"])
    for row in evidence["resultados"]:
        lines.append(f"| {row['corte']} | {row['positivos']} | {row['positivos_con_actividad_otro_operador']} | {fraction(row['positivos_con_actividad_otro_operador'], row['positivos'])} | {percent(row['proporcion_costo'])} | {row['positivos_aerometro']} |")
    lines.extend(["", "## Desglose por operador", "", "| Corte | Operador | Población | Positivos |", "|---|---|---:|---:|"])
    for row in evidence["por_operador"]:
        lines.append(f"| {row['corte']} | {row['operador']} | {row['poblacion']} | {row['positivos']} |")
    lines.extend(["", "## Verificación y cobertura", "",
                  f"Diferencias contra recálculo independiente del universo completo: {evidence['verificacion']['diferencias_recalculo']}.",
                  f"Cortes con diferencias contra recálculo independiente del costo: {evidence['verificacion']['diferencias_costo']}.",
                  f"28/30 fechas con usos por operador: {evidence['verificacion']['cobertura_diaria_28_y_30_dias']}.",
                  "La cobertura diaria constata datos en cada fecha; no certifica exhaustividad de registros ni continuidad de identidad personal.", "",
                  "| Corte | Operador | Días previos con usos | Días futuros con usos | Primer uso observado | Último uso observado |",
                  "|---|---|---:|---:|---|---|"])
    for row in evidence["cobertura"]:
        lines.append(f"| {row['corte']} | {row['operador']} | {row['dias_con_usos_previos']} | {row['dias_con_usos_futuros']} | {row['primer_uso']} | {row['ultimo_uso']} |")
    if not evidence["verificacion"]["cobertura_diaria_28_y_30_dias"]:
        lines.extend(["", "**REVISAR COBERTURA: faltan fechas con usos en alguna ventana/operador; no interpretar ausencia como inactividad sin revisar la fuente.**"])
    return "\n".join(lines) + "\n"


def write_evidence(evidence: dict, paths: list[Path], *, overwrite: bool) -> None:
    mode = "w" if overwrite else "x"
    paths[0].parent.mkdir(parents=True, exist_ok=True)
    with paths[0].open(mode, encoding="utf-8", newline="\n") as file:
        file.write(render_markdown(evidence))
    with paths[1].open(mode, encoding="utf-8", newline="") as file:
        columns = ["corte", "fecha_corte", "poblacion", "positivos", "tasa_positiva",
                   "positivos_poblacion", "positivos_con_actividad_otro_operador", "proporcion_costo",
                   "costo_positivos", "positivos_aerometro"]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in evidence["resultados"]:
            writer.writerow({**row, "positivos_poblacion": fraction(row["positivos"], row["poblacion"]),
                             "costo_positivos": fraction(row["positivos_con_actividad_otro_operador"], row["positivos"])})
    with paths[2].open(mode, encoding="utf-8", newline="\n") as file:
        json.dump(evidence, file, ensure_ascii=False, indent=2, default=str)
        file.write("\n")


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-prefix", default="p2-12-tarjeta")
    parser.add_argument("--output-dir", type=Path, default=ROOT / "docs/metricas")
    parser.add_argument("--overwrite", action="store_true")
    args = parser.parse_args(argv)
    if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_-]*", args.output_prefix):
        parser.error("Prefijo inválido")
    paths = [args.output_dir / f"{args.output_prefix}.{extension}" for extension in ("md", "csv", "json")]
    if any(p.is_dir() or (p.exists() and not args.overwrite) for p in paths):
        parser.error("Destino existente; use otro prefijo o --overwrite explícito para archivos")
    load_dotenv(ROOT / ".env")
    with psycopg.connect(host=os.getenv("POSTGRES_HOST", "localhost"), port=os.getenv("POSTGRES_PORT", "5432"),
                         dbname=os.environ["POSTGRES_DB"], user=os.environ["POSTGRES_USER"],
                         password=os.environ["POSTGRES_PASSWORD"], connect_timeout=10, row_factory=dict_row,
                         options="-c default_transaction_read_only=on -c statement_timeout=300000") as conn:
        conn.execute("set transaction isolation level repeatable read, read only")
        evidence = collect_evidence(conn)
        conn.rollback()
    write_evidence(evidence, paths, overwrite=args.overwrite)
    for row in evidence["resultados"]:
        print(f"{row['corte']}: positivos/población={row['positivos']}/{row['poblacion']} "
              f"({percent(row['tasa_positiva'])}); costo={row['positivos_con_actividad_otro_operador']}/{row['positivos']} "
              f"({percent(row['proporcion_costo'])})")
    print("Verificación independiente sin diferencias. Evidencia: " + ", ".join(p.name for p in paths))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
