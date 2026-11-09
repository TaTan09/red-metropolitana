#!/usr/bin/env python3
"""2.2: seleccionar con OOF A; test B explícito, registrado y de una sola ejecución."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
from datetime import datetime, timezone, timedelta

import numpy as np
import pandas as pd
from sklearn.metrics import roc_auc_score
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts import entrenar_p2_21_ensemble as training

EVIDENCE = ROOT / 'docs/evidencias/p2-21-ensemble.json'
DECISION = ROOT / 'docs/evidencias/p2-22-decision.json'
RESULT = ROOT / 'docs/evidencias/p2-22-test-b.json'
JOURNAL = ROOT / 'docs/evidencias/p2-22-test-b-bitacora.jsonl'
METRICS = ROOT / 'docs/metricas/p2-22'
OOF = ROOT / 'datos_red/p2-21-oof-a.csv'
EXPECTED_OOF = '52427568e65f76ccfbab0e5d27cd9e905467759ce421e48f009deffe0b7dc8a0'
COSTS = {'contacto_gtq': 5, 'retencion_probabilidad': 0.25, 'valor_retenido_gtq': 60,
         'beneficio_esperado_tp_gtq': 15}
MODEL_PATH = ROOT / 'datos_red/p2-22-modelo-a.joblib'
PREDICTIONS = ROOT / 'datos_red/p2-22-predicciones-b.csv'


def now():
    return datetime.now(timezone(timedelta(hours=-6))).isoformat(timespec='microseconds')


def digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def git(*args):
    return subprocess.check_output(['git', *args], cwd=ROOT).decode('utf-8').strip()


def versions():
    return {'python': sys.version.split()[0], **{name: importlib.metadata.version(name)
            for name in ('scikit-learn', 'numpy', 'pandas', 'scipy', 'threadpoolctl', 'joblib')}}


def write_json(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open('x', encoding='utf-8', newline='\n') as f:
        json.dump(value, f, ensure_ascii=False, indent=2, allow_nan=False)
        f.write('\n')
        f.flush()
        os.fsync(f.fileno())


def evidence():
    e = json.loads(EVIDENCE.read_text(encoding='utf-8'))
    if e['recomendado']['modelo'] != 'rf_somero' or e['oof_sha256'] != EXPECTED_OOF:
        raise ValueError('La recomendación o la fuente OOF de 2.1 cambió')
    if e['predictores'] != list(training.PREDICTORS):
        raise ValueError('Cambió el orden de predictores')
    model = training.build_model(e['recomendado']['configuracion'])
    columns = [c for _, _, group in model.named_steps['prep'].transformers for c in group]
    if columns != e['predictores']:
        raise ValueError('Preprocesamiento incompatible')
    return e


def validate_oof(frame, e):
    """Contrato completo; reconstruye folds estratificados sin entrenar modelos."""
    if list(frame.columns) != list(training.OOF_COLUMNS) or frame.empty:
        raise ValueError('Esquema OOF incorrecto')
    d = frame.copy()
    if d.isna().any().any() or d['unidad_id'].astype(str).str.strip().eq('').any():
        raise ValueError('OOF nulo o identificador vacío')
    if d['unidad_id'].duplicated().any() or len(d) != e['filas']:
        raise ValueError('Una predicción por tarjeta; población incorrecta')
    if not d['corte'].eq('A').all() or not pd.to_datetime(d['fecha_corte']).eq(training.CUT_DATE).all():
        raise ValueError('Sólo OOF del corte A')
    if not d['etiqueta'].isin([0, 1]).all() or int(d['etiqueta'].sum()) != e['positivos']:
        raise ValueError('Etiquetas o positivos inconsistentes')
    p = d['probabilidad_abandono'].to_numpy(dtype=float)
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Probabilidades inválidas')
    if not d['modelo'].eq(e['recomendado']['modelo']).all():
        raise ValueError('Modelo OOF incorrecto')
    for config in d['configuracion_modelo'].unique():
        if json.loads(config) != e['recomendado']['configuracion']:
            raise ValueError('Configuración OOF incorrecta')
    d = d.sort_values('unidad_id', kind='stable').reset_index(drop=True)
    folds = training.fold_assignment(training.make_folds(d['etiqueta'].to_numpy(dtype=int)), len(d))
    if not np.array_equal(d['fold'].to_numpy(), folds):
        raise ValueError('Folds distintos a 2.1')
    fold_hash = training.sha256(d[['unidad_id', 'fold']].to_csv(index=False, lineterminator='\n'))
    if fold_hash != e['folds_sha256']:
        raise ValueError('Huella de folds incorrecta')
    for f in e['folds']:
        rows = d[d['fold'].eq(f['fold'])]
        if len(rows) != f['validacion'] or int(rows['etiqueta'].sum()) != f['positivos_validacion']:
            raise ValueError('Distribución OOF por fold incorrecta')
    return d


def load_oof(e):
    if digest(OOF) != EXPECTED_OOF:
        raise ValueError('SHA-256 OOF no coincide; no se permite continuar')
    # round_trip conserva exactamente el float64 exportado con %.17g en 2.1.
    d = validate_oof(pd.read_csv(OOF, dtype={'unidad_id': str}, float_precision='round_trip'), e)
    if float(roc_auc_score(d['etiqueta'], d['probabilidad_abandono'])) != e['auc_oof_recomendado']:
        raise ValueError('AUC OOF distinto del publicado en 2.1')
    return d


def validate_scores(y, p):
    y, p = np.asarray(y), np.asarray(p, dtype=float)
    if y.ndim != 1 or y.shape != p.shape or not len(y) or not np.isin(y, [0, 1]).all():
        raise ValueError('Etiquetas binarias, vectores alineados no vacíos')
    if not np.isfinite(p).all() or ((p < 0) | (p > 1)).any():
        raise ValueError('Probabilidades finitas en [0,1]')
    return y.astype(int), p


def counts_metrics(tp, fp, positives, negatives):
    tp, fp, positives, negatives = map(int, (tp, fp, positives, negatives))
    n = tp + fp
    return {'contactadas': n, 'tp': tp, 'fp': fp, 'tn': negatives - fp, 'fn': positives - tp,
            'precision': tp / n if n else 0.0,
            'recall': tp / positives if positives else 0.0,
            'ganancia_gtq': 15 * tp - 5 * n}


def at_threshold(y, p, threshold):
    y, p = validate_scores(y, p)
    if not np.isfinite(threshold) or not 0 <= threshold <= np.nextafter(1.0, np.inf):
        raise ValueError('Umbral inválido')
    contact = p >= threshold
    tp = int(y[contact].sum())
    return counts_metrics(tp, int(contact.sum()) - tp, y.sum(), len(y) - y.sum())


def threshold_table(y, p):
    """Todos los conjuntos alcanzables por p>=t; O(n log n), empates indivisibles."""
    y, p = validate_scores(y, p)
    order = np.argsort(-p, kind='stable')
    scores, labels = p[order], y[order]
    ends = np.r_[np.flatnonzero(scores[:-1] != scores[1:]), len(scores) - 1]
    tp = np.cumsum(labels)
    positives = int(y.sum())
    rows = []
    thresholds = np.unique(np.r_[scores[ends], 0.0, 1 / 3, 1.0, np.nextafter(1.0, np.inf)])
    # searchsorted consulta acumulados en el orden descendente sin recorrer n por umbral.
    for t in thresholds:
        n = int(np.searchsorted(-scores, -t, side='right'))
        hits = int(tp[n - 1]) if n else 0
        rows.append({'umbral': float(t), **counts_metrics(hits, n - hits, positives, len(y) - positives)})
    return pd.DataFrame(rows)


def select_threshold(table):
    # Misma ganancia: menor cantidad de contactos; luego mayor umbral.
    return table.sort_values(['ganancia_gtq', 'contactadas', 'umbral'],
                             ascending=[False, True, False], kind='stable').iloc[0].to_dict()


def plot_gain(table, selected, path):
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'datos_red/.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(9, 5), layout='constrained')
    ax.plot(table['umbral'], table['ganancia_gtq'], label='Ganancia OOF A', linewidth=1.4)
    ax.axhline(0, color='gray', linewidth=0.8, label='No contactar: Q0')
    ax.axvline(1 / 3, color='#9b59b6', linestyle='--', label='Teórico: 1/3')
    ax.scatter([selected['umbral']], [selected['ganancia_gtq']], color='#c0392b', zorder=4,
               label=f"Elegido: {selected['umbral']:.6f}; Q{selected['ganancia_gtq']:,.0f}")
    ax.set(xlabel='Umbral (contactar si p ≥ umbral)', ylabel='Ganancia esperada (Q)',
           title='Selección de decisión con predicciones OOF del corte A', xlim=(0, 1))
    ax.legend(fontsize=9)
    ax.grid(alpha=0.2)
    fig.savefig(path, dpi=160)
    plt.close(fig)


def select_a():
    if git('branch', '--show-current') != 'p2/hector-22' or git('status', '--porcelain'):
        raise RuntimeError('Seleccionar con código comprometido y árbol limpio en p2/hector-22')
    if any(p.exists() for p in (DECISION, JOURNAL, RESULT, METRICS)):
        raise FileExistsError('La decisión/evidencia ya existe; no sobrescribir')
    e = evidence()
    d = load_oof(e)
    y, p = d['etiqueta'].to_numpy(), d['probabilidad_abandono'].to_numpy()
    table = threshold_table(y, p)
    selected = select_threshold(table)
    # Tipos enteros explícitos para la interfaz JSON.
    for key in ('contactadas', 'tp', 'fp', 'tn', 'fn', 'ganancia_gtq'):
        selected[key] = int(selected[key])
    decision = {'requisito': '2.2', 'seleccion_en': now(), 'codigo_commit': git('rev-parse', 'HEAD'),
                'modelo': e['recomendado']['modelo'], 'configuracion': e['recomendado']['configuracion'],
                'predictores': e['predictores'], 'preprocesamiento': 'build_model de scripts/entrenar_p2_21_ensemble.py',
                'evidencia_21_sha256': digest(EVIDENCE), 'oof_sha256': digest(OOF),
                'costos': COSTS, 'umbral_teorico': 1 / 3, 'umbral': selected['umbral'],
                'regla_contacto': 'probabilidad_abandono >= umbral',
                'busqueda': 'Todos los scores OOF únicos, 0, 1, 1/3 y nextafter(1,+inf) para no contactar',
                'desempate': 'Máxima ganancia; menos contactos; mayor umbral',
                'justificacion': 'Máximo empírico de ganancia OOF en A; no supone calibración perfecta. B no consultado.',
                'candidatos': len(table), 'a': {'filas': len(d), 'positivos': int(y.sum()),
                'seleccionado': selected, 'teorico': at_threshold(y, p, 1 / 3),
                'nadie': at_threshold(y, p, np.nextafter(1.0, np.inf)),
                'todos': at_threshold(y, p, 0), 'roc_auc_oof': float(roc_auc_score(y, p)),
                'roc_auc_media_folds_21': e['modelos'][e['recomendado']['modelo']]['auc_validacion']['media']},
                'versiones': versions(), 'b_consultado': False}
    METRICS.mkdir(parents=True)
    csv_path = METRICS / 'umbrales-a.csv'
    table.to_csv(csv_path, index=False, lineterminator='\n', float_format='%.17g')
    plot_gain(table, selected, METRICS / 'ganancia-a.png')
    decision['tabla_umbrales_sha256'] = digest(csv_path)
    write_json(DECISION, decision)
    print(json.dumps(decision, indent=2, ensure_ascii=False))


def verify_freeze(freeze):
    if git('branch', '--show-current') != 'p2/hector-22' or git('status', '--porcelain'):
        raise RuntimeError('Test B exige rama p2/hector-22 y árbol limpio')
    freeze = git('rev-parse', f'{freeze}^{{commit}}')
    subprocess.run(['git', 'merge-base', '--is-ancestor', freeze, 'HEAD'], cwd=ROOT, check=True)
    rel = DECISION.relative_to(ROOT).as_posix()
    committed = subprocess.check_output(['git', 'show', f'{freeze}:{rel}'], cwd=ROOT)
    if committed != DECISION.read_bytes():
        raise ValueError('Decisión distinta a la congelada')
    d = json.loads(committed)
    if d['b_consultado'] is not False or digest(EVIDENCE) != d['evidencia_21_sha256']:
        raise ValueError('Evidencia de selección inconsistente')
    if d['configuracion'] != evidence()['recomendado']['configuracion'] or d['predictores'] != list(training.PREDICTORS):
        raise ValueError('Configuración/predictores cambiaron')
    if versions() != d['versiones']:
        raise ValueError('Entorno diferente al de selección; revisar antes de abrir B')
    # Todo el código, SQL y dependencias deben ser los que se revisaron al seleccionar A.
    changes = git('diff', '--name-only', d['codigo_commit'], 'HEAD', '--', 'scripts', 'dbt',
                  'requirements.txt', 'requirements-ml.txt', 'tests')
    if changes:
        raise ValueError('Código cambió después de seleccionar A: ' + changes)
    validate_decision(d, evidence(), load_oof(evidence()))
    if digest(METRICS / 'umbrales-a.csv') != d['tabla_umbrales_sha256']:
        raise ValueError('Tabla de umbrales modificada')
    return d, freeze


def validate_decision(d, e, oof):
    if d['modelo'] != e['recomendado']['modelo'] or d['costos'] != COSTS:
        raise ValueError('Modelo o costos de decisión inconsistentes')
    selected = select_threshold(threshold_table(oof['etiqueta'], oof['probabilidad_abandono']))
    if d['umbral'] != selected['umbral'] or d['a']['seleccionado'] != selected:
        raise ValueError('La decisión no corresponde al máximo OOF de A')


def append_event(file, stage, **details):
    file.write(json.dumps({'fecha': now(), 'etapa': stage, **details}, ensure_ascii=False) + '\n')
    file.flush()
    os.fsync(file.fileno())


def b_query():
    """Mismo SQL original 1.3, población restringida a B antes de agregar features."""
    return training.recalculated_query().replace("corte = 'A'", "corte = 'B'").replace(
        "timestamp '2026-07-01 00:00:00'", "timestamp '2026-07-31 00:00:00'")


def load_b():
    with training.connect() as conn:
        conn.execute('set transaction isolation level repeatable read, read only')
        rows = conn.execute(b_query()).fetchall()
    h = hashlib.sha256()
    for row in rows:
        h.update((json.dumps(row, sort_keys=True, default=str, ensure_ascii=False,
                             separators=(',', ':')) + '\n').encode('utf-8'))
    published = json.loads((ROOT / 'docs/metricas/p2-13-features.json').read_text(encoding='utf-8'))
    expected = next(c['sha256_filas_ordenadas'] for c in published['cortes'] if c['corte'] == 'B')
    if h.hexdigest() != expected:
        raise ValueError('B no coincide con la huella publicada en 1.3')
    d = pd.DataFrame(rows, columns=training.INPUT_COLUMNS)
    if d.empty or not d['corte'].eq('B').all() or not pd.to_datetime(d['fecha_corte']).eq(pd.Timestamp('2026-07-31')).all():
        raise ValueError('Corte B incorrecto')
    # Reutiliza validación de esquema, claves, etiquetas y predictores; sólo adapta metadatos.
    validated = training.prepare_cut_a(d.assign(corte='A', fecha_corte=training.CUT_DATE))
    validated['corte'], validated['fecha_corte'] = 'B', pd.Timestamp('2026-07-31')
    return validated, h.hexdigest()


def evaluate_once(freeze):
    """No se invoca al importar, seleccionar A ni ejecutar unittest discover."""
    if any(p.exists() for p in (JOURNAL, RESULT, MODEL_PATH, PREDICTIONS)):
        raise FileExistsError('Test B reservado o ejecutado. No se permite repetir; consultar bitácora.')
    decision, freeze = verify_freeze(freeze)
    code = git('rev-parse', 'HEAD')
    # Reserva exclusiva y durable ANTES de cualquier consulta. Un fallo también bloquea reintentos.
    with JOURNAL.open('x', encoding='utf-8', newline='\n') as journal:
        accessed = metrics_produced = False
        stage = 'reserva'
        append_event(journal, stage, codigo_commit=code, decision_commit=freeze,
                     decision_sha256=digest(DECISION), etiquetas_b_acceso=False, metricas_b=False,
                     comando=sys.argv)
        try:
            stage = 'entrenamiento_a'
            append_event(journal, stage)
            a = training.load_cut_a(recalculate=True)
            e = evidence()
            if training.sha256(a.to_csv(index=False, lineterminator='\n')) != e['entrada_sha256']:
                raise ValueError('Entrada A distinta de 2.1')
            oof = load_oof(e)
            if not a['unidad_id'].equals(oof['unidad_id']) or not np.array_equal(a['etiqueta'], oof['etiqueta']):
                raise ValueError('Claves/etiquetas A distintas al OOF')
            model = training.build_model(decision['configuracion'])
            with threadpool_limits(limits=1):
                model.fit(a[decision['predictores']], a['etiqueta'])
            import joblib
            joblib.dump(model, MODEL_PATH)
            append_event(journal, 'modelo_a_ajustado', filas=len(a), sha256_modelo=digest(MODEL_PATH))
            # Señal conservadora: desde este punto puede haber acceso incluso si SQL falla.
            stage, accessed = 'consulta_etiquetas_b', True
            append_event(journal, stage, etiquetas_b_acceso_posible=True, metricas_b=False,
                         sql_sha256=hashlib.sha256(b_query().encode()).hexdigest())
            b, source_hash = load_b()
            stage = 'prediccion_b'
            append_event(journal, stage, filas=len(b), etiquetas_b_acceso=True)
            with threadpool_limits(limits=1):
                p = model.predict_proba(b[decision['predictores']])[:, 1]
            y = b['etiqueta'].to_numpy()
            stage = 'metricas_b'
            metrics = at_threshold(y, p, decision['umbral'])
            metrics_produced = True
            append_event(journal, 'confusion_b_calculada', metricas_b=True, **metrics)
            auc = float(roc_auc_score(y, p))
            # La métrica queda durable antes de generar tablas/gráficas o escribir otros archivos.
            append_event(journal, 'metricas_b_completadas', metricas_b=True, roc_auc=auc, **metrics)
            predictions = b[list(training.IDENTIFIERS)].copy()
            predictions['probabilidad_abandono'] = p
            predictions['contactar'] = (p >= decision['umbral']).astype(int)
            predictions.to_csv(PREDICTIONS, index=False, mode='x', lineterminator='\n', float_format='%.17g')
            result = {'requisito': '2.2', 'evaluado_en': now(), 'codigo_commit': code,
                      'decision_commit': freeze, 'decision_sha256': digest(DECISION),
                      'modelo': decision['modelo'], 'configuracion': decision['configuracion'],
                      'umbral': decision['umbral'], 'costos': decision['costos'],
                      'versiones': versions(), 'corte': 'B', 'fecha_corte': '2026-07-31',
                      'filas': len(b), 'positivos': int(y.sum()), 'negativos': int(len(y) - y.sum()),
                      **metrics, 'roc_auc': auc,
                      'matriz_confusion_filas_real_columnas_contacto': [[metrics['tn'], metrics['fp']],
                                                                      [metrics['fn'], metrics['tp']]],
                      'a_oof': decision['a'], 'b_filas_sha256_formato_13': source_hash,
                      'modelo_a_sha256': digest(MODEL_PATH), 'predicciones_b_sha256': digest(PREDICTIONS),
                      'estado': 'completado', 'evaluaciones_b': 1}
            write_json(RESULT, result)
            append_event(journal, 'resultado_guardado', resultado_sha256=digest(RESULT), metricas_b=True)
            print(json.dumps(result, indent=2, ensure_ascii=False))
        except BaseException as exc:
            append_event(journal, 'error', etapa_fallida=stage, tipo=type(exc).__name__, detalle=str(exc),
                         etiquetas_b_acceso_posible=accessed, metricas_b_producidas=metrics_produced,
                         reintento_automatico=False)
            raise


def render_report():
    """Sólo lee resultados guardados: nunca conecta a SQL, entrena o predice."""
    d = json.loads(DECISION.read_text(encoding='utf-8'))
    r = json.loads(RESULT.read_text(encoding='utf-8'))
    if r['decision_sha256'] != digest(DECISION):
        raise ValueError('La decisión cambió tras evaluar B')
    report = METRICS / 'reporte.md'
    matrix_path = METRICS / 'matriz-confusion-b.png'
    if report.exists() or matrix_path.exists():
        raise FileExistsError('El reporte ya existe; conservar evidencia')
    lines = ['# 2.2 — Umbral según costo y test único', '',
             f"Modelo **{d['modelo']}**, recomendado en 2.1. Umbral congelado: **{d['umbral']:.17g}**; contactar si `p >= umbral`.", '',
             '## Decisión económica', '',
             'Retener un abandono contactado aporta en promedio 0.25 × Q60 = Q15. Cada contacto cuesta Q5, incluso si la tarjeta no abandonaba. Por eso:', '',
             '`G = 15 TP − 5 (TP + FP) = 10 TP − 5 FP`.', '',
             'Para una probabilidad real p, la ganancia esperada por contacto es `15p − 5`; es positiva cuando `p > 1/3`. En la igualdad la ganancia es cero. El umbral teórico sólo es óptimo si las probabilidades están calibradas y los supuestos económicos se cumplen.', '',
             'Se eligió el máximo empírico usando exclusivamente las predicciones fuera de muestra de A: todos los scores distintos, los extremos, 1/3 y una opción explícita de no contactar. Los empates de score no se separan. Desempate: menos contactos y luego mayor umbral. No hubo calibración adicional ni elección de modelo.', '',
             f"Se evaluaron {d['candidatos']:,} umbrales. Precisión y recall sin denominador se reportan como cero. El valor `nextafter(1,+inf)` representa no contactar incluso si existen scores iguales a 1.", '',
             '## Selección con OOF de A', '',
             '| Política | Contactos | TP | FP | TN | FN | Precisión | Recall | Ganancia Q |',
             '|---|---:|---:|---:|---:|---:|---:|---:|---:|']
    for name, x in [('Seleccionada', d['a']['seleccionado']), ('Teórica 1/3', d['a']['teorico']),
                    ('Nadie', d['a']['nadie']), ('Todos', d['a']['todos'])]:
        lines.append(f"| {name} | {x['contactadas']:,} | {x['tp']:,} | {x['fp']:,} | {x['tn']:,} | {x['fn']:,} | {x['precision']:.6f} | {x['recall']:.6f} | {x['ganancia_gtq']:,} |")
    lines.extend(['', '![Ganancia OOF A](ganancia-a.png)', '',
                  '[Todos los umbrales y métricas](umbrales-a.csv). Esta ganancia de A es una estimación seleccionada sobre los mismos OOF: puede ser optimista y no es una nueva estimación independiente.', '',
                  '## Test B realizado una sola vez', '',
                  f"Fecha exacta: `{r['evaluado_en']}`. Código: `{r['codigo_commit']}`. Commit de decisión previa: `{r['decision_commit']}`.", '',
                  f"B contiene {r['filas']:,} tarjetas: {r['positivos']:,} positivas y {r['negativos']:,} negativas. Contactos: {r['contactadas']:,}. Ganancia esperada: **Q{r['ganancia_gtq']:,}**.", '',
                  '| Real / Decisión | No contactar | Contactar |', '|---|---:|---:|',
                  f"| No abandona | TN = {r['tn']:,} | FP = {r['fp']:,} |",
                  f"| Abandona | FN = {r['fn']:,} | TP = {r['tp']:,} |", '',
                  '![Matriz de confusión B](matriz-confusion-b.png)', '',
                  '| Métrica | A OOF, umbral elegido | B, umbral congelado |', '|---|---:|---:|'])
    for key, name in [('precision', 'Precisión'), ('recall', 'Recall'), ('ganancia_gtq', 'Ganancia Q')]:
        lines.append(f"| {name} | {d['a']['seleccionado'][key]:.6f} | {r[key]:.6f} |")
    lines.extend([f"| ROC-AUC agrupado | {d['a']['roc_auc_oof']:.6f} | {r['roc_auc']:.6f} |", '',
                  f"En 2.1 el AUC medio de los cinco folds fue {d['a']['roc_auc_media_folds_21']:.6f}; el AUC OOF agrupado es otro resumen. B usa un único bosque ajustado con todo A; la comparación temporal y de tamaños es descriptiva. No se reajustó nada con B.", '',
                  'Precisión indica qué proporción de los contactos realmente abandonaba. Recall indica qué proporción de los abandonos se alcanzó. ROC-AUC mide el ordenamiento del riesgo a través de todos los umbrales; no mide calibración ni beneficio económico. TP/FP/TN/FN comparan la decisión de contactar con la etiqueta de abandono, no observan retención causal.', '',
                  'La ganancia es esperada bajo los supuestos Q5 / 25% / Q60, no dinero ni retenciones observadas. La unidad es tarjeta por operador, no una persona consolidada. A y B pueden compartir tarjetas: la separación es temporal, no por identidad. Se usaron las ventanas previas y disponibilidad de Silver de 1.3.', '',
                  '## Trazabilidad y reproducción segura', '',
                  'El JSON de decisión se comprometió antes de abrir B. Se verificaron hashes OOF, folds, configuración, orden de features y datos A. Se reutilizó `build_model` de 2.1: variables numéricas passthrough, operador OneHotEncoder con categorías desconocidas ignoradas; ajuste únicamente en A.', '',
                  'El comando `test-b` exige árbol limpio y decisión idéntica al commit previo; rechaza cambios de código, SQL, dependencias o pruebas tras seleccionar A. Una reserva exclusiva y durable se crea antes de consultar datos. La bitácora registra el acceso posible a etiquetas B antes de SQL y guarda las métricas antes de producir otros artefactos. Si falla, no reintenta automáticamente. La presencia de bitácora, resultado, modelo o predicciones impide otra ejecución.', '',
                  'La tabla de features se recalculó con el SQL original de 1.3 filtrando primero la población del corte. Las huellas de A y B coinciden con 1.3; la entrada de entrenamiento A coincide además con 2.1. No se reconstruyó todo el pipeline.', '',
                  'Ver [decisión](../../evidencias/p2-22-decision.json), [resultado único](../../evidencias/p2-22-test-b.json) y [bitácora](../../evidencias/p2-22-test-b-bitacora.jsonl). La comparación de resultados guardados y este reporte no repite predicciones ni consultas de B.', '',
                  '```powershell', '# Pruebas con fixtures; nunca ejecutan el test real B',
                  '.venv\\Scripts\\python.exe -m unittest discover -s tests',
                  '# Sólo si todavía NO existe una decisión: seleccionar-a (sin SQL)',
                  '.venv\\Scripts\\python.exe scripts/umbral_p2_22.py seleccionar-a',
                  '# El test oficial ya está completado: NO volver a ejecutar test-b.',
                  '# reporte sólo transforma JSON guardados; rechaza sobrescribir archivos.',
                  '```', '',
                  '## Entrega a Jonatán para 2.4', '',
                  'Consumir `docs/evidencias/p2-22-decision.json`: `configuracion`, `predictores`, `umbral` y la regla inclusiva `p >= umbral`. Construir con `scripts.entrenar_p2_21_ensemble.build_model(decision["configuracion"])`; ajustar con todo A, nunca B/C. No redondear el umbral del JSON ni usar el texto redondeado de las gráficas.', '',
                  'El Pipeline ya ajustado en A se conserva localmente en `datos_red/p2-22-modelo-a.joblib` (ignorado), con SHA-256 en el resultado B. Puede compartirse por un medio directo; cargar sólo un artefacto de origen confiable y verificar la huella y versiones. Para reproducir el reajuste usar `load_cut_a(recalculate=True)` y `predictores` en el mismo orden. Modelo RF de 100 árboles, semilla registrada y un hilo. Python/paquetes exactos usados figuran en los JSON.', '',
                  'El CSV OOF y las predicciones individuales B permanecen ignorados. Para C usar features de C sin etiquetas, el Pipeline ajustado con A y la misma decisión. La interfaz de salida de 2.4 y su auditoría temporal siguen siendo responsabilidad de esa entrega; aquí no se implementan.', ''])
    os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'datos_red/.matplotlib'))
    import matplotlib
    matplotlib.use('Agg')
    import matplotlib.pyplot as plt
    matrix = np.array(r['matriz_confusion_filas_real_columnas_contacto'])
    fig, ax = plt.subplots(figsize=(6, 5), layout='constrained')
    image = ax.imshow(matrix, cmap='Blues')
    for i in range(2):
        for j in range(2):
            ax.text(j, i, f"{matrix[i, j]:,}", ha='center', va='center', fontsize=15,
                    color='white' if matrix[i, j] > matrix.max() / 2 else 'black')
    ax.set(xticks=[0, 1], xticklabels=['No contactar', 'Contactar'], yticks=[0, 1],
           yticklabels=['No abandona', 'Abandona'], xlabel='Decisión', ylabel='Etiqueta real',
           title='Test único B · umbral congelado en A')
    fig.colorbar(image, ax=ax, label='Tarjetas')
    fig.savefig(matrix_path, dpi=160)
    plt.close(fig)
    with report.open('x', encoding='utf-8', newline='\n') as f:
        f.write('\n'.join(lines))
    print(report)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest='command', required=True)
    sub.add_parser('seleccionar-a', help='No consulta PostgreSQL ni B')
    sub.add_parser('reporte', help='Sólo renderiza JSON guardados; no evalúa B')
    test = sub.add_parser('test-b', help='Irrepetible: reserva durable antes de consultar datos')
    test.add_argument('--decision-commit', required=True)
    args = parser.parse_args(argv)
    if args.command == 'seleccionar-a':
        select_a()
    elif args.command == 'test-b':
        evaluate_once(args.decision_commit)
    else:
        render_report()


if __name__ == '__main__':
    main()
