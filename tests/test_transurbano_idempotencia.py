"""Regresión de IDs TU empatados: SQLite en memoria, sin PostgreSQL/Kafka/Docker.

Ejecuta el ORDER BY real del row_number del modelo sobre entradas ya parseadas.
Dos órdenes físicos del mismo multiconjunto reproducen la diferencia histórica;
el desempate debe conservar la asociación ID/linaje y el fingerprint completo.
"""
import hashlib
import itertools
import json
import re
import sqlite3
import unittest
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
MODEL = ROOT / "dbt/red_metropolitana/models/silver/silver_transurbano_transacciones.sql"
LEGACY_ORDER = "fecha_valida, hora_raw, id_tarjeta"
# Dos registros con igual fecha/hora/tarjeta y distinto linaje. Incluso con los
# mismos atributos de negocio, intercambiar TU-1/TU-2 cambia las filas completas.
PEERS = (
    ("2026-09-01", "08:00:00", "fixture-card", "P1", "R1", 2, "fixture-hash:2", "2026-10-28T08:00:00-06:00"),
    ("2026-09-01", "08:00:00", "fixture-card", "P1", "R1", 2, "fixture-hash:1", "2026-10-28T08:00:00-06:00"),
    ("2026-09-01", "08:00:00", "fixture-card", "P2", "R2", 3, "fixture-hash:3", "2026-10-28T08:00:00-06:00"),
)


def model_order():
    sql = MODEL.read_text(encoding="utf-8")
    match = re.search(r"row_number\(\)\s+over\s*\(\s*order\s+by\s+(.*?)\)", sql, re.IGNORECASE | re.DOTALL)
    if not match:
        raise AssertionError("No se encontró el orden del row_number del modelo")
    return match.group(1)


def evaluate(order_by, input_rows):
    with sqlite3.connect(":memory:") as connection:
        connection.row_factory = sqlite3.Row
        connection.execute("""CREATE TABLE parsed_dates (
            fecha_valida TEXT, hora_raw TEXT, id_tarjeta TEXT, cod_parada TEXT,
            ruta TEXT, tarifa_quetzales NUMERIC, bronze_record_id TEXT, ingesta_timestamp TEXT
        )""")
        connection.executemany("INSERT INTO parsed_dates VALUES (?, ?, ?, ?, ?, ?, ?, ?)", input_rows)
        # Misma ventana y posición de los filtros que en el modelo. Las fechas
        # del fixture ya están parseadas; aquí no se prueba normalización PG.
        result = connection.execute(f"""WITH transurbano_base AS (
            SELECT 'TU-' || row_number() OVER (ORDER BY {order_by}) AS id_transaccion,
                id_tarjeta, fecha_valida || ' ' || hora_raw AS fecha_hora,
                cod_parada, ruta, tarifa_quetzales, bronze_record_id, ingesta_timestamp
            FROM parsed_dates WHERE fecha_valida IS NOT NULL
        ) SELECT * FROM transurbano_base
          WHERE cod_parada IS NOT NULL AND trim(cod_parada) <> ''
            AND fecha_hora <= '2026-10-01 00:00:00'
        """)
        return [dict(row) for row in result]


def fingerprint(rows):
    # Multiconjunto independiente del orden físico, con TODOS los campos.
    # No pretende reproducir el formato textual JSONB de PostgreSQL, sólo la
    # propiedad que verifica el pipeline: detectar cambios de contenido por fila.
    row_hashes = sorted(hashlib.md5(json.dumps(row, sort_keys=True).encode()).hexdigest() for row in rows)
    return hashlib.md5("".join(row_hashes).encode()).hexdigest()


class TransurbanoIdempotenciaTest(unittest.TestCase):
    def test_orden_anterior_reproduce_mismo_conteo_distinto_id_y_fingerprint(self):
        first = evaluate(LEGACY_ORDER, PEERS)
        second = evaluate(LEGACY_ORDER, reversed(PEERS))
        self.assertEqual(len(first), len(second))
        self.assertNotEqual(fingerprint(first), fingerprint(second))
        # Al alinear por linaje, la única columna cambiante es id_transaccion.
        indexed = [{row["bronze_record_id"]: row for row in rows} for rows in (first, second)]
        changed = {column for key in indexed[0] for column in indexed[0][key]
                   if indexed[0][key][column] != indexed[1][key][column]}
        self.assertEqual(changed, {"id_transaccion"})
        self.assertEqual(fingerprint([{k: v for k, v in row.items() if k != "id_transaccion"} for row in first]),
                         fingerprint([{k: v for k, v in row.items() if k != "id_transaccion"} for row in second]))

    def test_modelo_corregido_conserva_id_linaje_y_fingerprint_en_todas_las_permutaciones(self):
        reference = evaluate(model_order(), PEERS)
        expected_ids = {"fixture-hash:1": "TU-1", "fixture-hash:2": "TU-2", "fixture-hash:3": "TU-3"}
        for input_rows in itertools.permutations(PEERS):
            with self.subTest(order=[row[6] for row in input_rows]):
                result = evaluate(model_order(), input_rows)
                self.assertEqual(len(result), len(PEERS))
                self.assertEqual({row["bronze_record_id"]: row["id_transaccion"] for row in result}, expected_ids)
                self.assertEqual(fingerprint(result), fingerprint(reference))

    def test_conserva_prefijo_grano_y_orden_previo_entre_transacciones_sin_empate(self):
        earlier = ("2026-08-31", *PEERS[0][1:6], "fixture-hash:9", PEERS[0][7])
        later = ("2026-09-02", *PEERS[0][1:6], "fixture-hash:0", PEERS[0][7])
        rows = (later, PEERS[0], earlier)
        legacy = evaluate(LEGACY_ORDER, rows)
        fixed = evaluate(model_order(), rows)
        self.assertEqual(fingerprint(legacy), fingerprint(fixed))
        self.assertEqual({row["bronze_record_id"]: row["id_transaccion"] for row in fixed},
                         {"fixture-hash:9": "TU-1", "fixture-hash:2": "TU-2", "fixture-hash:0": "TU-3"})


if __name__ == "__main__":
    unittest.main()
