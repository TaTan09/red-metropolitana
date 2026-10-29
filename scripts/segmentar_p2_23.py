#!/usr/bin/env python3
"""KMeans y PCA descriptivos, exclusivamente sobre features del corte A."""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
import os
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
os.environ.setdefault('MPLCONFIGDIR', str(ROOT / 'datos_red/.matplotlib'))
import matplotlib
matplotlib.use('Agg')
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.decomposition import PCA
from sklearn.metrics import silhouette_score
from sklearn.preprocessing import StandardScaler
from threadpoolctl import threadpool_limits

sys.path.insert(0, str(ROOT))
from scripts.auditar_fuga_p2_13 import FEATURES, connect  # noqa: E402

SEED = 2026


def load_a(conn):
    rows = conn.execute("select * from silver.silver_p2_features_tarjeta where corte='A' order by unidad_id,fecha_corte").fetchall()
    if not rows:
        raise ValueError('Corte A vacío')
    digest = hashlib.sha256()
    for row in rows:
        digest.update((json.dumps(row, sort_keys=True, default=str, ensure_ascii=False,
                                  separators=(',', ':')) + '\n').encode('utf-8'))
    frame = pd.DataFrame(rows)
    if frame['unidad_id'].duplicated().any() or frame['fecha_corte'].nunique() != 1:
        raise ValueError('A tiene claves duplicadas o más de una fecha')
    if not frame['etiqueta'].isin([0, 1]).all():
        raise ValueError('A requiere etiquetas 0/1 para la descripción posterior')
    return frame, digest.hexdigest()


def fit_segments(x, *, ks=range(2, 9), seed=SEED, sample_size=3000):
    """No recibe etiquetas ni datos B/C: no pueden participar en el ajuste."""
    x = np.asarray(x, dtype=float)
    if x.ndim != 2 or x.shape[0] < 4 or not np.isfinite(x).all():
        raise ValueError('Se requieren al menos cuatro filas numéricas finitas')
    unique = np.unique(x, axis=0).shape[0]
    candidates = sorted(set(int(k) for k in ks if 2 <= k < len(x) and k <= unique))
    if len(candidates) < 2 or sample_size < 3:
        raise ValueError('Se requieren al menos dos k válidos y muestra de silueta >=3')
    scaled = StandardScaler().fit_transform(x)
    sample = np.sort(np.random.default_rng(seed).choice(len(x), min(sample_size, len(x)), replace=False))
    curves, solutions = [], {}
    with threadpool_limits(limits=1):
        for k in candidates:
            model = KMeans(n_clusters=k, random_state=seed, n_init=20, max_iter=300, algorithm='lloyd')
            labels = model.fit_predict(scaled)
            sample_labels = labels[sample]
            if not 1 < len(np.unique(sample_labels)) < len(sample):
                raise ValueError(f'La muestra de silueta no representa al menos dos segmentos para k={k}')
            score = float(silhouette_score(scaled[sample], sample_labels))
            curves.append({'k': k, 'inercia': float(model.inertia_), 'silueta_muestra': score})
            solutions[k] = labels
        pca = PCA(n_components=2, svd_solver='full')
        coordinates = pca.fit_transform(scaled)
    # Regla previa al ajuste, independiente de etiqueta: máxima silueta; empate -> menor k.
    chosen = max(curves, key=lambda row: (row['silueta_muestra'], -row['k']))['k']
    inertia = np.array([row['inercia'] for row in curves])
    normal = (inertia - inertia[-1]) / max(inertia[0] - inertia[-1], np.finfo(float).eps)
    k_norm = (np.array(candidates) - candidates[0]) / (candidates[-1] - candidates[0])
    elbow = candidates[int(np.argmax((1 - k_norm) - normal))]
    return {'k': chosen, 'k_codo': elbow, 'curvas': curves,
            'etiquetas_cluster': solutions[chosen], 'pca': coordinates,
            'varianza_explicada': pca.explained_variance_ratio_.tolist(),
            'muestra_silueta': len(sample), 'semilla': seed}


