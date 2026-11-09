"""Contratos de 2.4. Importar no entrena ni consulta datos."""
from __future__ import annotations
import hashlib
import importlib.metadata
import json
from pathlib import Path
import sys
import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import entrenar_p2_21_ensemble as training

VERSION = 'v1_rf_somero'
MODEL = ROOT / 'models/modelo_abandono_rf_somero_v1.joblib'
MODEL_META = MODEL.with_suffix('.json')
DECISION = ROOT / 'docs/evidencias/p2-22-decision.json'
EVIDENCE = ROOT / 'docs/evidencias/p2-21-ensemble.json'
OUTPUT_COLUMNS = ['unidad_id', 'tarjetas', 'puntaje', 'contactar']
LIBRARIES = ('numpy', 'pandas', 'scipy', 'scikit-learn', 'joblib', 'threadpoolctl',
             'psycopg', 'psycopg-binary', 'python-dotenv', 'Jinja2', 'MarkupSafe',
             'python-dateutil', 'six', 'pytz', 'tzdata')

def sha256(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()

def json_hash(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, ensure_ascii=False,
                                    separators=(',', ':'), allow_nan=False).encode()).hexdigest()

def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, indent=2, ensure_ascii=False, allow_nan=False)
        f.write('\n')

def versions():
    return {name: importlib.metadata.version(name) for name in LIBRARIES}

def official():
    d = json.loads(DECISION.read_text(encoding='utf-8'))
    e = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    if (d['modelo'] != 'rf_somero' or d['modelo'] != e['recomendado']['modelo']
            or d['configuracion'] != e['recomendado']['configuracion']
            or d['predictores'] != e['predictores'] or d['predictores'] != list(training.PREDICTORS)
            or d['umbral'] != 0.311210473799652):
        raise ValueError('Modelo, configuración, predictores o umbral difieren de la decisión oficial')
    return d, e

def load_model(path=MODEL, metadata_path=MODEL_META):
    d, _ = official()
    path, metadata_path = Path(path), Path(metadata_path)
    meta = json.loads(metadata_path.read_text(encoding='utf-8'))
    if (meta['modelo_version'] != VERSION or meta['modelo_sha256'] != sha256(path)
            or meta['decision_json_canonico_sha256'] != json_hash(d)
            or meta['predictores'] != d['predictores'] or meta['configuracion'] != d['configuracion']):
        raise ValueError('Modelo serializado o metadata no coinciden con la decisión')
    for name, version in meta['versiones'].items():
        if importlib.metadata.version(name) != version:
            raise ValueError(f'Versión incompatible de {name}; instalar requirements-inferencia.txt')
    # Sólo cargar el joblib confiable del repositorio y verificar antes su hash.
    model = joblib.load(path)
    clf = model.named_steps['clf']
    if not isinstance(clf, RandomForestClassifier):
        raise ValueError('El artefacto no contiene Random Forest')
    if any(clf.get_params()[k] != v for k, v in d['configuracion']['parametros'].items()):
        raise ValueError('Hiperparámetros serializados incorrectos')
    if list(model.feature_names_in_) != d['predictores'] or not np.array_equal(model.classes_, [0, 1]):
        raise ValueError('Esquema o clases del modelo incorrectos')
    prep = model.named_steps['prep']
    if ([c for _, _, group in prep.transformers for c in group] != d['predictores']
            or prep.transformers[0][1] != 'passthrough'
            or prep.named_transformers_['cat'].handle_unknown != 'ignore'):
        raise ValueError('Preprocesamiento serializado incorrecto')
    return model, d, meta

def validate_features(rows):
    data = pd.DataFrame(rows, columns=['unidad_id', 'tarjetas', *training.PREDICTORS])
    if data.empty or data.isna().any().any():
        raise ValueError('Población vacía o features/llaves nulas')
    if data['unidad_id'].duplicated().any():
        raise ValueError('Unidades duplicadas')
    for col in ('unidad_id', 'tarjetas', 'operador'):
        if data[col].astype(str).str.strip().eq('').any():
            raise ValueError(f'{col} contiene vacíos')
    for row in data[['unidad_id', 'tarjetas', 'operador']].itertuples(index=False):
        expected = hashlib.md5((row.operador + ':' + row.tarjetas).encode()).hexdigest()
        if row.unidad_id != expected:
            raise ValueError('unidad_id no corresponde al namespace operador:llave de Silver')
    for col in training.FEATURES:
        data[col] = pd.to_numeric(data[col], errors='raise').astype(float)
    if not np.isfinite(data[list(training.FEATURES)].to_numpy()).all():
        raise ValueError('Features numéricas no finitas')
    return data.sort_values('unidad_id', kind='stable').reset_index(drop=True)

def frame_hash(data):
    return hashlib.sha256(data.to_csv(index=False, lineterminator='\n', float_format='%.17g').encode()).hexdigest()

def predict_frame(model, data, threshold):
    p = model.predict_proba(data[list(training.PREDICTORS)])[:, 1]
    if p.shape != (len(data),) or not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Probabilidades inválidas')
    output = data[['unidad_id', 'tarjetas']].copy()
    output['puntaje'] = p
    output['contactar'] = (p >= threshold).astype(int)
    return output.loc[:, OUTPUT_COLUMNS]
