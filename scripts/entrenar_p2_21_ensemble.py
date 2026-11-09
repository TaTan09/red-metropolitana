#!/usr/bin/env python3
"""Compara baselines, logística y bosque en cinco folds del corte A."""
from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import os
import sys
import tempfile
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.compose import ColumnTransformer
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.exceptions import ConvergenceWarning
from sklearn.inspection import permutation_importance
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import roc_auc_score
from sklearn.model_selection import StratifiedKFold, StratifiedShuffleSplit
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder, StandardScaler
from threadpoolctl import threadpool_limits

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.auditar_fuga_p2_13 import FEATURES, connect, render_model  # noqa: E402

SEED = 2026
N_FOLDS = 5
CUT_DATE = pd.Timestamp("2026-07-01")
PREDICTORS = (*FEATURES, "operador")
IDENTIFIERS = ("unidad_id", "corte", "fecha_corte", "etiqueta")
INPUT_COLUMNS = (*IDENTIFIERS, *PREDICTORS)
QUERY = f"""
SELECT {", ".join(INPUT_COLUMNS)}
FROM silver.silver_p2_features_tarjeta
WHERE corte = 'A' AND fecha_corte = timestamp '2026-07-01 00:00:00'
ORDER BY unidad_id
"""
OOF_COLUMNS = (*IDENTIFIERS, "fold", "probabilidad_abandono", "modelo", "configuracion_modelo")
OOF_PATH = ROOT / "datos_red/p2-21-oof-a.csv"
EVIDENCE = ROOT / "docs/evidencias"
REPORT = ROOT / "docs/metricas/p2-21-ensemble.md"
REPEATS = 5
RF_IMPORTANCE_LIMIT = 4000
RF_MIN_GAIN = 0.002
RF_MIN_FOLD_WINS = 4
RF_STD_TOLERANCE = 0.002
RF_GAP_TOLERANCE = 0.020
RF_COMPLEXITY_TOLERANCE = 0.001

LOGISTIC_COMMON = {"max_iter": 1000, "random_state": SEED, "tol": 1e-4}
FOREST_COMMON = {"n_estimators": 100, "max_features": "sqrt", "bootstrap": True,
                 "criterion": "gini", "random_state": SEED, "n_jobs": 1}
# Los bosques aparecen en orden de menor a mayor complejidad.
MODELS = {
    "baseline_tasa": {"familia": "constante", "parametros": {"strategy": "prior"}},
    "baseline_recencia": {"familia": "recencia", "parametros": {"variable": "dias_desde_ultimo_uso"}},
    "logistica_l1": {"familia": "logistica", "parametros": {
        **LOGISTIC_COMMON, "C": 0.1, "l1_ratio": 1.0, "solver": "saga"}},
    "logistica_l2": {"familia": "logistica", "parametros": {
        **LOGISTIC_COMMON, "C": 0.01, "l1_ratio": 0.0, "solver": "lbfgs"}},
    "rf_somero": {"familia": "bosque", "parametros": {
        **FOREST_COMMON, "max_depth": 6, "min_samples_leaf": 50}},
    "rf_regularizado": {"familia": "bosque", "parametros": {
        **FOREST_COMMON, "max_depth": 12, "min_samples_leaf": 20}},
    "rf_flexible": {"familia": "bosque", "parametros": {
        **FOREST_COMMON, "max_depth": None, "min_samples_leaf": 5}},
}


def prepare_cut_a(frame):
    if set(frame.columns) != set(INPUT_COLUMNS) or not frame.columns.is_unique:
        raise ValueError("El esquema debe coincidir con los identificadores y predictores de 1.4")
    data = frame.loc[:, list(INPUT_COLUMNS)].copy()
    data["fecha_corte"] = pd.to_datetime(data["fecha_corte"])
    if data.empty or not data["corte"].isin(["A"]).all() or not data["fecha_corte"].eq(CUT_DATE).all():
        raise ValueError("Se requiere únicamente el corte A del 2026-07-01")
    if data["unidad_id"].isna().any():
        raise ValueError("unidad_id contiene nulos")
    data["unidad_id"] = data["unidad_id"].astype(str)
    if data["unidad_id"].str.strip().eq("").any() or data["unidad_id"].duplicated().any():
        raise ValueError("unidad_id debe ser único y no vacío")
    if not data["etiqueta"].isin([0, 1]).all():
        raise ValueError("Las etiquetas deben ser 0/1 y sin nulos")
    data["etiqueta"] = data["etiqueta"].astype(int)
    for feature in FEATURES:
        data[feature] = pd.to_numeric(data[feature], errors="raise").astype(float)
    if not np.isfinite(data[list(FEATURES)].to_numpy()).all():
        raise ValueError("Los predictores numéricos deben ser finitos y sin nulos")
    if data["operador"].isna().any() or data["operador"].astype(str).str.strip().eq("").any():
        raise ValueError("operador debe estar informado")
    return data.sort_values("unidad_id", kind="stable").reset_index(drop=True)