def describe(frame, labels):
    data = frame.copy()
    data['segmento'] = labels
    global_usage = float(data['viajes_28d'].median())
    global_recency = float(data['dias_desde_ultimo_uso'].median())
    descriptions = []
    for group, rows in data.groupby('segmento', sort=True):
        medians = {col: float(rows[col].median()) for col in FEATURES}
        frequent = medians['viajes_28d'] >= global_usage
        recent = medians['dias_desde_ultimo_uso'] <= global_recency
        name = f"Uso {'frecuente' if frequent else 'ocasional'} y {'reciente' if recent else 'con pausa mayor'}"
        action = ('Beneficio por continuidad o abono de viajes, ofrecido en los puntos de origen habituales.'
                  if frequent else 'Recarga de retorno de monto limitado y recordatorio de volver a usar la tarjeta.')
        descriptions.append({'segmento': int(group), 'nombre': f'S{group}: {name}',
                             'tamano': len(rows), 'positivos': int(rows['etiqueta'].sum()),
                             'tasa_abandono': float(rows['etiqueta'].mean()),
                             'medianas': medians, 'accion_retencion': action})
    # Garantizar dos propuestas diferentes aun si ambos grupos quedan del mismo lado de la mediana.
    ranked = sorted(descriptions, key=lambda row: (row['medianas']['dias_desde_ultimo_uso'], row['segmento']))
    ranked[0]['accion_retencion'] = 'Beneficio por continuidad o abono de viajes en los puntos de origen habituales.'
    ranked[-1]['accion_retencion'] = 'Recarga de retorno de monto limitado y recordatorio tras una pausa de uso.'
    return descriptions


def plot_results(result, segments, output):
    curves = result['curvas']
    for key, title, ylabel, filename in (
        ('inercia', 'Método del codo — corte A escalado', 'Inercia (suma de distancias cuadradas)', 'codo.png'),
        ('silueta_muestra', f"Silueta — muestra fija de {result['muestra_silueta']:,} tarjetas A", 'Silueta media de la muestra', 'silueta.png')):
        fig, ax = plt.subplots(figsize=(8, 4.5))
        ax.plot([r['k'] for r in curves], [r[key] for r in curves], 'o-', color='#0072B2')
        ax.axvline(result['k'], color='#D55E00', linestyle='--', label=f"k elegido = {result['k']}")
        if key == 'inercia':
            ax.axvline(result['k_codo'], color='#555555', linestyle=':', label=f"codo geométrico = {result['k_codo']}")
        ax.set(title=title, xlabel='Número de segmentos (k)', ylabel=ylabel)
        ax.set_xticks([r['k'] for r in curves])
        ax.grid(alpha=.2)
        ax.legend()
        fig.tight_layout()
        fig.savefig(output / filename, dpi=170)
        plt.close(fig)
    fig, ax = plt.subplots(figsize=(10, 5.5))
    palette = ['#0072B2', '#D55E00', '#009E73', '#CC79A7', '#E69F00', '#56B4E9', '#555555', '#882255']
    for segment in segments:
        group = segment['segmento']
        points = result['pca'][result['etiquetas_cluster'] == group]
        ax.scatter(points[:, 0], points[:, 1], s=5, alpha=.3, linewidths=0,
                   color=palette[group % len(palette)], label=f"S{group} (n={len(points):,})")
    variance = result['varianza_explicada']
    ax.set(title='Segmentos de A — PCA de las mismas features escaladas',
           xlabel=f'PC1 ({variance[0]:.1%} de varianza)', ylabel=f'PC2 ({variance[1]:.1%} de varianza)')
    ax.grid(alpha=.15)
    ax.legend(markerscale=3, loc='upper right')
    fig.tight_layout()
    fig.savefig(output / 'pca.png', dpi=170)
    plt.close(fig)


