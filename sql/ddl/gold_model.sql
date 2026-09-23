-- DDL de referencia del modelo Gold. dbt materializa estas tablas en ejecución.
-- Ejecutar manualmente solo sobre un esquema Gold vacío si se requiere el DDL físico.
CREATE SCHEMA IF NOT EXISTS gold;
CREATE EXTENSION IF NOT EXISTS pgcrypto;

CREATE TABLE gold.dim_usuario (
    usuario_sk text PRIMARY KEY,
    modos_observados integer NOT NULL,
    metodo_identidad text NOT NULL
);

CREATE TABLE gold.dim_tiempo (
    tiempo_sk bigint PRIMARY KEY,
    fecha_hora timestamp NOT NULL,
    fecha date NOT NULL,
    anio integer NOT NULL,
    mes integer NOT NULL,
    dia integer NOT NULL,
    dia_semana_iso integer NOT NULL,
    hora integer NOT NULL,
    minuto integer NOT NULL,
    segundo integer NOT NULL,
    es_dia_habil boolean NOT NULL,
    es_hora_pico boolean NOT NULL
);

CREATE TABLE gold.dim_zona (
    zona_sk text PRIMARY KEY,
    nombre_zona text NOT NULL
);

CREATE TABLE gold.dim_modo (
    modo_sk text PRIMARY KEY,
    nombre_modo text NOT NULL
);

CREATE TABLE gold.dim_servicio (
    servicio_sk text PRIMARY KEY,
    modo_sk text NOT NULL REFERENCES gold.dim_modo(modo_sk),
    modo text NOT NULL,
    codigo_servicio text NOT NULL,
    tipo_servicio text NOT NULL
);

CREATE TABLE gold.dim_punto_transporte (
    punto_sk text PRIMARY KEY,
    modo_sk text NOT NULL REFERENCES gold.dim_modo(modo_sk),
    zona_sk text NOT NULL REFERENCES gold.dim_zona(zona_sk),
    codigo_punto text NOT NULL,
    nombre_punto text,
    modo text NOT NULL,
    zona_conformada text NOT NULL,
    servicio_codigo text,
    latitud numeric,
    longitud numeric,
    UNIQUE (modo, codigo_punto)
);

CREATE TABLE gold.fact_abordajes (
    abordaje_sk text PRIMARY KEY,
    usuario_sk text NOT NULL REFERENCES gold.dim_usuario(usuario_sk),
    tiempo_sk bigint NOT NULL REFERENCES gold.dim_tiempo(tiempo_sk),
    zona_sk text NOT NULL REFERENCES gold.dim_zona(zona_sk),
    punto_sk text NOT NULL REFERENCES gold.dim_punto_transporte(punto_sk),
    modo_sk text NOT NULL REFERENCES gold.dim_modo(modo_sk),
    servicio_sk text NOT NULL REFERENCES gold.dim_servicio(servicio_sk),
    fuente_evento text NOT NULL,
    cantidad_abordajes integer NOT NULL CHECK (cantidad_abordajes = 1),
    tarifa_quetzales numeric NOT NULL
);

CREATE TABLE gold.fact_viajes_metroriel (
    viaje_sk text PRIMARY KEY,
    usuario_sk text NOT NULL REFERENCES gold.dim_usuario(usuario_sk),
    tiempo_ingreso_sk bigint NOT NULL REFERENCES gold.dim_tiempo(tiempo_sk),
    tiempo_salida_sk bigint NOT NULL REFERENCES gold.dim_tiempo(tiempo_sk),
    zona_origen_sk text NOT NULL REFERENCES gold.dim_zona(zona_sk),
    zona_destino_sk text NOT NULL REFERENCES gold.dim_zona(zona_sk),
    punto_origen_sk text NOT NULL REFERENCES gold.dim_punto_transporte(punto_sk),
    punto_destino_sk text NOT NULL REFERENCES gold.dim_punto_transporte(punto_sk),
    modo_sk text NOT NULL REFERENCES gold.dim_modo(modo_sk),
    servicio_sk text NOT NULL REFERENCES gold.dim_servicio(servicio_sk),
    fuente_evento text NOT NULL,
    cantidad_viajes integer NOT NULL CHECK (cantidad_viajes = 1),
    tarifa_quetzales numeric NOT NULL,
    duracion_minutos numeric
);

CREATE INDEX fact_abordajes_tiempo_idx ON gold.fact_abordajes(tiempo_sk);
CREATE INDEX fact_abordajes_zona_modo_idx ON gold.fact_abordajes(zona_sk, modo_sk);
CREATE INDEX fact_viajes_origen_idx ON gold.fact_viajes_metroriel(zona_origen_sk, tiempo_ingreso_sk);