def recalculated_query():
    usos = render_model("silver_p2_usos_tarjeta")
    features = render_model("silver_p2_features_tarjeta", refs={
        "silver_p2_usos_tarjeta": "usos_validos",
        "silver_p2_poblacion_tarjeta": "poblacion_a",
    })
    return f"""
WITH poblacion_a AS MATERIALIZED (
    SELECT unidad_id, corte, fecha_corte, operador, llave_operacional, etiqueta
    FROM silver.silver_p2_poblacion_tarjeta
    WHERE corte = 'A' AND fecha_corte = timestamp '2026-07-01 00:00:00'
), usos_validos AS ({usos}), features_a AS ({features})
{QUERY.replace("FROM silver.silver_p2_features_tarjeta", "FROM features_a")}
"""


def load_cut_a(*, recalculate=False):
    with connect() as conn:
        conn.execute("set transaction read only")
        rows = conn.execute(recalculated_query() if recalculate else QUERY).fetchall()
    data = prepare_cut_a(pd.DataFrame(rows, columns=INPUT_COLUMNS))
    # Misma serialización de la evidencia 1.3, antes de convertir NUMERIC a float.
    digest = hashlib.sha256()
    for row in sorted(rows, key=lambda row: row["unidad_id"]):
        line = json.dumps(row, sort_keys=True, default=str, ensure_ascii=False, separators=(",", ":"))
        digest.update((line + "\n").encode("utf-8"))
    published = json.loads((ROOT / "docs/metricas/p2-13-features.json").read_text(encoding="utf-8"))
    expected = next(row["sha256_filas_ordenadas"] for row in published["cortes"] if row["corte"] == "A")
    matches = digest.hexdigest() == expected
    if recalculate and not matches:
        raise ValueError(f"El recálculo de A no coincide con la huella publicada de 1.3 ({digest.hexdigest()})")
    data.attrs["origen"] = {
        "consulta": "SQL original de 1.3 en CTE de solo lectura" if recalculate
        else "silver.silver_p2_features_tarjeta",
        "sha256_filas_formato_13": digest.hexdigest(), "coincide_con_13_publicado": matches,
        "recalcular_a": recalculate,
    }
    return data


def make_folds(y):
    if min(np.bincount(y, minlength=2)) < N_FOLDS:
        raise ValueError("Cada clase necesita al menos cinco tarjetas")
    return list(StratifiedKFold(n_splits=N_FOLDS, shuffle=True, random_state=SEED)
                .split(np.zeros(len(y)), y))


def build_model(spec):
    """Construye un Pipeline nuevo a partir de recomendado.configuracion del JSON."""
    family = spec["familia"]
    params = spec["parametros"]
    if family == "constante":
        return Pipeline([("clf", DummyClassifier(**params))])
    if family not in {"logistica", "bosque"}:
        raise ValueError(f"Familia sin estimador probabilístico: {family}")
    prep = ColumnTransformer([
        ("num", StandardScaler() if family == "logistica" else "passthrough", list(FEATURES)),
        ("cat", OneHotEncoder(drop="first" if family == "logistica" else None,
                              handle_unknown="ignore", sparse_output=False), ["operador"]),
    ])
    estimator = LogisticRegression if family == "logistica" else RandomForestClassifier
    return Pipeline([("prep", prep), ("clf", estimator(**params))])