def write_report(report, output):
    with (output / 'resultados.json').open('x', encoding='utf-8') as file:
        json.dump(report, file, ensure_ascii=False, indent=2)
        file.write('\n')
    with (output / 'segmentos.csv').open('x', newline='', encoding='utf-8') as file:
        columns = ['segmento', 'nombre', 'tamano', 'positivos', 'tasa_abandono', *FEATURES, 'accion_retencion']
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for row in report['segmentos']:
            writer.writerow({key: value for key, value in row.items() if key != 'medianas'} | row['medianas'])
    lines = ['# Segmentación KMeans y PCA — corte A', '',
             f"Filas: {report['filas']:,}. k elegido: {report['k']}; codo geométrico: {report['k_codo']}.", '',
             report['justificacion_k'], '',
             f"PCA: PC1={report['varianza_explicada'][0]:.2%}; PC2={report['varianza_explicada'][1]:.2%}; "
             f"total={sum(report['varianza_explicada']):.2%}.", '',
             '| Segmento | Nombre | Tamaño | Abandono A | Viajes 28d (mediana) | Recencia en días (mediana) | Gasto Q (mediana) |',
             '|---|---|---:|---|---:|---:|---:|']
    for row in report['segmentos']:
        m = row['medianas']
        lines.append(f"| S{row['segmento']} | {row['nombre']} | {row['tamano']} | {row['positivos']} / {row['tamano']} = {row['tasa_abandono']:.4%} | {m['viajes_28d']:.2f} | {m['dias_desde_ultimo_uso']:.2f} | {m['gasto_28d_gtq']:.2f} |")
    lines.extend(['', '## Acciones propuestas', ''])
    lines.extend(f"- **{row['nombre']}**: {row['accion_retencion']}" for row in report['segmentos'])
    lines.extend(['', 'Las tasas son descriptivas; no demuestran causalidad ni efecto de las acciones.',
                  'La etiqueta no participa en escalado, KMeans, PCA, selección de k ni nombres.',
                  'No se consultan B/C ni se incorpora el segmento al clasificador.', '',
                  '![Codo](codo.png)', '', '![Silueta](silueta.png)', '', '![PCA](pca.png)', ''])
    (output / 'resumen.md').write_text('\n'.join(lines), encoding='utf-8')


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output-dir', type=Path, required=True)
    parser.add_argument('--assignments', type=Path, default=ROOT / 'datos_red/p2-23-asignaciones.csv')
    args = parser.parse_args(argv)
    if args.output_dir.exists() or args.assignments.exists():
        raise FileExistsError('Use destinos nuevos para conservar los resultados anteriores')
    started = time.perf_counter()
    with connect() as conn:
        conn.execute('set transaction isolation level repeatable read, read only')
        frame, fingerprint = load_a(conn)
        conn.rollback()
    result = fit_segments(frame[list(FEATURES)].to_numpy(dtype=float))
    segments = describe(frame, result['etiquetas_cluster'])
    chosen = next(r for r in result['curvas'] if r['k'] == result['k'])
    justification = (f"Se evalúan k=2..8 sobre A escalado, con n_init=20 y semilla {SEED}. "
                     f"Se elige k={result['k']} por máxima silueta ({chosen['silueta_muestra']:.4f}) "
                     f"en una muestra uniforme fija de {result['muestra_silueta']} filas; empates favorecen menor k. "
                     f"El codo geométrico está en k={result['k_codo']}. "
                     + ('Ambos criterios coinciden.' if result['k'] == result['k_codo'] else
                        'Los criterios no coinciden: se prioriza la separación medida por silueta; el codo queda como alternativa, sin consultar etiquetas.'))
    report = {key: value for key, value in result.items() if key not in ('etiquetas_cluster', 'pca')}
    report.update(filas=len(frame), fecha_corte=str(frame['fecha_corte'].iloc[0]),
                  sha256_features_a=fingerprint, features=list(FEATURES),
                  escalado='StandardScaler ajustado exclusivamente en A',
                  seleccion='máxima silueta de muestra fija; empate a menor k',
                  justificacion_k=justification, segmentos=segments,
                  segundos=round(time.perf_counter() - started, 3),
                  versiones={name: importlib.metadata.version(name) for name in
                             ('numpy', 'pandas', 'scipy', 'scikit-learn', 'matplotlib', 'threadpoolctl')})
    args.output_dir.mkdir(parents=True)
    write_report(report, args.output_dir)
    plot_results(result, segments, args.output_dir)
    args.assignments.parent.mkdir(parents=True, exist_ok=True)
    pd.DataFrame({'unidad_id': frame['unidad_id'], 'segmento': result['etiquetas_cluster'],
                  'PC1': result['pca'][:, 0], 'PC2': result['pca'][:, 1]}).to_csv(args.assignments, index=False, mode='x')
    print(json.dumps(report, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
