"""Entrada portable de Silver y recálculo C en tablas TEMP; no depende de Silver vivo."""
from __future__ import annotations
import argparse
import csv
from datetime import date, datetime, timezone
import json
from pathlib import Path
import sys
import time
from jinja2 import Environment, StrictUndefined

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import p2_24 as m

# Proyección mínima de fuentes; ningún archivo contiene etiquetas A/B/C.
SCHEMAS = {
 'silver_transmetro_validaciones': [('bronze_record_id','text'),('tarjeta_id','text'),('fecha_hora','timestamp'),('tarifa_quetzales','numeric'),('estacion_id','text')],
 'silver_transurbano_transacciones': [('bronze_record_id','text'),('id_tarjeta','text'),('fecha_hora','timestamp'),('tarifa_quetzales','numeric'),('cod_parada','text')],
 'silver_aerometro_boardings': [('bronze_record_id','text'),('user_hash','text'),('fecha_hora','timestamp'),('tarifa_quetzales','numeric'),('station_code','text')],
 'silver_metroriel_viajes': [('bronze_record_id','text'),('tarjeta_mr','text'),('fecha_hora_ingreso','timestamp'),('fecha_hora_salida','timestamp'),('tarifa_quetzales','numeric'),('origen_estacion_id','text')],
 'silver_padron_transmetro_scd2': [('tarjeta_id','text'),('operacion','text'),('valid_from','timestamp')],
 'silver_cuarentena': [('fuente','text'),('id_registro_crudo','text')],
}
FORMAT = 'p2-24-silver-csv-v1'

def cutoff(value):
    parsed = date.fromisoformat(value)
    if parsed.isoformat() != value or value != '2026-08-30':
        raise ValueError('Esta entrega admite exclusivamente C: 2026-08-30; nunca evalúa B')
    return value

def source_refs():
    return {name: f'pg_temp.entrada_{i}' for i, name in enumerate(SCHEMAS)}

def render(name, refs, cut):
    cut = cutoff(cut)
    env = Environment(undefined=StrictUndefined)
    env.globals.update(config=lambda **kwargs: '', ref=lambda key: refs[key],
        p2_12_cortes=lambda **kwargs: f"select 'C'::text as corte, '{cut}'::timestamp as fecha_corte")
    folder = ROOT / 'dbt/red_metropolitana/models/silver'
    group = 'p2_13' if name == 'silver_p2_features_tarjeta' else 'p2_12'
    return env.from_string((folder / group / f'{name}.sql').read_text(encoding='utf-8')).render()

def read_manifest(folder, cut):
    folder = Path(folder).resolve()
    if not (folder / 'manifest.json').is_file():
        folder = folder / 'p2-24-entrada'
    path = folder / 'manifest.json'
    manifest = json.loads(path.read_text(encoding='utf-8'))
    if manifest['formato'] != FORMAT or manifest['fecha_corte'] != cutoff(cut):
        raise ValueError('Formato o fecha de entrada incorrectos')
    if set(manifest['fuentes']) != set(SCHEMAS):
        raise ValueError('Se requieren las seis fuentes Silver del contrato')
    for name, columns in SCHEMAS.items():
        entry = manifest['fuentes'][name]
        if entry['archivo'] != f'{name}.csv' or entry['filas'] < 0:
            raise ValueError('Ruta o conteo de fuente inválido')
        p = folder / entry['archivo']
        if m.sha256(p) != entry['sha256']:
            raise ValueError(f'Hash de entrada incorrecto: {name}')
        with p.open(encoding='utf-8', newline='') as f:
            if next(csv.reader(f), None) != [col for col, _ in columns]:
                raise ValueError(f'Columnas de entrada incorrectas: {name}')
    return folder, manifest