def fit_fold(spec, X_train, y_train):
    model = build_model(spec)
    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter("always", ConvergenceWarning)
        model.fit(X_train, y_train)
    convergence = sum(issubclass(w.category, ConvergenceWarning) for w in captured)
    for warning in captured:
        if not issubclass(warning.category, ConvergenceWarning):
            warnings.warn(warning.message, warning.category, stacklevel=2)
    return model, convergence


def evaluate(X, y, folds):
    results, predictions = {}, {}
    for name, spec in MODELS.items():
        oof = np.full(len(y), np.nan)
        fold_rows = []
        for fold, (train, valid) in enumerate(folds):
            if spec["familia"] == "recencia":
                scores = X[spec["parametros"]["variable"]].to_numpy()
                train_score, valid_score = scores[train], scores[valid]
                convergence = 0
            else:
                model, convergence = fit_fold(spec, X.iloc[train], y[train])
                train_score = model.predict_proba(X.iloc[train])[:, 1]
                valid_score = model.predict_proba(X.iloc[valid])[:, 1]
            if np.isfinite(oof[valid]).any():
                raise ValueError("Tarjeta repetida entre folds de validación")
            oof[valid] = valid_score
            auc_train = float(roc_auc_score(y[train], train_score))
            auc_valid = float(roc_auc_score(y[valid], valid_score))
            fold_rows.append({"fold": fold, "auc_entrenamiento": auc_train, "auc_validacion": auc_valid,
                              "brecha": auc_train - auc_valid, "avisos_convergencia": convergence})
        if not np.isfinite(oof).all():
            raise ValueError("Predicciones OOF incompletas")
        stats = {}
        for metric in ("auc_entrenamiento", "auc_validacion", "brecha"):
            values = [row[metric] for row in fold_rows]
            stats[metric] = {"media": float(np.mean(values)), "de": float(np.std(values, ddof=0))}
        results[name] = {"configuracion": spec, "folds": fold_rows, **stats}
        predictions[name] = oof
        print(f"{name} | AUC validación {stats['auc_validacion']['media']:.6f}", flush=True)
    return results, predictions


def choose_model(results):
    converged = {name: row for name, row in results.items()
                 if not any(fold["avisos_convergencia"] for fold in row["folds"])}
    logistics = [name for name, row in converged.items() if row["configuracion"]["familia"] == "logistica"]
    if not logistics:
        raise ValueError("Las logísticas no convergieron. Revisar la comparación antes de recomendar.")
    best_logistic = max(logistics, key=lambda name: (results[name]["auc_validacion"]["media"],
                                                      -results[name]["auc_validacion"]["de"]))
    baseline = results[best_logistic]
    comparisons = {}
    for name, row in results.items():
        if row["configuracion"]["familia"] != "bosque":
            continue
        delta = [a["auc_validacion"] - b["auc_validacion"] for a, b in zip(row["folds"], baseline["folds"])]
        gain = float(np.mean(delta))
        wins = sum(value > 0 for value in delta)
        stable = row["auc_validacion"]["de"] <= baseline["auc_validacion"]["de"] + RF_STD_TOLERANCE
        gap_ok = row["brecha"]["media"] <= baseline["brecha"]["media"] + RF_GAP_TOLERANCE
        comparisons[name] = {"delta_auc_por_fold": delta, "delta_auc_medio": gain, "folds_ganados": wins,
                             "cumple_estabilidad": stable, "cumple_brecha": gap_ok,
                             "elegible": name in converged and gain >= RF_MIN_GAIN and
                             wins >= RF_MIN_FOLD_WINS and stable and gap_ok}
    eligible = [name for name in MODELS if name in comparisons and comparisons[name]["elegible"]]
    winner = best_logistic
    if eligible:
        best_gain = max(comparisons[name]["delta_auc_medio"] for name in eligible)
        winner = next(name for name in eligible
                      if comparisons[name]["delta_auc_medio"] >= best_gain - RF_COMPLEXITY_TOLERANCE)
    return {"modelo": winner, "configuracion": results[winner]["configuracion"],
            "mejor_logistica": best_logistic, "bosques_vs_logistica": comparisons,
            "delta_auc_vs_logistica": results[winner]["auc_validacion"]["media"] - baseline["auc_validacion"]["media"]}


