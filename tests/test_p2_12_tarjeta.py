"""Ejecuta el SQL real del requisito 1.2 en SQLite en memoria.

Sólo adapta casts, literales timestamp e intervalos PostgreSQL. No replica la
lógica de selección/etiqueta en Python ni conecta servicios externos.
"""
import csv
import hashlib
import importlib.util
import json
import re
import sqlite3
import tempfile
import unittest
from datetime import datetime
from pathlib import Path

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
MODELS = ROOT / "dbt/red_metropolitana/models/silver/p2_12"
NAMES = ("silver_p2_usos_tarjeta", "silver_p2_poblacion_tarjeta", "silver_p2_costo_tarjeta")
SPEC = importlib.util.spec_from_file_location("p2_12_evidence", ROOT / "scripts/generar_evidencia_p2_12.py")
REPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(REPORT)


def model_sql(name):
    env = Environment()
    env.globals.update(ref=lambda name: name, config=lambda **kwargs: "")
    macro = env.from_string((ROOT / "dbt/red_metropolitana/macros/p2_12_cortes.sql").read_text(encoding="utf-8")).module
    env.globals["p2_12_cortes"] = macro.p2_12_cortes
    sql = env.from_string((MODELS / f"{name}.sql").read_text(encoding="utf-8")).render()
    sql = re.sub(r"\btimestamp\s+'([^']+)'", r"'\1'", sql, flags=re.IGNORECASE)
    sql = re.sub(r"::(?:text|timestamp|integer|bigint|numeric)\b", "", sql)
    return re.sub(r"(\w+\.fecha_corte)\s*([+-])\s*interval '(\d+) days'",
                  lambda m: f"datetime({m[1]}, '{m[2]}{m[3]} days')", sql)