def calculate(folder, cut):
    folder, manifest = read_manifest(folder, cut)
    started = time.perf_counter()
    refs = source_refs()
    # Sólo el motor PostgreSQL es externo. Todas las fuentes se cargan desde --datos.
    with m.training.connect() as conn:
        # PostgreSQL prohíbe CREATE TEMP en una transacción READ ONLY.
        # Todas las escrituras son TEMP ON COMMIT DROP y se revierten al terminar.
        conn.execute('set transaction isolation level repeatable read')
        for name, cols in SCHEMAS.items():
            table = refs[name].split('.')[-1]
            definitions = ', '.join(f'{col} {kind}' for col, kind in cols)
            conn.execute(f'create temp table {table} ({definitions}) on commit drop')
            with conn.cursor().copy(f'copy {table} from stdin with (format csv, header true)') as copy:
                with (folder / f'{name}.csv').open('rb') as f:
                    for chunk in iter(lambda: f.read(1024 * 1024), b''):
                        copy.write(chunk)
            actual = conn.execute(f'select count(*) as n from {table}').fetchone()['n']
            if actual != manifest['fuentes'][name]['filas']:
                raise ValueError(f'Conteo de entrada distinto al manifest: {name}')
            conn.execute(f'analyze {table}')
        loaded = time.perf_counter()
        for name in ('silver_p2_usos_tarjeta', 'silver_p2_poblacion_tarjeta', 'silver_p2_features_tarjeta'):
            temp = {'silver_p2_usos_tarjeta':'usos_c', 'silver_p2_poblacion_tarjeta':'poblacion_c',
                    'silver_p2_features_tarjeta':'features_c'}[name]
            sql = render(name, refs, cut)
            conn.execute(f'create temp table {temp} on commit drop as {sql}')
            conn.execute(f'analyze {temp}')
            refs[name] = f'pg_temp.{temp}'
        fields = ', '.join(f'f.{c}' for c in m.training.PREDICTORS)
        rows = conn.execute(f'''select f.unidad_id, p.llave_operacional as tarjetas, {fields}
            from pg_temp.features_c f join pg_temp.poblacion_c p using (unidad_id, fecha_corte)
            order by f.unidad_id''').fetchall()
        conn.rollback()
    data = m.validate_features(rows)
    return data, {'segundos_carga_temp': loaded - started,
                  'segundos_features_y_validacion': time.perf_counter() - loaded,
                  'entrada_manifest_sha256': m.sha256(folder / 'manifest.json'),
                  'features_sha256': m.frame_hash(data),
                  'fuentes': manifest['fuentes']}

def prepare(output, cut):
    cut = cutoff(cut)
    output = Path(output)
    if output.exists():
        raise FileExistsError('La carpeta destino ya existe; usar otra para preservar entradas')
    output.mkdir(parents=True)
    started = time.perf_counter()
    manifest = {'formato': FORMAT, 'fecha_corte': cut, 'creado_en_utc': datetime.now(timezone.utc).isoformat(),
                'origen': 'Proyecciones Silver P2 previas al corte; sin etiquetas; cuarentena por evento',
                'fuentes': {}}
    with m.training.connect() as conn:
        conn.execute('set transaction isolation level repeatable read, read only')
        for name, cols in SCHEMAS.items():
            columns = ', '.join(c for c, _ in cols)
            if name == 'silver_cuarentena':
                condition = 'true'
            elif name == 'silver_padron_transmetro_scd2':
                condition = f"valid_from < timestamp '{cut}'"
            elif name == 'silver_metroriel_viajes':
                condition = f"fecha_hora_ingreso < timestamp '{cut}' and fecha_hora_salida < timestamp '{cut}'"
            else:
                condition = f"fecha_hora < timestamp '{cut}'"
            query = f'select {columns} from silver.{name} where {condition}'
            p = output / f'{name}.csv'
            with p.open('xb') as f, conn.cursor().copy(f'copy ({query}) to stdout with (format csv, header true)') as copy:
                for chunk in copy:
                    f.write(chunk)
            n = conn.execute(f'select count(*) as n from silver.{name} where {condition}').fetchone()['n']
            manifest['fuentes'][name] = {'archivo': p.name, 'filas': n, 'sha256': m.sha256(p)}
        # Referencia independiente para comprobar identidad y features frente al Silver original.
        fields = ', '.join(f'f.{c}' for c in m.training.PREDICTORS)
        rows = conn.execute(f'''select f.unidad_id, p.llave_operacional as tarjetas, {fields}
            from silver.silver_p2_features_tarjeta f
            join silver.silver_p2_poblacion_tarjeta p using (unidad_id, fecha_corte)
            where f.corte='C' and f.fecha_corte=timestamp '{cut}' order by f.unidad_id''').fetchall()
    reference = m.validate_features(rows)
    manifest['referencia_silver_c'] = {'filas':len(reference), 'features_sha256':m.frame_hash(reference),
                                     'identidades_sha256':m.frame_hash(reference[['unidad_id','tarjetas']])}
    manifest['segundos_exportacion'] = time.perf_counter() - started
    m.write_json(output / 'manifest.json', manifest)
    return manifest

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=ROOT / 'datos_red/p2-24-entrada')
    parser.add_argument('--fecha-corte', required=True)
    args = parser.parse_args(argv)
    try:
        result = prepare(args.salida, args.fecha_corte)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Error preparando datos: {exc}\n')
    print(json.dumps(result, indent=2, ensure_ascii=False))

if __name__ == '__main__':
    main()
