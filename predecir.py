import os
import argparse
import joblib
import pandas as pd
from sqlalchemy import create_engine
from dotenv import load_dotenv

def main():
    parser = argparse.ArgumentParser(description="Script de inferencia para predicción de abandono.")
    parser.add_argument("--corte", type=str, default="C", help="Corte a evaluar (ej. C)")
    parser.add_argument("--umbral", type=float, default=0.5, help="Umbral de decisión óptimo definido en la Fase 2.2")
    parser.add_argument("--output", type=str, default="datos_red/p2-24-predicciones-c.csv", help="Ruta del CSV de salida")
    args = parser.parse_args()

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

    print(f"Cargando datos del Corte {args.corte} desde PostgreSQL...")
    query = f"""
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
        proporcion_fin_semana
    FROM silver.silver_p2_features_tarjeta
    WHERE corte = '{args.corte}';
    """
    df_c = pd.read_sql(query, engine)
    print(f"Registros cargados para Corte {args.corte}: {len(df_c)}")

    model_path = "models/modelo_abandono_v1.joblib"
    if not os.path.exists(model_path):
        raise FileNotFoundError(f"No se encontró el modelo serializado en {model_path}. Ejecuta primero scripts/serializar_modelo.py")

    print(f"Cargando modelo desde {model_path}...")
    model = joblib.load(model_path)

    num_cols = [
        'viajes_28d', 'viajes_7d', 'viajes_14d', 'dias_activos_28d',
        'dias_desde_ultimo_uso', 'gasto_28d_gtq', 'tarifa_media_gtq',
        'puntos_origen_28d', 'proporcion_hora_pico', 'proporcion_fin_semana'
    ]
    cat_cols = ['operador']

    X_c = df_c[num_cols + cat_cols]

    print("Calculando probabilidades de abandono...")
    probs = model.predict_proba(X_c)[:, 1]

    df_output = df_c[['unidad_id', 'fecha_corte']].copy()
    df_output['tarjetas'] = 1  # Conteo unitario por tarjeta
    df_output['puntaje'] = probs
    df_output['contactar'] = (probs >= args.umbral).astype(int)
    df_output['modelo_version'] = 'v1_logistica_l2'

    os.makedirs(os.path.dirname(args.output), exist_ok=True)
    df_output.to_csv(args.output, index=False)
    print(f"Predicciones generadas y guardadas exitosamente en: {args.output}")
    print(f"Total de usuarios a contactar según umbral {args.umbral}: {df_output['contactar'].sum()} de {len(df_output)}")

if __name__ == "__main__":
    main()