class TarjetaTest(unittest.TestCase):
    def setUp(self):
        self.db = sqlite3.connect(":memory:")
        self.db.row_factory = sqlite3.Row
        self.db.create_function("md5", 1, lambda value: hashlib.md5(value.encode()).hexdigest())
        self.addCleanup(self.db.close)
        self.db.executescript("""
            create table silver_transmetro_validaciones(tarjeta_id text, fecha_hora text, bronze_record_id text);
            create table silver_transurbano_transacciones(id_tarjeta text, fecha_hora text, bronze_record_id text);
            create table silver_aerometro_boardings(user_hash text, fecha_hora text, bronze_record_id text);
            create table silver_metroriel_viajes(tarjeta_mr text, fecha_hora_ingreso text, fecha_hora_salida text, bronze_record_id text);
            create table silver_cuarentena(fuente text, id_registro_crudo text);
            create table silver_padron_transmetro_scd2(tarjeta_id text, valid_from text, operacion text);
            create table bridge_identidad_usuario(sistema_origen text, llave_origen text, usuario_canonico_id text, metodo_match text);
        """)
        self.event_number = 0

    def event(self, operator, key, timestamp, *, close=None, quarantine=False):
        self.event_number += 1
        eid = f"fixture-{self.event_number}"
        if operator == "MetroRiel":
            self.db.execute("insert into silver_metroriel_viajes values (?,?,?,?)", (key, timestamp, close, eid))
        else:
            table = {"Transmetro": "silver_transmetro_validaciones", "Transurbano": "silver_transurbano_transacciones",
                     "Aerometro": "silver_aerometro_boardings"}[operator]
            self.db.execute(f"insert into {table} values (?,?,?)", (key, timestamp, eid))
        if quarantine:
            self.db.execute("insert into silver_cuarentena values (?,?)", (operator, eid))
        return eid

    def prior(self, operator="Transmetro", key="TC-fixture"):
        self.event(operator, key, "2026-06-15 08:00:00", close="2026-06-15 08:40:00")
        self.event(operator, key, "2026-06-20 08:00:00", close="2026-06-20 08:40:00")

    def cdc(self, key, when, op="DELETE"):
        self.db.execute("insert into silver_padron_transmetro_scd2 values (?,?,?)", (key, when, op))

    def identity(self, operator, key, canonical="USR-fixture", method="PATRON_NUMERICO_INFERIDO"):
        self.db.execute("insert into bridge_identidad_usuario values (?,?,?,?)", (operator, key, canonical, method))

    def build(self):
        for name in reversed(NAMES):
            self.db.execute(f"drop {'view' if name == NAMES[0] else 'table'} if exists {name}")
        for name in NAMES:
            self.db.execute(f"create {'view' if name == NAMES[0] else 'table'} {name} as " + model_sql(name))

    def population(self, cut="A"):
        return [dict(r) for r in self.db.execute("select * from silver_p2_poblacion_tarjeta where corte=? order by operador,llave_operacional", (cut,))]

    def cost(self, cut="A"):
        return dict(self.db.execute("select * from silver_p2_costo_tarjeta where corte=?", (cut,)).fetchone())

    def test_exactamente_dos_usos_previos_entra_y_sin_futuro_es_positivo(self):
        self.prior()
        self.build()
        row, = self.population()
        self.assertEqual((row["eventos_previos_28d"], row["eventos_futuros_30d"], row["etiqueta"]), (2, 0, 1))
        self.assertEqual((row["operador"], row["llave_operacional"]), ("Transmetro", "TC-fixture"))

    def test_un_uso_previo_queda_fuera(self):
        self.event("Transmetro", "TC-fixture", "2026-06-15 08:00:00")
        self.build()
        self.assertEqual(self.population(), [])

    def test_evento_exactamente_en_corte_no_es_previo_y_si_es_futuro(self):
        self.prior()
        self.event("Transmetro", "TC-fixture", "2026-07-01 00:00:00")
        self.event("Transmetro", "TC-solo-uno", "2026-06-20 08:00:00")
        self.event("Transmetro", "TC-solo-uno", "2026-07-01 00:00:00")
        self.build()
        row, = self.population()
        self.assertEqual((row["eventos_previos_28d"], row["eventos_futuros_30d"], row["etiqueta"]), (2, 1, 0))

    def test_uso_en_ventana_futura_etiqueta_cero(self):
        self.prior()
        self.event("Transmetro", "TC-fixture", "2026-07-30 23:59:59")
        self.build()
        self.assertEqual(self.population()[0]["etiqueta"], 0)

    def test_limite_superior_futuro_exclusivo(self):
        self.prior()
        self.event("Transmetro", "TC-fixture", "2026-07-31 00:00:00")
        self.build()
        self.assertEqual(self.population()[0]["etiqueta"], 1)

    def test_limite_inferior_previo_inclusivo_y_anterior_fuera(self):
        self.event("Transmetro", "incluida", "2026-06-03 00:00:00")
        self.event("Transmetro", "incluida", "2026-06-20 08:00:00")
        self.event("Transmetro", "excluida", "2026-06-02 23:59:59")
        self.event("Transmetro", "excluida", "2026-06-20 08:00:00")
        self.build()
        self.assertEqual([r["llave_operacional"] for r in self.population()], ["incluida"])

    def test_cualquier_delete_previo_excluye_aunque_haya_reactivacion(self):
        self.prior()
        self.cdc("TC-fixture", "2026-06-10 08:00:00")
        self.cdc("TC-fixture", "2026-06-11 08:00:00", "INSERT")
        self.build()
        self.assertEqual(self.population(), [])

    def test_delete_exacto_en_corte_o_futuro_no_excluye(self):
        self.prior(key="exacto")
        self.prior(key="futuro")
        self.cdc("exacto", "2026-07-01 00:00:00")
        self.cdc("futuro", "2026-07-15 08:00:00")
        self.build()
        self.assertEqual(len(self.population()), 2)

    def test_cdc_transmetro_no_se_aplica_a_otros_operadores(self):
        self.prior("Transurbano", "misma-llave")
        self.cdc("misma-llave", "2026-06-10 08:00:00")
        self.build()
        self.assertEqual(len(self.population()), 1)

    def test_cuarentena_no_cuenta_en_previos_ni_futuros(self):
        self.event("Transmetro", "sin-poblacion", "2026-06-15 08:00:00")
        self.event("Transmetro", "sin-poblacion", "2026-06-20 08:00:00", quarantine=True)
        self.prior(key="positivo")
        self.event("Transmetro", "positivo", "2026-07-10 08:00:00", quarantine=True)
        self.build()
        row, = self.population()
        self.assertEqual((row["llave_operacional"], row["etiqueta"]), ("positivo", 1))

    def test_metroriel_un_viaje_cerrado_es_un_solo_uso(self):
        self.prior("MetroRiel", "MR-fixture")
        self.event("MetroRiel", "MR-fixture", "2026-07-15 08:00:00", close="2026-07-15 08:45:00")
        self.build()
        row, = self.population()
        self.assertEqual((row["eventos_previos_28d"], row["eventos_futuros_30d"], row["etiqueta"]), (2, 1, 0))

    def test_metroriel_cierre_en_corte_no_se_filtra_hacia_atras(self):
        self.event("MetroRiel", "MR-fixture", "2026-06-15 08:00:00", close="2026-06-15 08:40:00")
        self.event("MetroRiel", "MR-fixture", "2026-06-30 23:30:00", close="2026-07-01 00:00:00")
        self.build()
        self.assertEqual(self.population(), [])

    def test_metroriel_cierre_posterior_al_horizonte_no_etiqueta_con_futuro_extra(self):
        self.prior("MetroRiel", "MR-fixture")
        self.event("MetroRiel", "MR-fixture", "2026-07-30 23:50:00", close="2026-07-31 00:20:00")
        self.build()
        self.assertEqual(self.population()[0]["etiqueta"], 1)

    def test_costo_otra_tarjeta_operador_aunque_no_entre_en_poblacion(self):
        self.prior("Transurbano", "TU-fixture")
        self.identity("Transurbano", "TU-fixture")
        self.identity("Transmetro", "TM-otra")
        self.event("Transmetro", "TM-otra", "2026-07-10 08:00:00")
        self.event("Transmetro", "TM-otra", "2026-07-11 08:00:00")
        self.build()
        self.assertEqual(len(self.population()), 1)
        self.assertEqual((self.cost()["positivos"], self.cost()["positivos_con_actividad_otro_operador"], self.cost()["proporcion_costo"]), (1, 1, 1))

    def test_otro_operador_con_uso_cuarentenado_no_es_costo(self):
        self.prior()
        self.identity("Transmetro", "TC-fixture")
        self.identity("Transurbano", "TU-otra")
        self.event("Transurbano", "TU-otra", "2026-07-10 08:00:00", quarantine=True)
        self.build()
        self.assertEqual(self.cost()["positivos_con_actividad_otro_operador"], 0)

    def test_otra_tarjeta_mismo_operador_no_es_costo_cruzado(self):
        self.prior()
        self.identity("Transmetro", "TC-fixture")
        self.identity("Transmetro", "TC-otra")
        self.event("Transmetro", "TC-otra", "2026-07-10 08:00:00")
        self.build()
        self.assertEqual(self.cost()["positivos_con_actividad_otro_operador"], 0)

    def test_aerometro_aislado_sin_equivalencia_numerica(self):
        self.prior("Aerometro", "123")
        self.identity("Aerometro", "123", "AM-123", "HASH_AISLADO")
        self.identity("Transmetro", "TC-123", "USR-123")
        self.event("Transmetro", "TC-123", "2026-07-10 08:00:00")
        self.build()
        self.assertEqual((self.cost()["positivos_aerometro"], self.cost()["positivos_con_actividad_otro_operador"]), (1, 0))

    def test_unidad_no_depende_de_identidad_y_separa_operadores(self):
        self.prior("Transmetro", "misma")
        self.prior("Transurbano", "misma")
        self.identity("Transmetro", "misma")
        self.identity("Transurbano", "misma")
        self.build()
        rows = self.population()
        self.assertEqual(len({r["unidad_id"] for r in rows}), 2)
        self.assertEqual({r["llave_operacional"] for r in rows}, {"misma"})

    def test_futuro_no_cambia_la_poblacion(self):
        self.prior()
        self.build()
        before = self.population()
        self.event("Transmetro", "TC-fixture", "2026-07-10 08:00:00")
        self.cdc("TC-fixture", "2026-07-15 08:00:00")
        self.build()
        after = self.population()
        self.assertEqual([(r["unidad_id"], r["eventos_previos_28d"]) for r in before],
                         [(r["unidad_id"], r["eventos_previos_28d"]) for r in after])
        self.assertEqual((before[0]["etiqueta"], after[0]["etiqueta"]), (1, 0))

    def test_b_ventanas_independientes_y_sin_denominador_no_inventa_tasa(self):
        self.event("Transurbano", "B", "2026-07-03 00:00:00")
        self.event("Transurbano", "B", "2026-07-30 23:59:59")
        self.event("Transurbano", "B", "2026-07-31 00:00:00")
        self.build()
        self.assertEqual(self.population(), [])
        self.assertEqual((self.population("B")[0]["eventos_previos_28d"], self.population("B")[0]["etiqueta"]), (2, 0))
        self.assertIsNone(self.cost()["tasa_positiva"])
        self.assertIsNone(self.cost("B")["proporcion_costo"])


