import os
import pandas as pd
from sqlalchemy import create_engine, text
from dotenv import load_dotenv

load_dotenv()

user = os.getenv("POSTGRES_USER", "red_user")
pwd = os.getenv("POSTGRES_PASSWORD", "red_password")
host = os.getenv("POSTGRES_HOST", "localhost")
port = os.getenv("POSTGRES_PORT", "5433")
db = os.getenv("POSTGRES_DB", "red_metropolitana")

engine = create_engine(f"postgresql+psycopg://{user}:{pwd}@{host}:{port}/{db}")

with engine.begin() as conn:
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS bronze;"))
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS staging;"))
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS silver;"))
    conn.execute(text("CREATE SCHEMA IF NOT EXISTS gold;"))

print("1. Cargando Transmetro Validaciones...")
df_tm = pd.read_csv("data/raw/transmetro_validaciones.csv")
df_tm["ingesta_timestamp"] = pd.Timestamp.now()
df_tm.to_sql("transmetro_validaciones", engine, schema="bronze", if_exists="replace", index=False)

print("2. Cargando Transurbano Transacciones...")
df_tu = pd.read_csv("data/raw/transurbano_transacciones.csv")
df_tu["ingesta_timestamp"] = pd.Timestamp.now()
df_tu.to_sql("transurbano_transacciones", engine, schema="bronze", if_exists="replace", index=False)

print("3. Cargando Aerómetro Boardings...")
df_am = pd.read_csv("data/raw/aerometro_boardings.csv")
df_am["ingesta_timestamp"] = pd.Timestamp.now()
df_am.to_sql("aerometro_boardings", engine, schema="bronze", if_exists="replace", index=False)

print("4. Cargando MetroRiel Viajes (aplanando JSON anidado)...")
df_mr_raw = pd.read_json("data/raw/metroriel_viajes.jsonl", lines=True)

# Aplanar diccionarios anidados de entry y exit
entry_df = pd.json_normalize(df_mr_raw["entry"]).rename(
    columns={"station": "origen_estacion_id", "ts": "fecha_hora_ingreso"}
)

# exit puede tener filas None/nulas
exit_df = pd.json_normalize(df_mr_raw["exit"]).rename(
    columns={"station": "destino_estacion_id", "ts": "fecha_hora_salida"}
)

df_mr = pd.DataFrame({
    "viaje_id": df_mr_raw["trip_id"].astype(str),
    "tarjeta_mr": df_mr_raw["card"].astype(str),
    "origen_estacion_id": entry_df["origen_estacion_id"].astype(str),
    "fecha_hora_ingreso": pd.to_datetime(entry_df["fecha_hora_ingreso"]),
    "destino_estacion_id": exit_df["destino_estacion_id"].astype(str).replace({"nan": None, "<NA>": None}),
    "fecha_hora_salida": pd.to_datetime(exit_df["fecha_hora_salida"]),
    "monto_viaje": df_mr_raw["fare_gtq"],
    "duracion_segundos": df_mr_raw["duration_s"],
    "ingesta_timestamp": pd.Timestamp.now()
})

df_mr.to_sql("metroriel_viajes", engine, schema="bronze", if_exists="replace", index=False)

print("5. Cargando CDC Padrón...")
df_cdc = pd.read_csv("data/raw/cdc_padron_usuarios.csv")
df_cdc["ingesta_timestamp"] = pd.Timestamp.now()
df_cdc.to_sql("cdc_padron_usuarios", engine, schema="bronze", if_exists="replace", index=False)

print("¡Todas las tablas base en esquema bronze han sido creadas con éxito!")