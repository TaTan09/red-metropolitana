#!/usr/bin/env python3
"""Ejecuta los modelos reales contra Silver completo y recortado físicamente.

Sólo crea tablas TEMP dentro de una transacción REPEATABLE READ que se revierte.
No compara etiquetas: necesitan el horizonte futuro por definición.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from collections import Counter
from datetime import datetime
from pathlib import Path

import psycopg
from dotenv import load_dotenv
from jinja2 import Environment, StrictUndefined
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[1]
PROJECT = ROOT / 'dbt/red_metropolitana'
FEATURES = ('viajes_28d', 'viajes_7d', 'viajes_14d', 'dias_activos_28d',
            'dias_desde_ultimo_uso', 'gasto_28d_gtq', 'tarifa_media_gtq',
            'puntos_origen_28d', 'proporcion_hora_pico', 'proporcion_fin_semana')
BASES = {
    'silver_transmetro_validaciones': 'fecha_hora',
    'silver_transurbano_transacciones': 'fecha_hora',
    'silver_aerometro_boardings': 'fecha_hora',
    'silver_metroriel_viajes': 'fecha_hora_ingreso',
    'silver_padron_transmetro_scd2': 'valid_from',
}
MODELS = {
    'silver_p2_usos_tarjeta': 'p2_12',
    'silver_p2_poblacion_tarjeta': 'p2_12',
    'silver_p2_features_tarjeta': 'p2_13',
}


def render_model(name, *, refs=None, variables=None, only_a=False):
    refs, variables = refs or {}, variables or {}
    env = Environment(undefined=StrictUndefined)
    env.globals.update(config=lambda **kwargs: '',
                       ref=lambda key: refs.get(key, f'silver.{key}'),
                       var=lambda key, default: variables.get(key, default))
    macro = env.from_string((PROJECT / 'macros/p2_12_cortes.sql').read_text(encoding='utf-8')).module
    def cuts(incluir_c=False):
        sql = macro.p2_12_cortes(incluir_c=incluir_c)
        return f"select * from ({sql}) cortes_a where corte = 'A'" if only_a else sql
    env.globals['p2_12_cortes'] = cuts
    return env.from_string((PROJECT / f'models/silver/{MODELS[name]}/{name}.sql').read_text(encoding='utf-8')).render()


def connect():
    load_dotenv(ROOT / '.env')
    return psycopg.connect(host=os.getenv('POSTGRES_HOST', 'localhost'),
                           port=os.getenv('POSTGRES_PORT', '5432'),
                           dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'],
                           password=os.environ['POSTGRES_PASSWORD'], connect_timeout=10, row_factory=dict_row)


def compare_rows(full, trimmed):
    """Compara claves completas y todas las columnas predictoras, sin redondeo."""
    keys = ('unidad_id', 'fecha_corte')
    columns = ('operador', *FEATURES)
    def index(rows):
        result = {}
        for row in rows:
            if set(row) != {*keys, 'corte', 'etiqueta', *columns}:
                raise ValueError('El esquema cambió: actualizar explícitamente las columnas auditadas')
            key = tuple(row[k] for k in keys)
            if key in result:
                raise ValueError(f'Clave duplicada: {key}')
            result[key] = row
        return result
    left, right = index(full), index(trimmed)
    counts = Counter()
    for key in sorted(left.keys() | right.keys()):
        if key not in left or key not in right:
            counts['__fila_ausente__'] += 1
        else:
            for col in columns:
                if left[key][col] != right[key][col]:
                    counts[col] += 1
    if not left or not right:
        raise ValueError('Auditoría vacía: no demuestra invariancia')
    return {'filas_completas': len(left), 'filas_recortadas': len(right),
            'filas_comparadas': len(left.keys() & right.keys()),
            'columnas_evaluadas': list(columns), 'cantidad_columnas': len(columns),
            'diferencias': sum(counts.values()), 'diferencias_por_columna': dict(sorted(counts.items()))}


def audit(conn, *, variables=None, source_schema='silver'):
    if not re.fullmatch(r'[a-z_][a-z_0-9]*', source_schema):
        raise ValueError('Esquema de origen inválido')
    # A se obtiene del mismo parámetro que dbt; no hay otra fecha hardcodeada.
    cuts = Environment()
    cuts.globals['var'] = lambda key, default: (variables or {}).get(key, default)
    macro = cuts.from_string((PROJECT / 'macros/p2_12_cortes.sql').read_text(encoding='utf-8')).module
    cutoff = conn.execute(f"select fecha_corte from ({macro.p2_12_cortes()}) c where corte='A'").fetchone()['fecha_corte']
    snapshots = []
    removed = {}
    for mode in ('completo', 'recortado'):
        refs = {name: f'{source_schema}.{name}' for name in (*BASES, 'silver_cuarentena')}
        if mode == 'recortado':
            for name, date_col in BASES.items():
                target = f'audit_trim_{name}'
                extra = ' and fecha_hora_salida < %(cutoff)s' if name == 'silver_metroriel_viajes' else ''
                conn.execute(f'create temp table {target} on commit drop as select * from {source_schema}.{name} '
                             f'where {date_col} < %(cutoff)s{extra}', {'cutoff': cutoff})
                refs[name] = target
                removed[name] = conn.execute(f'select (select count(*) from {source_schema}.{name}) '
                                            f'- (select count(*) from {target}) as n').fetchone()['n']
        for name in MODELS:
            target = f'audit_{mode}_{name}'
            conn.execute(f'create temp table {target} on commit drop as '
                         + render_model(name, refs=refs, variables=variables, only_a=True))
            refs[name] = target
        snapshots.append(conn.execute(f'select * from {target} order by unidad_id, fecha_corte').fetchall())
    result = compare_rows(*snapshots)
    result.update(fecha_corte=str(cutoff), registros_eliminados_por_fuente=removed,
                  etiqueta_comparada=False, alcance='Silver operacional y CDC; no reconstruye ingesta/Staging',
                  sql_sha256={name: hashlib.sha256(render_model(name, variables=variables).encode()).hexdigest() for name in MODELS})
    if not sum(removed.values()):
        raise ValueError('No existen registros futuros para probar su exclusión')
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--vars', type=json.loads, default={})
    parser.add_argument('--dataset-label', required=True,
                        help='Identificación explícita del dataset verificado; no inferir Proyecto 2 por las fechas')
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    with connect() as conn:
        conn.execute('set transaction isolation level repeatable read')
        result = audit(conn, variables=args.vars)
        conn.rollback()
    result['ejecutado_en'] = datetime.now().astimezone().isoformat()
    result['dataset'] = args.dataset_label
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as file:
        json.dump(result, file, ensure_ascii=False, indent=2)
        file.write('\n')
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return int(result['diferencias'] != 0)


if __name__ == '__main__':
    raise SystemExit(main())