def validation_importance(spec, X, y, folds, oof):
    fold_importances, sample_sizes = [], []
    for fold, (train, valid) in enumerate(folds):
        model, convergence = fit_fold(spec, X.iloc[train], y[train])
        if convergence or not np.array_equal(model.predict_proba(X.iloc[valid])[:, 1], oof[valid]):
            raise RuntimeError("El reajuste de importancia no reprodujo las predicciones del fold")
        sample = valid
        if spec["familia"] == "bosque" and len(valid) > RF_IMPORTANCE_LIMIT:
            splitter = StratifiedShuffleSplit(n_splits=1, train_size=RF_IMPORTANCE_LIMIT,
                                               random_state=SEED + fold)
            local, _ = next(splitter.split(X.iloc[valid], y[valid]))
            sample = valid[np.sort(local)]
        permutation = permutation_importance(
            model, X.iloc[sample], y[sample], scoring="roc_auc", n_repeats=REPEATS,
            random_state=SEED + fold, n_jobs=1,
        )
        fold_importances.append(permutation.importances)
        sample_sizes.append({"fold": fold, "validacion": len(valid), "muestra": len(sample),
                             "positivos_muestra": int(y[sample].sum()), "semilla": SEED + fold})
    values = np.stack(fold_importances)  # fold × variable original × permutación
    means = values.mean(axis=2)
    rows = [{"variable": name, "caida_auc_media": float(means[:, i].mean()),
             "de_entre_folds": float(means[:, i].std(ddof=0)),
             "de_permutacion_media": float(values[:, i, :].std(axis=1, ddof=0).mean()),
             "caidas_auc_por_fold": values[:, i, :].tolist()} for i, name in enumerate(PREDICTORS)]
    return {"repeticiones": REPEATS, "muestras": sample_sizes,
            "variables": sorted(rows, key=lambda row: -row["caida_auc_media"])}


def fold_assignment(folds, size):
    assignment = np.full(size, -1, dtype=int)
    for fold, (train, valid) in enumerate(folds):
        if np.intersect1d(train, valid).size or np.any(assignment[valid] >= 0):
            raise ValueError("Los folds no aíslan entrenamiento y validación")
        assignment[valid] = fold
    if np.any(assignment < 0):
        raise ValueError("Hay tarjetas fuera de los folds de validación")
    return assignment


def build_oof(data, folds, scores, recommended):
    scores = np.asarray(scores)
    if scores.shape != (len(data),) or not np.isfinite(scores).all() or np.any((scores < 0) | (scores > 1)):
        raise ValueError("Las probabilidades OOF deben estar completas y dentro de [0, 1]")
    result = data[list(IDENTIFIERS)].copy()
    result["fold"] = fold_assignment(folds, len(data))
    result["probabilidad_abandono"] = scores
    result["modelo"] = recommended["modelo"]
    result["configuracion_modelo"] = json.dumps(recommended["configuracion"], sort_keys=True)
    return result.loc[:, list(OOF_COLUMNS)]


def run_experiment(frame):
    data = prepare_cut_a(frame)
    X = data.loc[:, list(PREDICTORS)]
    y = data["etiqueta"].to_numpy()
    folds = make_folds(y)
    with threadpool_limits(limits=1):
        results, predictions = evaluate(X, y, folds)
        recommended = choose_model(results)
        scores = predictions[recommended["modelo"]]
        importance = validation_importance(recommended["configuracion"], X, y, folds, scores)
    oof = build_oof(data, folds, scores, recommended)
    summary = {"corte": "A", "fecha_corte": str(CUT_DATE), "filas": len(data), "positivos": int(y.sum()),
               "origen": frame.attrs.get("origen"),
               "predictores": list(PREDICTORS), "semilla": SEED, "n_folds": N_FOLDS,
               "versiones": {"python": sys.version.split()[0], **{
                   name: importlib.metadata.version(name)
                   for name in ("scikit-learn", "numpy", "pandas", "scipy", "threadpoolctl", "joblib")}},
               "entrada_sha256": sha256(data.to_csv(index=False, lineterminator="\n")),
               "folds_sha256": sha256(oof[["unidad_id", "fold"]].to_csv(index=False, lineterminator="\n")),
               "folds": [{"fold": i, "entrenamiento": len(train), "validacion": len(valid),
                          "positivos_validacion": int(y[valid].sum())} for i, (train, valid) in enumerate(folds)],
               "criterio_bosque": {"ganancia_minima": RF_MIN_GAIN, "folds_ganados_minimos": RF_MIN_FOLD_WINS,
                                  "tolerancia_de": RF_STD_TOLERANCE, "tolerancia_brecha": RF_GAP_TOLERANCE,
                                  "tolerancia_para_preferir_bosque_mas_simple": RF_COMPLEXITY_TOLERANCE},
               "modelos": results, "recomendado": recommended, "importancia": importance,
               "auc_oof_recomendado": float(roc_auc_score(y, scores))}
    return summary, oof


