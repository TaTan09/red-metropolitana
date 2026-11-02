import os
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from dotenv import load_dotenv
from sqlalchemy import create_engine
from sklearn.model_selection import StratifiedKFold
from sklearn.metrics import roc_auc_score
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression

# 1. Cargar variables de entorno y construir conexión robusta
load_dotenv()

pg_user = os.getenv("POSTGRES_USER", "postgres")
pg_pass = os.getenv("POSTGRES_PASSWORD", "postgres")
pg_host = os.getenv("POSTGRES_HOST", "127.0.0.1")
pg_port = os.getenv("POSTGRES_PORT", "5432")
pg_db = os.getenv("POSTGRES_DB", "red_metropolitana")

db_url = os.getenv(
    "DATABASE_URL",
    f"postgresql://{pg_user}:{pg_pass}@{pg_host}:{pg_port}/{pg_db}"
)
engine = create_engine(db_url)

print("Cargando datos del Corte A desde silver.silver_p2_features_tarjeta...")
query = """
SELECT 
    unidad_id,
    corte,
    fecha_corte,
    operador,
    viajes_28d,
    viajes_7d,
    viajes_14d,
    dias_activos_28d,
    dias_desde_ultimo_uso,
    gasto_28d_gtq,
    tarifa_media_gtq,
    puntos_origen_28d,
    proporcion_hora_pico,
    proporcion_fin_semana,
    etiqueta
FROM silver.silver_p2_features_tarjeta
WHERE corte = 'A';
"""
df_a = pd.read_sql(query, engine)
print(f"Filas cargadas: {len(df_a)} (esperadas: 77411)")

# 2. Definición de predictores y variable objetivo
num_cols = [
    'viajes_28d', 'viajes_7d', 'viajes_14d', 'dias_activos_28d',
    'dias_desde_ultimo_uso', 'gasto_28d_gtq', 'tarifa_media_gtq',
    'puntos_origen_28d', 'proporcion_hora_pico', 'proporcion_fin_semana'
]
cat_cols = ['operador']

X = df_a[num_cols + cat_cols]
y = df_a['etiqueta'].values

# 3. 5 Folds estratificados con semilla fija
skf = StratifiedKFold(n_splits=5, shuffle=True, random_state=2026)

# 4. Evaluación de Baselines de forma explícita en cada fold
print("\n--- Evaluando Baselines en Validación Cruzada ---")

# Baseline 1: Probabilidad constante igual a la tasa positiva de entrenamiento en cada pliegue
b1_scores = []
for train_idx, val_idx in skf.split(X, y):
    tasa_positiva_train = np.mean(y[train_idx])
    probs_b1 = np.full(shape=len(val_idx), fill_value=tasa_positiva_train)
    # roc_auc_score con vector constante produce 0.5 evaluado directamente
    score_b1 = roc_auc_score(y[val_idx], probs_b1)
    b1_scores.append(score_b1)

b1_mean, b1_std = np.mean(b1_scores), np.std(b1_scores)
print(f"Baseline 1 (Tasa positiva constante): ROC-AUC = {b1_mean:.4f} +/- {b1_std:.4f}")

# Baseline 2: Puntaje directo por recencia (dias_desde_ultimo_uso)
b2_scores = []
for _, val_idx in skf.split(X, y):
    score_b2 = roc_auc_score(y[val_idx], df_a.iloc[val_idx]['dias_desde_ultimo_uso'])
    b2_scores.append(score_b2)

b2_mean, b2_std = np.mean(b2_scores), np.std(b2_scores)
print(f"Baseline 2 (dias_desde_ultimo_uso): ROC-AUC = {b2_mean:.4f} +/- {b2_std:.4f}")

# 5. Preprocesamiento aislado dentro del pipeline
preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), num_cols),
        ('cat', OneHotEncoder(drop='first', sparse_output=False), cat_cols)
    ]
)

# 6. Comparación L1 vs L2 barriendo C (C = 1/lambda)
print("\n--- Entrenando Regresión Logística (L1 vs L2) ---")
c_values = [0.001, 0.01, 0.1, 1.0, 10.0, 100.0]
resultados = []