class EvidenciaTest(unittest.TestCase):
    def test_markdown_csv_json_con_cuentas_completas_y_sin_sobrescritura_implicita(self):
        evidence = {"verificado_en": "fixture", "politica_cdc": "DELETE previo", "metroriel": "Un uso por viaje cerrado",
                    "limitacion_identidad": "Patrón inferido; Aerómetro aislado",
                    "verificacion": {"diferencias_recalculo": 0, "diferencias_costo": 0, "cobertura_diaria_28_y_30_dias": True},
                    "resultados": [{"corte": "A", "fecha_corte": datetime(2026, 7, 1), "poblacion": 10,
                        "positivos": 3, "tasa_positiva": 0.3, "positivos_con_actividad_otro_operador": 1,
                        "proporcion_costo": 1/3, "positivos_aerometro": 1}], "por_operador": [], "cobertura": []}
        temporary_root = ROOT / "dbt/red_metropolitana/target"
        temporary_root.mkdir(parents=True, exist_ok=True)
        with tempfile.TemporaryDirectory(dir=temporary_root) as tmp:
            paths = [Path(tmp) / f"fixture.{ext}" for ext in ("md", "csv", "json")]
            REPORT.write_evidence(evidence, paths, overwrite=False)
            self.assertIn("3 / 10", paths[0].read_text(encoding="utf-8"))
            self.assertIn("1 / 3", paths[0].read_text(encoding="utf-8"))
            with paths[1].open(encoding="utf-8", newline="") as file:
                row, = csv.DictReader(file)
            self.assertEqual((row["positivos_poblacion"], row["costo_positivos"]), ("3 / 10", "1 / 3"))
            self.assertEqual(json.loads(paths[2].read_text(encoding="utf-8"))["resultados"][0]["poblacion"], 10)
            with self.assertRaises(FileExistsError):
                REPORT.write_evidence(evidence, paths, overwrite=False)


if __name__ == "__main__":
    unittest.main()