def sha256(value):
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def write_text(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(mode="w", encoding="utf-8", newline="\n",
                                     dir=path.parent, delete=False) as pending:
        temp_path = Path(pending.name)
        pending.write(value)
    try:
        os.replace(temp_path, path)
    finally:
        temp_path.unlink(missing_ok=True)


def render_report(result):
    decision = result["recomendado"]
    models = result["modelos"]
    origin = result["origen"]
    versions = result["versiones"]
    libraries = ", ".join(f"`{name}=={version}`" for name, version in versions.items() if name != "python")
    criteria = result["criterio_bosque"]
    provenance = f"Se leyó A desde {origin['consulta']}."
    if origin["coincide_con_13_publicado"]:
        provenance += " La huella de todas las filas y etiquetas coincide con la publicada para A en 1.3."
    command = "python scripts/entrenar_p2_21_ensemble.py"
    if origin["recalcular_a"]:
        command += " --recalcular-a"
    lines = ["# Proyecto 2 · 2.1 Ensemble y sesgo-varianza", "",
             f"Se recomienda **{decision['modelo']}**. Su ROC-AUC medio cambia "
             f"{decision['delta_auc_vs_logistica']:+.6f} frente a {decision['mejor_logistica']}.", "",
             f"Corte A del 1 de julio de 2026. {result['filas']:,} tarjetas, "
             f"{result['positivos']:,} positivas. Cinco folds estratificados con mezcla y semilla 2026.", "",
             provenance, "",
             f"La ejecución reportada utilizó Python {versions['python']} con {libraries}. "
             "Las versiones quedan registradas en [la evidencia JSON](../evidencias/p2-21-ensemble.json).", "",
             "Se ordenó por unidad_id antes de separar los folds. Se recalcularon los dos baselines y "
             "las configuraciones seleccionadas de 1.4 (L1 C=0.1, L2 C=0.01). El orden estable puede "
             "cambiar la asignación de la corrida histórica, cuya consulta carecía de ORDER BY.", "",
             "| Modelo | AUC entrenamiento, media ± DE | AUC validación, media ± DE | Brecha, media ± DE |",
             "|---|---:|---:|---:|"]
    for name, row in models.items():
        stats = [f"{row[key]['media']:.6f} ± {row[key]['de']:.6f}"
                 for key in ("auc_entrenamiento", "auc_validacion", "brecha")]
        lines.append(f"| {name} | {' | '.join(stats)} |")
    lines.extend(["", "La DE es descriptiva sobre los cinco folds (ddof=0). Brecha = AUC de entrenamiento "
                  "menos AUC de validación en cada fold. El AUC evalúa ordenamiento de riesgo.", "",
                  "## Sesgo y varianza observados", "",
                  f"- Tasa constante. AUC {models['baseline_tasa']['auc_validacion']['media']:.6f}. "
                  "El puntaje igual para todas las tarjetas del fold carece de discriminación.",
                  f"- Recencia. AUC {models['baseline_recencia']['auc_validacion']['media']:.6f} con una "
                  "regla fija de una variable. La diferencia entre conjuntos refleja su composición.",
                  f"- L1 y L2. Sus brechas son {models['logistica_l1']['brecha']['media']:.6f} y "
                  f"{models['logistica_l2']['brecha']['media']:.6f}. La regularización limita el ajuste "
                  "a patrones particulares de entrenamiento. L1 puede anular coeficientes y L2 los contrae."])
    for name in ("rf_somero", "rf_regularizado", "rf_flexible"):
        row = models[name]
        params = row["configuracion"]["parametros"]
        lines.append(f"- {name}. Profundidad {params['max_depth']}, hoja mínima {params['min_samples_leaf']}, "
                     f"brecha {row['brecha']['media']:.6f} y AUC validación {row['auc_validacion']['media']:.6f}.")
    forest_names = ("rf_somero", "rf_regularizado", "rf_flexible")
    widest = max(forest_names, key=lambda name: models[name]["brecha"]["media"])
    best_valid = max(forest_names, key=lambda name: models[name]["auc_validacion"]["media"])
    shallow, flexible = models["rf_somero"], models["rf_flexible"]
    train_change = flexible["auc_entrenamiento"]["media"] - shallow["auc_entrenamiento"]["media"]
    valid_change = flexible["auc_validacion"]["media"] - shallow["auc_validacion"]["media"]
    lines.extend(["", f"El bosque con mayor brecha fue {widest}. El mejor AUC de validación entre bosques "
                  f"fue el de {best_valid}. Del bosque somero al flexible el AUC cambia {train_change:+.6f} "
                  f"en entrenamiento y {valid_change:+.6f} en validación. El límite de profundidad y el "
                  "mínimo por hoja restringen el ajuste del somero, mientras que las hojas pequeñas "
                  "permiten interacciones más específicas. Mantener cien árboles y el mismo muestreo "
                  "por árbol concentra la comparación en profundidad y tamaño de hoja. "
                  "La brecha y la DE entre folds describen optimismo y dispersión empíricos. "
                  "La descomposición matemática de sesgo y varianza requeriría otro diseño.", "",
                  "## Decisión", ""])
    regularized = models["rf_regularizado"]
    if (decision["modelo"] == "rf_somero"
            and regularized["auc_validacion"]["media"] > shallow["auc_validacion"]["media"]
            and regularized["brecha"]["media"] > shallow["brecha"]["media"]):
        lines.extend([
            "La recomendación de `rf_somero` equilibra el ROC-AUC de validación, "
            "la complejidad del modelo y la brecha de generalización. "
            f"`rf_regularizado` alcanzó un AUC ligeramente mayor ({regularized['auc_validacion']['media']:.6f} "
            f"frente a {shallow['auc_validacion']['media']:.6f}) y presentó una brecha mayor "
            f"({regularized['brecha']['media']:.6f} frente a {shallow['brecha']['media']:.6f}). "
            "La menor profundidad y la menor brecha del bosque somero justifican recomendarlo "
            "pese a esa pequeña diferencia de AUC.", ""])
    lines.extend([
        "En esta implementación, un bosque es elegible si supera a la mejor logística convergente "
        f"por al menos {criteria['ganancia_minima']:.3f} de AUC medio, gana al menos "
        f"{criteria['folds_ganados_minimos']} de {result['n_folds']} folds y mantiene su DE y su brecha "
        f"dentro de {criteria['tolerancia_de']:.3f} y {criteria['tolerancia_brecha']:.3f} adicionales, "
        "respectivamente. Entre los bosques elegibles, se prefiere el menos complejo cuyo AUC medio "
        f"quede a una distancia de hasta {criteria['tolerancia_para_preferir_bosque_mas_simple']:.3f} "
        "del mejor. Si ningún bosque cumple los criterios, se recomienda la mejor logística convergente.", "",
        "| Bosque | Delta AUC medio | Folds ganados | Estabilidad | Brecha | Elegible |",
        "|---|---:|---:|---|---|---|"])
    for name, comparison in decision["bosques_vs_logistica"].items():
        checks = ["Sí" if comparison[key] else "No" for key in
                  ("cumple_estabilidad", "cumple_brecha", "elegible")]
        lines.append(f"| {name} | {comparison['delta_auc_medio']:+.6f} | "
                     f"{comparison['folds_ganados']}/5 | {' | '.join(checks)} |")
    lines.extend(["", "```json", json.dumps(decision["configuracion"], indent=2), "```", "",
                  "## Importancia por permutación", "",
                  "Se permuta cada columna original antes del Pipeline ajustado en el fold. Se registra "
                  "la caída de ROC-AUC de validación con cinco permutaciones por variable. El promedio "
                  "pondera igual los folds. La DE entre folds usa sus medias y la DE de permutación "
                  "promedia la dispersión de las cinco repeticiones en cada fold. Una importancia negativa "
                  "se conserva. Variables correlacionadas pueden compartir o sustituir señal.", "",
                  "Se utilizaron " +
                  ", ".join(f"{r['muestra']}/{r['validacion']}" for r in result["importancia"]["muestras"]) +
                  " filas de validación en los folds 0–4.",
                  "Para un bosque se limita el cálculo a 4,000 filas estratificadas por fold cuando se "
                  "supera ese tamaño. Esto acota el costo de las predicciones repetidas en cien árboles. "
                  "La comparación de AUC y la exportación OOF utilizan todos los registros.", "",
                  "| Variable original | Caída AUC media | DE entre folds | DE media de permutación |",
                  "|---|---:|---:|---:|"])
    for row in result["importancia"]["variables"][:10]:
        lines.append(f"| {row['variable']} | {row['caida_auc_media']:+.6f} | "
                     f"{row['de_entre_folds']:.6f} | {row['de_permutacion_media']:.6f} |")
    lines.extend(["", "## Resumen de implementación y continuidad", "",
                  "El requisito 2.1 completó la comparación de baselines, logísticas y bosques en A, "
                  "el análisis de las brechas de generalización, la importancia por permutación "
                  f"en validación y la generación de predicciones OOF para `{decision['modelo']}`, "
                  "el modelo recomendado.", "",
                  "Héctor debe usar las probabilidades OOF y las etiquetas de A para fijar el umbral "
                  "de 2.2, junto con la configuración del modelo y el orden de predictores registrados "
                  "en la evidencia. El CSV local `datos_red/p2-21-oof-a.csv` está ignorado por Git. "
                  "Debe compartirse directamente o regenerarse con el comando de abajo. "
                  "[Evidencia JSON](../evidencias/p2-21-ensemble.json).", "",
                  "Después de que Héctor fije el umbral, Alejandro deberá reutilizar en 2.4 "
                  "la configuración definitiva del modelo, su preprocesamiento y ese umbral.", "",
                  "## Reproducción", "",
                  "Desde la raíz, con el entorno de requirements-ml.txt y PostgreSQL configurado "
                  "mediante POSTGRES_HOST, POSTGRES_PORT, POSTGRES_DB, POSTGRES_USER y POSTGRES_PASSWORD en .env.", "",
                  "```powershell", command, "```", "",
                  "El comando sin opciones lee la tabla materializada de 1.3. La opción "
                  "`--recalcular-a` ejecuta el SQL original de 1.3 sobre Silver y la población A "
                  "de 1.2 en una transacción de solo lectura. Exige coincidencia con la huella "
                  "publicada de A antes de entrenar.", "",
                  "El CSV contiene una predicción de validación por tarjeta, con fold 0–4 y configuración. "
                  "El JSON conserva hashes, versiones, métricas y permutaciones por fold. Para el "
                  "reajuste posterior en todo A, usar `build_model(recomendado['configuracion'])` "
                  "con el orden de predictores del JSON.", "",
                  f"El AUC OOF agrupado fue {result['auc_oof_recomendado']:.6f}. "
                  "El AUC medio de folds es la métrica principal. La selección y el AUC se calcularon "
                  "en los mismos folds de A. La evaluación final del modelo elegido requiere un conjunto separado.", "",
                  f"El SHA-256 del CSV OOF es `{result['oof_sha256']}`.", ""])
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--recalcular-a", action="store_true",
                        help="Reproducir A con el SQL de 1.3 si falta la tabla materializada")
    args = parser.parse_args(argv)
    data = load_cut_a(recalculate=args.recalcular_a)
    print(f"Corte A: {len(data):,} tarjetas", flush=True)
    result, oof = run_experiment(data)
    csv = oof.to_csv(index=False, lineterminator="\n", float_format="%.17g")
    result["oof_sha256"] = sha256(csv)
    write_text(OOF_PATH, csv)
    write_text(EVIDENCE / "p2-21-ensemble.json", json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False) + "\n")
    write_text(REPORT, render_report(result))
    print(f"Recomendado: {result['recomendado']['modelo']} | OOF: {len(oof):,} tarjetas", flush=True)


if __name__ == "__main__":
    main()
