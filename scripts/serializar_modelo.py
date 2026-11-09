"""Ajusta sólo A con el modelo oficial y guarda el Pipeline completo."""
from __future__ import annotations
import argparse
from datetime import datetime, timezone
from pathlib import Path
import subprocess
import sys
import time
import joblib
from threadpoolctl import threadpool_limits
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import p2_24 as m

def train(output=m.MODEL):
    output = Path(output)
    metadata = output.with_suffix('.json')
    if output.exists() or metadata.exists():
        raise FileExistsError('Artefacto ya existe: elegir otra versión/ruta, no sobrescribir')
    d, e = m.official()
    started = time.perf_counter()
    data = m.training.load_cut_a(recalculate=True)
    if m.training.sha256(data.to_csv(index=False, lineterminator='\n')) != e['entrada_sha256']:
        raise ValueError('Entrenamiento A distinto al de 2.1')
    loaded = time.perf_counter()
    model = m.training.build_model(d['configuracion'])
    with threadpool_limits(limits=1):
        model.fit(data[d['predictores']], data['etiqueta'])
    fitted = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, output, compress=3)
    meta = {'modelo_version': m.VERSION, 'modelo': d['modelo'], 'configuracion': d['configuracion'],
            'predictores': d['predictores'], 'umbral': d['umbral'],
            'decision_json_canonico_sha256': m.json_hash(d), 'modelo_sha256': m.sha256(output),
            'corte_entrenamiento': 'A', 'fecha_corte': '2026-07-01', 'filas': len(data),
            'positivos': int(data['etiqueta'].sum()), 'entrada_21_sha256': e['entrada_sha256'],
            'origen': data.attrs['origen'], 'versiones': m.versions(), 'python': sys.version.split()[0],
            'creado_en_utc': datetime.now(timezone.utc).isoformat(),
            'codigo_commit': subprocess.check_output(['git', 'rev-parse', 'HEAD'], cwd=ROOT).decode().strip(),
            'segundos_carga_y_features_a': loaded - started, 'segundos_fit': fitted - loaded,
            'segundos_total': time.perf_counter() - started, 'b_evaluado': False}
    m.write_json(metadata, meta)
    m.load_model(output, metadata)
    print(f"Modelo {m.VERSION}: {len(data)} filas A; SHA256 {meta['modelo_sha256']}")
    return meta

def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--salida', type=Path, default=m.MODEL)
    args = parser.parse_args(argv)
    try:
        train(args.salida)
    except (ValueError, OSError) as exc:
        parser.exit(1, f'Error al serializar: {exc}\n')

if __name__ == '__main__':
    main()