for penalty, solver in [('l2', 'lbfgs'), ('l1', 'saga')]:
    for C in c_values:
        fold_scores = []
        for train_idx, val_idx in skf.split(X, y):
            X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
            y_tr, y_val = y[train_idx], y[val_idx]
            
            clf = LogisticRegression(penalty=penalty, C=C, solver=solver, max_iter=1000, random_state=2026)
            pipe = Pipeline([('prep', preprocessor), ('clf', clf)])
            pipe.fit(X_tr, y_tr)
            
            val_probs = pipe.predict_proba(X_val)[:, 1]
            fold_scores.append(roc_auc_score(y_val, val_probs))
            
        lambd = 1.0 / C
        mean_s, std_s = np.mean(fold_scores), np.std(fold_scores)
        resultados.append({
            'penalty': penalty,
            'C': C,
            'lambda': lambd,
            'mean_auc': mean_s,
            'std_auc': std_s
        })
        print(f"Penalty={penalty.upper()} | lambda={lambd:8.4f} (C={C:6.3f}) | ROC-AUC: {mean_s:.4f} +/- {std_s:.4f}")

df_grid = pd.DataFrame(resultados)

# 7. Gráfica de Métrica vs Lambda
os.makedirs("docs/evidencias", exist_ok=True)
plt.figure(figsize=(8, 5))
for penalty, group in df_grid.groupby('penalty'):
    group_sorted = group.sort_values('lambda')
    plt.errorbar(group_sorted['lambda'], group_sorted['mean_auc'], yerr=group_sorted['std_auc'], 
                 label=f'Logistic ({penalty.upper()})', marker='o', capsize=4)

plt.xscale('log')
plt.xlabel(r'$\lambda$ (Castigo de regularización, escala logarítmica)')
plt.ylabel('ROC-AUC (CV 5-folds)')
plt.title('Selección de Regularización: ROC-AUC vs. Lambda en Corte A')
plt.legend()
plt.grid(True, which='both', linestyle='--', alpha=0.5)
plt.tight_layout()
grafica_path = "docs/evidencias/p2-14-lambda-vs-auc.png"
plt.savefig(grafica_path)
plt.close()
print(f"\nGráfica guardada en: {grafica_path}")

# 8. Selección del mejor modelo y generación de OOF para Héctor (2.2)
best_row = df_grid.sort_values(by='mean_auc', ascending=False).iloc[0]
best_penalty = best_row['penalty']
best_C = best_row['C']
best_solver = 'lbfgs' if best_penalty == 'l2' else 'saga'

print(f"\nMejor modelo seleccionado: {best_penalty.upper()} con C={best_C} (lambda={best_row['lambda']:.4f})")

df_oof = df_a[['unidad_id', 'fecha_corte', 'etiqueta']].copy()
df_oof['corte'] = 'A'
df_oof['fold'] = -1
df_oof['probabilidad_abandono'] = 0.0
df_oof['modelo'] = f"logistica_{best_penalty}_C{best_C}"

for fold_num, (train_idx, val_idx) in enumerate(skf.split(X, y)):
    X_tr, X_val = X.iloc[train_idx], X.iloc[val_idx]
    y_tr, y_val = y[train_idx], y[val_idx]
    
    pipe = Pipeline([
        ('prep', preprocessor),
        ('clf', LogisticRegression(penalty=best_penalty, C=best_C, solver=best_solver, max_iter=1000, random_state=2026))
    ])
    pipe.fit(X_tr, y_tr)
    df_oof.loc[val_idx, 'fold'] = fold_num
    df_oof.loc[val_idx, 'probabilidad_abandono'] = pipe.predict_proba(X_val)[:, 1]

os.makedirs("datos_red", exist_ok=True)
oof_path = "datos_red/p2-14-oof-predicciones-a.csv"
df_oof.to_csv(oof_path, index=False)
print(f"Predicciones Out-Of-Fold (OOF) guardadas en: {oof_path}")

# 9. Coeficientes del modelo entrenado en todo A
final_pipe = Pipeline([
    ('prep', preprocessor),
    ('clf', LogisticRegression(penalty=best_penalty, C=best_C, solver=best_solver, max_iter=1000, random_state=2026))
])
final_pipe.fit(X, y)

feature_names = final_pipe.named_steps['prep'].get_feature_names_out()
coefs = final_pipe.named_steps['clf'].coef_[0]
df_coefs = pd.DataFrame({'feature': feature_names, 'coeficiente': coefs})
df_coefs['abs_coef'] = df_coefs['coeficiente'].abs()
df_coefs = df_coefs.sort_values(by='coeficiente', ascending=False)

print("\n--- Coeficientes que más empujan al abandono ---")
print(df_coefs.head(5).to_string(index=False))

coef_path = "docs/evidencias/p2-14-coeficientes.csv"
df_coefs.to_csv(coef_path, index=False)
print(f"Tabla completa de coeficientes guardada en: {coef_path}")
