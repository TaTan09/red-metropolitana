"""Copia aislada, 30 días futuros añadidos y comparación exacta de inferencia C."""
from __future__ import annotations
import argparse
import csv
from datetime import datetime, timedelta
import hashlib
import json
from pathlib import Path
import shutil
import subprocess
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import datos_p2_24 as inputs, p2_24 as m
import pandas as pd

def extend(source, target, cut):
    source, manifest = inputs.read_manifest(source, cut)
    target = Path(target)
    if target.exists():
        raise FileExistsError('El escenario aislado ya existe')
    shutil.copytree(source, target)
    changes = {}
    cutoff = datetime.fromisoformat(cut)
    # Cada CSV conserva exactamente su prefijo original. Sólo se anexan registros.
    for name in inputs.SCHEMAS:
        p = target / f'{name}.csv'
        before_size = p.stat().st_size
        with p.open(encoding='utf-8', newline='') as f:
            reader = csv.DictReader(f)
            sample = []
            for row in reader:
                if len(sample) == 100:
                    break
                sample.append(row)
        additional = []
        if name == 'silver_cuarentena':
            additional = [{'fuente':'Transmetro', 'id_registro_crudo':f'futuro-cuarentena-{day}'} for day in range(30)]
        elif name == 'silver_padron_transmetro_scd2':
            keys = [r['tarjeta_id'] for r in sample if r['tarjeta_id']]
            for day in range(30):
                for key in keys:
                    additional.append({'tarjeta_id':key,'operacion':'DELETE',
                                       'valid_from':(cutoff+timedelta(days=day,hours=12)).isoformat(' ')})
        else:
            for day in range(30):
                for i, original in enumerate(sample):
                    row = dict(original)
                    row['bronze_record_id'] = f'p2-24-futuro-{day}-{i}'
                    instant = cutoff + timedelta(days=day, hours=12)
                    if name == 'silver_metroriel_viajes':
                        row['fecha_hora_ingreso'] = instant.isoformat(' ')
                        row['fecha_hora_salida'] = (instant+timedelta(minutes=20)).isoformat(' ')
                    else:
                        row['fecha_hora'] = instant.isoformat(' ')
                    additional.append(row)
            if name == 'silver_metroriel_viajes' and sample:
                row = dict(sample[0])
                row.update(bronze_record_id='p2-24-mr-cierre-futuro',
                           fecha_hora_ingreso=(cutoff-timedelta(minutes=1)).isoformat(' '),
                           fecha_hora_salida=(cutoff+timedelta(minutes=1)).isoformat(' '))
                additional.append(row)
        with p.open('a', encoding='utf-8', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=[c for c, _ in inputs.SCHEMAS[name]], lineterminator='\n')
            writer.writerows(additional)
        h = hashlib.sha256()
        with p.open('rb') as f:
            remaining = before_size
            while remaining:
                chunk = f.read(min(1024*1024,remaining))
                h.update(chunk)
                remaining -= len(chunk)
        if h.hexdigest() != manifest['fuentes'][name]['sha256']:
            raise ValueError('Se alteró el prefijo de registros originales')
        changes[name] = {'filas_originales':manifest['fuentes'][name]['filas'], 'filas_agregadas':len(additional),
                         'prefijo_original_sha256':h.hexdigest(), 'bytes_originales':before_size,
                         'sha256_ampliado':m.sha256(p)}
        manifest['fuentes'][name].update(filas=manifest['fuentes'][name]['filas']+len(additional), sha256=m.sha256(p))
    if any(changes[n]['filas_agregadas']==0 for n in inputs.SCHEMAS if n != 'silver_cuarentena'):
        raise ValueError('Prueba vacía: faltan fuentes de eventos/CDC')
    manifest['escenario'] = '30 días posteriores sintéticos + viaje MR con cierre posterior; sólo anexos'
    manifest['intervalo_adicional'] = [cut, (cutoff+timedelta(days=30)).date().isoformat()]
    # Se reemplaza únicamente el manifest de la copia creada por esta ejecución.
    (target/'manifest.json').write_text(json.dumps(manifest,indent=2,ensure_ascii=False)+'\n',encoding='utf-8')
    return changes

