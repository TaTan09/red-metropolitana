#!/usr/bin/env python3
"""Resume y verifica la tabla materializada de features sin exportar tarjetas."""
from __future__ import annotations

import argparse
import hashlib
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.auditar_fuga_p2_13 import FEATURES, connect  # noqa: E402


def summarize(rows):
    summaries = {}
    hashes = {}
    previous = None
    for row in rows:
        key = (row['unidad_id'], row['fecha_corte'])
        if previous is not None and key <= previous:
            raise ValueError('Filas desordenadas o clave (unidad_id, fecha_corte) duplicada')
        previous = key
        cut = row['corte']
        if cut not in ('A', 'B', 'C'):
            raise ValueError(f'Corte desconocido: {cut}')
        if any(row[name] is None for name in (*FEATURES, 'operador')):
            raise ValueError('Hay predictores nulos')
        if (cut == 'C' and row['etiqueta'] is not None) or (cut != 'C' and row['etiqueta'] not in (0, 1)):
            raise ValueError('Etiqueta inválida para el corte')
        entry = summaries.setdefault(cut, {'corte': cut, 'fecha_corte': str(row['fecha_corte']),
                                           'filas': 0, 'etiquetas_nulas': 0})
        if entry['fecha_corte'] != str(row['fecha_corte']):
            raise ValueError('Un corte tiene más de una fecha')
        entry['filas'] += 1
        entry['etiquetas_nulas'] += row['etiqueta'] is None
        digest = hashes.setdefault(cut, hashlib.sha256())
        digest.update((json.dumps(row, sort_keys=True, default=str, ensure_ascii=False,
                                  separators=(',', ':')) + '\n').encode('utf-8'))
    if set(summaries) != {'A', 'B', 'C'}:
        raise ValueError('Se requieren poblaciones no vacías en A, B y C')
    return [{**summaries[cut], 'sha256_filas_ordenadas': hashes[cut].hexdigest()} for cut in ('A', 'B', 'C')]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args(argv)
    if args.output.exists():
        raise FileExistsError(args.output)
    with connect() as conn:
        conn.execute('set transaction isolation level repeatable read, read only')
        with conn.cursor(name='evidencia_features') as cursor:
            cursor.execute('select * from silver.silver_p2_features_tarjeta order by unidad_id, fecha_corte')
            results = summarize(cursor)
        time = conn.execute("select current_timestamp at time zone 'America/Guatemala' as t").fetchone()['t']
        conn.rollback()
    report = {'tabla': 'silver.silver_p2_features_tarjeta', 'verificado_en': str(time),
              'predictores_numericos': list(FEATURES), 'predictor_categorico': 'operador',
              'clave': ['unidad_id', 'fecha_corte'], 'cortes': results,
              'nulos_predictores': 0, 'duplicados': 0,
              'huella': 'SHA256 de JSON por fila con claves ordenadas, NUMERIC como texto; orden unidad_id/fecha_corte; incluye etiqueta'}
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open('x', encoding='utf-8') as file:
        json.dump(report, file, indent=2, ensure_ascii=False)
        file.write('\n')
    print(json.dumps(report, indent=2, ensure_ascii=False))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
