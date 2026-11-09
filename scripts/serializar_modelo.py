import os
import joblib
import pandas as pd
from sqlalchemy import create_engine
from sklearn.pipeline import Pipeline
from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import StandardScaler, OneHotEncoder
from sklearn.linear_model import LogisticRegression
from dotenv import load_dotenv

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

print("Cargando todo el Corte A para entrenar el modelo final de producción...")
query = """
SELECT 
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

num_cols = [
    'viajes_28d', 'viajes_7d', 'viajes_14d', 'dias_activos_28d',
    'dias_desde_ultimo_uso', 'gasto_28d_gtq', 'tarifa_media_gtq',
    'puntos_origen_28d', 'proporcion_hora_pico', 'proporcion_fin_semana'
]
cat_cols = ['operador']

X = df_a[num_cols + cat_cols]
y = df_a['etiqueta'].values

preprocessor = ColumnTransformer(
    transformers=[
        ('num', StandardScaler(), num_cols),
        ('cat', OneHotEncoder(drop='first', sparse_output=False), cat_cols)
    ]
)

# Modelo definitivo seleccionado en la Fase 1 (Regresión Logística L2, C=0.01)
clf = LogisticRegression(penalty='l2', C=0.01, solver='lbfgs', max_iter=1000, random_state=2026)
pipeline = Pipeline([('prep', preprocessor), ('clf', clf)])

print("Ajustando pipeline completo con Corte A...")
pipeline.fit(X, y)

os.makedirs("models", exist_ok=True)
model_path = "models/modelo_abandono_v1.joblib"
joblib.dump(pipeline, model_path)
print(f"Modelo serializado exitosamente en: {model_path}")