def compare(left, right):
    frames = [pd.read_csv(p,dtype={'unidad_id':str,'tarjetas':str},float_precision='round_trip') for p in (left,right)]
    for frame in frames:
        if list(frame.columns)!=m.OUTPUT_COLUMNS or frame.empty or frame.unidad_id.duplicated().any() or frame.isna().any().any():
            raise ValueError('CSV inválido para comparación')
    a,b = [f.sort_values('unidad_id').reset_index(drop=True) for f in frames]
    missing = len(set(a.unidad_id)^set(b.unidad_id))
    common = a.merge(b,on='unidad_id',suffixes=('_a','_b'),validate='one_to_one')
    differences = {col:int((common[col+'_a']!=common[col+'_b']).sum()) for col in m.OUTPUT_COLUMNS[1:]}
    if missing or any(differences.values()) or len(a)!=len(b):
        raise ValueError(f'Fuga temporal: unidades diferentes={missing}; columnas={differences}')
    return {'filas_originales':len(a),'filas_ampliadas':len(b),'unidades_diferentes':missing,
            'diferencias_por_columna':{'unidad_id':missing,**differences},'diferencias':0,
            'sha256_original':m.sha256(left),'sha256_ampliado':m.sha256(right),
            'csv_identicos_byte_a_byte':m.sha256(left)==m.sha256(right)}

def run(folder, baseline, workspace, evidence):
    cut = '2026-08-30'
    workspace, evidence, baseline = Path(workspace), Path(evidence), Path(baseline)
    if workspace.exists() or evidence.exists():
        raise FileExistsError('Ya hay evidencia/escenario; usar rutas nuevas')
    baseline_meta=json.loads(baseline.with_suffix('.json').read_text(encoding='utf-8'))
    source, _ = inputs.read_manifest(folder,cut)
    if m.sha256(source/'manifest.json')!=baseline_meta['entrada_manifest_sha256']:
        raise ValueError('La base de comparación no proviene de esta entrada')
    started=time.perf_counter()
    workspace.mkdir(parents=True)
    changes=extend(source,workspace/'entrada-mas-30-dias',cut)
    output=workspace/'predicciones-c-mas-30-dias.csv'
    command=[sys.executable,str(ROOT/'predecir.py'),'--datos',str(workspace/'entrada-mas-30-dias'),
             '--fecha-corte',cut,'--salida',str(output)]
    subprocess.run(command,cwd=ROOT,check=True)
    comparison=compare(baseline,output)
    augmented=json.loads(output.with_suffix('.json').read_text(encoding='utf-8'))
    if baseline_meta['features_sha256'] != augmented['features_sha256']:
        raise ValueError('Las features cambiaron aunque las predicciones coincidieran')
    result={'fecha_utc':datetime.now().astimezone().isoformat(),'fecha_corte':cut,
            'tipo':'Eventos de prueba sintéticos posteriores añadidos a una copia de Silver P2 real',
            'intervalo':'[2026-08-30,2026-09-29)', 'dias_adicionales':30,'fuentes':changes,
            'datos_originales_preservados':True,'recalculo':'Población y features SQL originales 1.2/1.3 en tablas TEMP desde CSV ampliados',
            'ambito':'Desde Silver operacional/CDC/cuarentena hasta CSV; no certifica ingestión Raw/Bronze de archivos nuevos',
            'modelo_sha256':baseline_meta['modelo_sha256'],'umbral':baseline_meta['umbral'],
            'features_sha256_original':baseline_meta['features_sha256'],
            'features_sha256_ampliado':augmented['features_sha256'],
            'prediccion_original':baseline_meta,'prediccion_ampliada':augmented,
            **comparison,'segundos_auditoria':time.perf_counter()-started,'b_evaluado':False}
    m.write_json(evidence,result)
    print(json.dumps(comparison,indent=2))
    return result

def main(argv=None):
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('--datos',type=Path,required=True)
    p.add_argument('--original',type=Path,required=True)
    p.add_argument('--trabajo',type=Path,required=True)
    p.add_argument('--evidencia',type=Path,required=True)
    a=p.parse_args(argv)
    run(a.datos,a.original,a.trabajo,a.evidencia)

if __name__=='__main__':
    main()
