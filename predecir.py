"""Inferencia C: carga un Pipeline guardado; los datos provienen de --datos."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timezone
from pathlib import Path
import sys
import time
from threadpoolctl import threadpool_limits
from scripts import p2_24 as m
from scripts import datos_p2_24 as inputs

def predict(folder, cut, output, model_path=m.MODEL):
    cut = inputs.cutoff(cut)
    output = Path(output)
    sidecar = output.with_suffix('.json')
    if sidecar.exists() and not output.exists():
        raise FileExistsError('Hay evidencia sin CSV: usar --salida con una ruta nueva')
    if output.exists():
        with output.open(encoding='utf-8',newline='') as f:
            if next(csv.reader(f),None) != m.OUTPUT_COLUMNS:
                raise FileExistsError('La salida existente es ajena al contrato; se conserva')
    started = time.perf_counter()
    model, decision, meta = m.load_model(model_path, Path(model_path).with_suffix('.json'))
    data, timings = inputs.calculate(folder, cut)
    computed = time.perf_counter()
    with threadpool_limits(limits=1):
        result = m.predict_frame(model, data, decision['umbral'])
    predicted = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    serialized=result.to_csv(index=False,lineterminator='\n',float_format='%.17g').encode('utf-8')
    if output.exists():
        if output.read_bytes() != serialized:
            raise FileExistsError('La predicción difiere del CSV existente; se conserva. Usar otra --salida')
    else:
        with output.open('xb') as f:
            f.write(serialized)
    evidence = {'fecha_utc':datetime.now(timezone.utc).isoformat(), 'fecha_corte':cut,
                'modelo_version':m.VERSION, 'modelo_sha256':meta['modelo_sha256'],
                'decision_json_canonico_sha256':m.json_hash(decision), 'umbral':decision['umbral'],
                'filas':len(result),'contactar':int(result.contactar.sum()),'duplicados':0,
                'puntaje_min':float(result.puntaje.min()),'puntaje_max':float(result.puntaje.max()),
                'csv_sha256':m.sha256(output),'columnas':m.OUTPUT_COLUMNS,
                'versiones':meta['versiones'],
                'codigo_fuentes_sha256':{name:m.sha256(m.ROOT/name) for name in
                    ('predecir.py','scripts/p2_24.py','scripts/datos_p2_24.py')},
                'identidades_sha256':m.frame_hash(data[['unidad_id','tarjetas']]),
                **timings,'segundos_hasta_features':computed-started,
                'segundos_predict_proba':predicted-computed,'segundos_total':time.perf_counter()-started,
                'reentrenado':False,'etiquetas_futuras_consultadas':False}
    if sidecar.exists():
        import json
        if json.loads(sidecar.read_text(encoding='utf-8'))['csv_sha256'] != evidence['csv_sha256']:
            raise ValueError('Evidencia previa no coincide con el CSV; se conserva')
    else:
        m.write_json(sidecar,evidence)
    print(f"{len(result)} predicciones; contactar={evidence['contactar']}; SHA256={evidence['csv_sha256']}")
    return evidence

def main(argv=None):
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--datos',type=Path,required=True)
    parser.add_argument('--fecha-corte',required=True)
    parser.add_argument('--salida','--output',type=Path,default=m.ROOT/'datos_red/p2-24-predicciones-c.csv')
    parser.add_argument('--modelo',type=Path,default=m.MODEL)
    args=parser.parse_args(argv)
    try:
        predict(args.datos,args.fecha_corte,args.salida,args.modelo)
    except Exception as exc:
        print(f'Error de inferencia ({type(exc).__name__}): {exc}',file=sys.stderr)
        return 1
    return 0

if __name__=='__main__':
    raise SystemExit(main())
