"""Inferencia C: carga un Pipeline guardado; los datos provienen de --datos."""
from __future__ import annotations
import argparse
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
    if output.exists() or sidecar.exists():
        raise FileExistsError('La salida ya existe: usar --salida con una ruta nueva')
    started = time.perf_counter()
    model, decision, meta = m.load_model(model_path, Path(model_path).with_suffix('.json'))
    data, timings = inputs.calculate(folder, cut)
    computed = time.perf_counter()
    with threadpool_limits(limits=1):
        result = m.predict_frame(model, data, decision['umbral'])
    predicted = time.perf_counter()
    output.parent.mkdir(parents=True, exist_ok=True)
    result.to_csv(output, mode='x', index=False, lineterminator='\n', float_format='%.17g')
    evidence = {'fecha_utc':datetime.now(timezone.utc).isoformat(), 'fecha_corte':cut,
                'modelo_version':m.VERSION, 'modelo_sha256':meta['modelo_sha256'],
                'decision_json_canonico_sha256':m.json_hash(decision), 'umbral':decision['umbral'],
                'filas':len(result),'contactar':int(result.contactar.sum()),'duplicados':0,
                'puntaje_min':float(result.puntaje.min()),'puntaje_max':float(result.puntaje.max()),
                'csv_sha256':m.sha256(output),'columnas':m.OUTPUT_COLUMNS,
                'identidades_sha256':m.frame_hash(data[['unidad_id','tarjetas']]),
                **timings,'segundos_hasta_features':computed-started,
                'segundos_predict_proba':predicted-computed,'segundos_total':time.perf_counter()-started,
                'reentrenado':False,'etiquetas_futuras_consultadas':False}
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
