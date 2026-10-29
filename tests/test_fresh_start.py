"""Fresh-start sólo contra fixtures temporales; Docker/Kafka/SQL siempre simulados."""
import copy
import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import pyarrow as pa
import pyarrow.parquet as pq

from test_fase1_pipeline import PIPELINE, TEMP_ROOT, run_fixture


class FreshStartTest(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name).resolve()
        self.assertTrue(self.root.is_relative_to(TEMP_ROOT.resolve()))
        for name, value in {"ROOT": self.root, "RAW": self.root / "data/raw",
                            "EVIDENCE": self.root / "docs/evidencias"}.items():
            self.start_patch(patch.object(PIPELINE, name, value))
        # Cualquier proceso o conexión real es un fallo del test.
        self.process = self.start_patch(patch.object(PIPELINE.subprocess, "run",
            side_effect=AssertionError("El test no debe ejecutar procesos externos")))
        self.start_patch(patch.object(PIPELINE, "AdminClient",
            side_effect=AssertionError("El test no debe conectar Kafka")))
        self.start_patch(patch.object(PIPELINE, "postgres_engine",
            side_effect=AssertionError("El test no debe conectar PostgreSQL")))
        self.raw = self.root / "data/raw"
        self.raw.mkdir(parents=True)
        (self.raw / ".gitkeep").touch()
        for name, spec in PIPELINE.EXPECTED.items():
            content = (",".join(spec["columns"]) + "\n" + ",".join("x" for _ in spec["columns"]) + "\n"
                       if spec["type"] == "csv" else json.dumps(dict.fromkeys(spec["keys"])))
            (self.raw / name).write_text(content, encoding="utf-8")
        self.environment = {"POSTGRES_DB": "fixture", "POSTGRES_USER": "fixture_user",
                            "POSTGRES_PASSWORD": "fixture-private", "POSTGRES_HOST": "localhost",
                            "POSTGRES_PORT": "5432", "GOLD_PSEUDONYM_KEY": "x" * 64}

    def start_patch(self, patcher):
        value = patcher.start()
        self.addCleanup(patcher.stop)
        return value

    def write(self, relative, content="fixture"):
        path = self.root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
        return path

    def config(self):
        return {"name": "fixture", "services": {
            "postgres": {"environment": {name: self.environment[name] for name in
                ("POSTGRES_DB", "POSTGRES_USER", "POSTGRES_PASSWORD")},
                "ports": [{"target": 5432, "published": "5432"}], "volumes": [
                    {"type": "volume", "source": "postgres_data", "target": "/var/lib/postgresql/data"},
                    {"type": "bind", "source": str(self.root / "sql/init"),
                     "target": "/docker-entrypoint-initdb.d", "read_only": True}]},
            "kafka": {}}, "volumes": {"postgres_data": {"name": "fixture_postgres_data"}}}

    def preparation(self):
        return {"duracion_total_segundos": 0.1, "etapas": {"validar_raw": PIPELINE.validate_fresh_raw()}}

    def new_run(self):
        run = run_fixture()
        run["metricas"]["silver"] = dict(zip(
            ("silver_transmetro_validaciones", "silver_transurbano_transacciones",
             "silver_aerometro_boardings", "silver_metroriel_viajes"), (2, 3, 4, 5)))
        run["metricas"]["gold"].update(fact_abordajes=9, fact_viajes_metroriel=5)
        run["metricas"]["gold_abordajes_por_modo"] = {"Transmetro": 2, "Transurbano": 3, "Aerometro": 4}
        inventory = PIPELINE.validate_fresh_raw()["archivos"]
        run["metricas"]["raw_sha256"] = {name: item["sha256"] for name, item in inventory.items()}
        run["metricas"]["bronze"] = {Path(name).stem: {"filas": item["filas"]}
                                       for name, item in inventory.items()}
        return run

    def test_tabla_generica_diferencia_cero_faltantes_y_sobrantes(self):
        for loaded, difference in ((10, 0), (7, -3), (12, 2), (0, -10)):
            with self.subTest(loaded=loaded):
                rows = PIPELINE.load_count_table({"otra_fuente.csv": 10}, {"otra_fuente": {"filas": loaded}})
                self.assertEqual(rows, [{"archivo": "otra_fuente.csv", "filas_esperadas": 10,
                                         "filas_cargadas": loaded, "diferencia": difference}])
                self.assertEqual(list(rows[0]), ["archivo", "filas_esperadas", "filas_cargadas", "diferencia"])

    def test_nueve_conteos_oficiales_p2_no_reemplazan_contrato_p1(self):
        official = {"aerometro_boardings.csv": 387053, "am_estaciones.csv": 14,
                    "cdc_padron_usuarios.csv": 77636, "metroriel_viajes.jsonl": 590844,
                    "mr_estaciones.csv": 22, "tm_estaciones.csv": 104,
                    "transmetro_validaciones.csv": 713786, "transurbano_transacciones.csv": 1635788,
                    "tu_paradas.csv": 328}
        self.assertEqual(PIPELINE.PROJECT2_EXPECTED_ROWS, official)
        bronze = {Path(name).stem: {"filas": count} for name, count in official.items()}
        evidence = PIPELINE.project2_load_evidence({"metricas": {"bronze": bronze}}, {})
        self.assertEqual(evidence["estado"], "OK")
        self.assertEqual(len(evidence["tabla"]), 9)
        self.assertEqual({row["archivo"] for row in evidence["tabla"]}, set(official))
        self.assertTrue(all(row["diferencia"] == 0 for row in evidence["tabla"]))
        self.assertEqual(set(bronze), set(PIPELINE.SOURCES))
        self.assertEqual(PIPELINE.EXPECTED["aerometro_boardings.csv"]["expected_rows"], 203554)

    def test_faltantes_y_sobrantes_se_reportan_sin_sustituir_bronze_por_raw(self):
        bronze = {Path(name).stem: {"filas": count} for name, count in PIPELINE.PROJECT2_EXPECTED_ROWS.items()}
        bronze["transmetro_validaciones"]["filas"] -= 5
        bronze["metroriel_viajes"]["filas"] += 3
        raw = {name: {"filas": count} for name, count in PIPELINE.PROJECT2_EXPECTED_ROWS.items()}
        evidence = PIPELINE.project2_load_evidence({"metricas": {"bronze": bronze}}, raw)
        rows = {row["archivo"]: row for row in evidence["tabla"]}
        self.assertEqual(rows["transmetro_validaciones.csv"]["diferencia"], -5)
        self.assertEqual(rows["metroriel_viajes.jsonl"]["diferencia"], 3)
        self.assertEqual(evidence["conteos_raw"]["transmetro_validaciones.csv"], 713786)
        self.assertEqual(evidence["estado"], "CON_DIFERENCIAS")
        content = "\n".join(PIPELINE.render_load_evidence(evidence))
        self.assertIn("requieren explicación", content)
        self.assertIn("-5 filas", content)
        self.assertIn("+3 filas", content)
        self.assertIn("| archivo | filas_esperadas | filas_cargadas | diferencia |", content)
        self.assertIn("| archivo | filas_raw |", content)
        with patch("sys.stderr") as stderr:
            PIPELINE.write_load_evidence("p2-desvios", 1, evidence)
            self.assertIn("diferencia=-5", "".join(c.args[0] for c in stderr.write.call_args_list))

    def test_conteo_bronze_no_disponible_no_se_inventa_como_cero(self):
        with self.assertRaises(KeyError):
            PIPELINE.load_count_table({"fuente.csv": 10}, {})

    def test_filas_cargadas_suman_parquet_reales_de_las_nueve_fuentes(self):
        bronze = self.root / "data/bronze"
        for source in PIPELINE.SOURCES:
            directory = bronze / source / "fecha_ingesta=2026-10-28"
            directory.mkdir(parents=True)
            for name, ids in (("part-1.parquet", [1, 2]), ("part-2.parquet", [3, 4, 5])):
                pq.write_table(pa.table({"id": ids}), directory / name)
        engine = MagicMock()
        with patch.object(PIPELINE, "BRONZE", bronze), \
             patch.object(PIPELINE, "postgres_engine", return_value=engine), \
             patch.object(PIPELINE, "table_counts", return_value={}), \
             patch.object(PIPELINE, "relation_fingerprints", return_value={}):
            metrics = PIPELINE.collect_metrics.fn()
        raw = PIPELINE.validate_fresh_raw()["archivos"]  # Una fila Raw por fuente en este fixture.
        evidence = PIPELINE.project2_load_evidence({"metricas": metrics}, raw)
        self.assertTrue(all(row["filas_cargadas"] == 5 for row in evidence["tabla"]))
        self.assertTrue(all(count == 1 for count in evidence["conteos_raw"].values()))
        self.assertTrue(all(item["archivos"] == 2 and sorted(item["filas_por_parquet"].values()) == [2, 3]
                            for item in metrics["bronze"].values()))

    def test_nueve_fuentes_nuevas_sin_conteos_fijos_y_sin_modificar_raw(self):
        before = {p.name: p.read_bytes() for p in self.raw.iterdir()}
        result = PIPELINE.validate_fresh_raw()
        self.assertEqual(len(result["archivos"]), 9)
        self.assertTrue(all(item["filas"] == 1 for item in result["archivos"].values()))
        self.assertEqual(before, {p.name: p.read_bytes() for p in self.raw.iterdir()})

    def test_raw_invalido_aborta_antes_de_procesos_y_limpieza(self):
        source = self.raw / "tm_estaciones.csv"
        original = source.read_bytes()
        marker = self.write("data/bronze/_control/streaming_state.sqlite")
        for case in ("missing", "extra", "header", "empty", "directory", "jsonl"):
            with self.subTest(case=case):
                if case == "missing":
                    source.unlink()
                elif case == "extra":
                    (self.raw / "extra.csv").touch()
                elif case == "header":
                    source.write_text("incorrecto\n1\n", encoding="utf-8")
                elif case == "empty":
                    source.write_text(",".join(PIPELINE.EXPECTED[source.name]["columns"]) + "\n", encoding="utf-8")
                elif case == "directory":
                    (self.raw / "subcarpeta").mkdir()
                else:
                    (self.raw / "metroriel_viajes.jsonl").write_text("no es JSON", encoding="utf-8")
                with patch.object(PIPELINE, "clean_generated_files") as clean:
                    with self.assertRaises(RuntimeError):
                        PIPELINE.prepare_fresh_start()
                    clean.assert_not_called()
                self.process.assert_not_called()
                self.assertTrue(marker.exists())
                source.write_bytes(original)
                (self.raw / "extra.csv").unlink(missing_ok=True)
                if (self.raw / "subcarpeta").exists():
                    (self.raw / "subcarpeta").rmdir()

    def test_limpia_solo_generados_incluyendo_sqlite_manifiestos_y_cache_dbt(self):
        generated = [self.write(relative) for relative in (
            "data/bronze/_control/streaming_state.sqlite", "data/bronze/_control/streaming_state.sqlite-wal",
            "data/bronze/_control/streaming_state.sqlite-shm", "data/bronze/_control/batch_manifest.json",
            "data/bronze/_control/cdc_manifest.json", "data/bronze/tm_estaciones/part.parquet",
            "data/quarantine/invalid.csv", "dbt/red_metropolitana/target/partial_parse.msgpack",
            "dbt/red_metropolitana/target/revision_fase2_estado.json", "dbt/red_metropolitana/logs/dbt.log")]
        preserved = [self.write(relative) for relative in (
            "data/bronze/.gitkeep", "data/quarantine/.gitkeep", "docs/evidencias/historica.json",
            "docs/metricas/historica.md", "README.md", "ingestion/fuente.py", ".env",
            "dbt/red_metropolitana/snapshots/fuente.sql")]
        preserved += list(self.raw.iterdir())
        before = {p: p.read_bytes() for p in preserved}
        with patch.object(PIPELINE, "run_command", return_value=({}, "data/bronze/.gitkeep\0")):
            plan = PIPELINE.cleanup_plan()
        self.assertEqual(set(plan), set(generated))
        result = PIPELINE.clean_generated_files(plan)
        self.assertEqual(sum(result["archivos_eliminados"].values()), len(generated))
        self.assertTrue(all(not p.exists() for p in generated))
        self.assertEqual(before, {p: p.read_bytes() for p in preserved})
        # Volver a limpiar un entorno vacío también es válido.
        with patch.object(PIPELINE, "run_command", return_value=({}, "")):
            self.assertEqual(PIPELINE.cleanup_plan(), [])

    def test_archivo_versionado_en_ruta_generada_aborta_y_se_conserva(self):
        source = self.write("data/quarantine/documento.md")
        with patch.object(PIPELINE, "run_command", return_value=({}, "data/quarantine/documento.md\0")):
            with self.assertRaisesRegex(RuntimeError, "versionado"):
                PIPELINE.cleanup_plan()
        self.assertTrue(source.exists())

    def test_codigo_o_documentacion_no_versionados_en_datos_se_conservan(self):
        for name in ("nota.md", "fuente.py", "evidencia.pdf"):
            path = self.write("data/quarantine/" + name)
            with self.subTest(name=name), patch.object(PIPELINE, "run_command", return_value=({}, "")):
                with self.assertRaisesRegex(RuntimeError, "no reconocido"):
                    PIPELINE.cleanup_plan()
                self.assertTrue(path.exists())
            path.unlink()

    def test_plan_inyectado_no_puede_borrar_raw_fuentes_o_placeholder(self):
        generated = self.write("data/bronze/part.parquet")
        for path in (self.raw / "tm_estaciones.csv", self.write("fuente.py"), self.write("data/bronze/.gitkeep")):
            with self.subTest(path=path), self.assertRaises(RuntimeError):
                PIPELINE.clean_generated_files([generated, path])
            self.assertTrue(generated.exists() and path.exists())

    def test_junction_en_carpeta_generada_se_rechaza(self):
        directory = self.root / "data/bronze"
        directory.mkdir()
        with patch.object(Path, "is_junction", autospec=True, side_effect=lambda p: p == directory), \
             patch.object(PIPELINE, "run_command", return_value=({}, "")):
            with self.assertRaisesRegex(RuntimeError, "Enlace"):
                PIPELINE.cleanup_plan()

    def test_compose_solo_volumen_local_montajes_conocidos_y_sin_exponer_config(self):
        with patch.dict(os.environ, self.environment, clear=True), \
             patch.object(PIPELINE, "run_command", side_effect=[({"segundos": 1}, json.dumps(self.config())),
                 ({}, "npipe:////./pipe/dockerDesktopLinuxEngine"), ({}, "fixture")]) as command:
            result = PIPELINE.validate_fresh_compose("localhost:9092")
        self.assertEqual(result["volumen_postgres"], "fixture_postgres_data")
        self.assertFalse(command.call_args_list[0].kwargs["show_output"])
        self.assertIn("--file", command.call_args_list[0].args[1])

    def test_configuracion_docker_ajena_no_permite_limpieza(self):
        base = self.config()
        cases = []
        for name, value in (("external", True), ("name", "compartido"), ("driver_opts", {"device": "data/raw"})):
            config = copy.deepcopy(base)
            config["volumes"]["postgres_data"][name] = value
            cases.append(config)
        config = copy.deepcopy(base)
        config["services"]["otro"] = {}
        cases.append(config)
        config = copy.deepcopy(base)
        config["services"]["kafka"]["volumes"] = [{"type": "bind", "source": str(self.raw)}]
        cases.append(config)
        config = copy.deepcopy(base)
        config["services"]["postgres"]["ports"][0]["published"] = "9999"
        cases.append(config)
        for config in cases:
            with self.subTest(config=config), patch.dict(os.environ, self.environment, clear=True), \
                 patch.object(PIPELINE, "run_command", return_value=({"segundos": 1}, json.dumps(config))) as command:
                with self.assertRaises(RuntimeError):
                    PIPELINE.validate_fresh_compose("localhost:9092")
                self.assertEqual(command.call_count, 1)  # Sólo config, sin comandos destructivos.
        with patch.dict(os.environ, {**self.environment, "POSTGRES_HOST": "remoto"}, clear=True):
            with self.assertRaisesRegex(RuntimeError, "locales"):
                PIPELINE.validate_fresh_compose("localhost:9092")

    def test_daemon_docker_remoto_se_rechaza(self):
        with patch.dict(os.environ, self.environment, clear=True), \
             patch.object(PIPELINE, "run_command", side_effect=[({"segundos": 1}, json.dumps(self.config())),
                 ({}, "ssh://otro-servidor")]) as command:
            with self.assertRaisesRegex(RuntimeError, "daemon Docker local"):
                PIPELINE.validate_fresh_compose("localhost:9092")
            self.assertEqual(command.call_count, 2)

    def test_preparacion_valida_antes_de_destruir_y_espera_servicios_antes_de_topics(self):
        calls = []
        def step(name, result):
            def execute(*args, **kwargs):
                calls.append(name)
                return result
            return execute
        with patch.object(PIPELINE, "validate_fresh_raw", side_effect=step("raw", {"segundos": 0})), \
             patch.object(PIPELINE, "load_dotenv"), \
             patch.object(PIPELINE, "cleanup_plan", side_effect=step("plan", [])), \
             patch.object(PIPELINE, "validate_fresh_compose", side_effect=step("config", {"segundos": 0, "volumen_postgres": "fixture"})), \
             patch.object(PIPELINE, "verify_docker_reset", side_effect=step("confirmar_reset", {"segundos": 0})), \
             patch.object(PIPELINE, "clean_generated_files", side_effect=step("limpiar", {"segundos": 0})), \
             patch.object(PIPELINE, "run_command", side_effect=lambda stage, *a, **k: step(stage, ({"segundos": 0}, ""))()), \
             patch.object(PIPELINE, "wait_for_services", side_effect=step("esperar", {"segundos": 0})), \
             patch.object(PIPELINE, "create_stream_topics", side_effect=step("topics", {"segundos": 0})):
            result = PIPELINE.prepare_fresh_start()
        self.assertEqual(calls, ["raw", "plan", "config", "reiniciar_docker", "confirmar_reset", "limpiar", "levantar_docker", "esperar", "topics"])
        self.assertIn("duracion_total_segundos", result)

    def test_no_reutiliza_volumen_o_contenedor_que_docker_no_pudo_eliminar(self):
        for containers, volumes in (("", "fixture_postgres_data\n"), ("container-id\n", "")):
            with self.subTest(containers=containers, volumes=volumes), \
                 patch.object(PIPELINE, "run_command", side_effect=[({}, containers), ({}, volumes)]):
                with self.assertRaisesRegex(RuntimeError, "volumen anterior"):
                    PIPELINE.verify_docker_reset("fixture_postgres_data")
        with patch.object(PIPELINE, "run_command", side_effect=[({}, ""), ({}, "")]):
            self.assertIn("segundos", PIPELINE.verify_docker_reset("fixture_postgres_data"))

    def test_fallo_compose_aborta_antes_de_limpieza(self):
        with patch.object(PIPELINE, "cleanup_plan", return_value=[]), patch.object(PIPELINE, "load_dotenv"), \
             patch.object(PIPELINE, "validate_fresh_compose", side_effect=RuntimeError("config insegura")), \
             patch.object(PIPELINE, "clean_generated_files") as clean, patch.object(PIPELINE, "run_command") as command:
            with self.assertRaises(RuntimeError):
                PIPELINE.prepare_fresh_start()
            clean.assert_not_called()
            command.assert_not_called()

    def test_fresh_start_una_vez_dos_corridas_y_referencia_gold_nueva(self):
        calls = []
        def flow():
            calls.append("corrida")
            return self.new_run()
        def prepare():
            calls.append("fresh")
            return self.preparation()
        with patch.object(PIPELINE, "prepare_fresh_start", side_effect=prepare), \
             patch.object(PIPELINE, "fase1_pipeline", side_effect=flow):
            self.assertEqual(PIPELINE.main(["--fresh-start", "--evidence-prefix", "p2-test"]), 0)
        self.assertEqual(calls, ["fresh", "corrida", "corrida"])
        first, second, report = PIPELINE.evidence_paths("p2-test")
        first_json = json.loads(first.read_text(encoding="utf-8"))
        self.assertIn("preparacion_fresh_start", first_json)
        for number, path in ((1, first), (2, second)):
            evidence = json.loads(path.read_text(encoding="utf-8"))['requisito_1_1']
            self.assertEqual(evidence["estado"], "CON_DIFERENCIAS")
            self.assertEqual(len(evidence["tabla"]), 9)
            self.assertEqual(len(evidence["conteos_raw"]), 9)
            markdown = PIPELINE.load_evidence_path("p2-test", number)
            self.assertTrue(markdown.is_relative_to(self.root / "docs/metricas"))
            self.assertIn("| archivo | filas_esperadas | filas_cargadas | diferencia |", markdown.read_text(encoding="utf-8"))
        self.assertIn("Requisito 1.1", report.read_text(encoding="utf-8"))
        self.assertIn("Gold reconciliado con Silver", report.read_text(encoding="utf-8"))
        with patch.object(PIPELINE, "prepare_fresh_start") as prepare, \
             patch.object(PIPELINE, "fase1_pipeline") as flow:
            with self.assertRaises(SystemExit):
                PIPELINE.main(["--fresh-start", "--evidence-prefix", "p2-test"])
            prepare.assert_not_called()
            flow.assert_not_called()
        # --overwrite sigue siendo explícito y compatible.
        with patch.object(PIPELINE, "prepare_fresh_start", return_value=self.preparation()) as prepare, \
             patch.object(PIPELINE, "fase1_pipeline", side_effect=[self.new_run(), self.new_run()]):
            self.assertEqual(PIPELINE.main(["--fresh-start", "--evidence-prefix", "p2-test", "--overwrite"]), 0)
            prepare.assert_called_once()

    def test_flujo_normal_nunca_limpia(self):
        with patch.object(PIPELINE, "prepare_fresh_start") as prepare, \
             patch.object(PIPELINE, "fase1_pipeline", side_effect=[run_fixture(), run_fixture()]):
            self.assertEqual(PIPELINE.main(["--evidence-prefix", "normal"]), 0)
            prepare.assert_not_called()
        saved = json.loads(PIPELINE.evidence_paths("normal")[0].read_text(encoding="utf-8"))
        self.assertNotIn("requisito_1_1", saved)
        self.assertFalse(PIPELINE.load_evidence_path("normal", 1).exists())

    def test_markdown_existente_protegido_antes_de_fresh_start(self):
        for number in (1, 2):
            with self.subTest(number=number):
                path = self.write(f"docs/metricas/p2-existente-{number}-requisito-1-1-corrida-{number}.md", "preservar")
                with patch.object(PIPELINE, "prepare_fresh_start") as prepare, \
                     patch.object(PIPELINE, "fase1_pipeline") as flow, self.assertRaises(SystemExit):
                    PIPELINE.main(["--fresh-start", "--evidence-prefix", f"p2-existente-{number}"])
                prepare.assert_not_called()
                flow.assert_not_called()
                self.assertEqual(path.read_text(encoding="utf-8"), "preservar")

    def test_fresh_mas_resume_se_rechaza_antes_de_limpiar(self):
        with patch.object(PIPELINE, "prepare_fresh_start") as prepare:
            with self.assertRaises(SystemExit):
                PIPELINE.main(["--fresh-start", "--resume-second", "--evidence-prefix", "p2-test"])
            prepare.assert_not_called()

    def test_resume_p2_conserva_primera_y_referencia_nueva_sin_limpiar(self):
        run = self.new_run()
        run.update(evidence_prefix="p2-resume", preparacion_fresh_start=self.preparation())
        PIPELINE.write_json("p2-resume-corrida-1.json", run)
        first = PIPELINE.evidence_paths("p2-resume")[0]
        before = first.read_bytes()
        with patch.object(PIPELINE, "prepare_fresh_start") as prepare, \
             patch.object(PIPELINE, "fase1_pipeline", return_value=self.new_run()) as flow:
            self.assertEqual(PIPELINE.main(["--resume-second", "--evidence-prefix", "p2-resume"]), 0)
            flow.assert_called_once()
            prepare.assert_not_called()
        self.assertEqual(first.read_bytes(), before)
        self.assertIn("requisito_1_1", json.loads(PIPELINE.evidence_paths("p2-resume")[1].read_text(encoding="utf-8")))
        self.assertTrue(PIPELINE.load_evidence_path("p2-resume", 2).exists())

    def test_resume_p2_con_raw_cambiado_aborta_antes_del_flujo(self):
        run = self.new_run()
        run.update(evidence_prefix="p2-resume", preparacion_fresh_start=self.preparation())
        PIPELINE.write_json("p2-resume-corrida-1.json", run)
        with (self.raw / "tm_estaciones.csv").open("a", encoding="utf-8") as file:
            file.write("x,x,x,x,x,x\n")
        with patch.object(PIPELINE, "fase1_pipeline") as flow, self.assertRaises(SystemExit):
            PIPELINE.main(["--resume-second", "--evidence-prefix", "p2-resume"])
        flow.assert_not_called()

    def test_p2_rechaza_gold_inconsistente_aunque_las_corridas_sean_iguales(self):
        run = self.new_run()
        run["metricas"]["gold"]["fact_abordajes"] += 1
        with patch.object(PIPELINE, "prepare_fresh_start", return_value=self.preparation()), \
             patch.object(PIPELINE, "fase1_pipeline", side_effect=[copy.deepcopy(run), copy.deepcopy(run)]):
            self.assertEqual(PIPELINE.main(["--fresh-start", "--evidence-prefix", "p2-malo"]), 1)

    def test_espera_servicios_con_reintento_y_timeout_sin_dormir(self):
        with patch.object(PIPELINE.validate_services, "fn", side_effect=[RuntimeError("arrancando"), {"postgres": "OK", "kafka": "OK"}]), \
             patch.object(PIPELINE.time, "sleep") as sleep:
            result = PIPELINE.wait_for_services("localhost:9092")
        self.assertEqual(result["postgres"], "OK")
        sleep.assert_called_once_with(2)
        with patch.object(PIPELINE.validate_services, "fn", side_effect=RuntimeError("caído")), \
             patch.object(PIPELINE.time, "sleep") as sleep:
            with self.assertRaisesRegex(RuntimeError, "tiempo límite"):
                PIPELINE.wait_for_services("localhost:9092", timeout=0)
            sleep.assert_not_called()

    def test_topics_usan_nombres_existentes_y_una_particion(self):
        admin = MagicMock()
        futures = {name: MagicMock() for name in (PIPELINE.TM_TOPIC, PIPELINE.AM_TOPIC)}
        admin.create_topics.return_value = futures
        with patch.object(PIPELINE, "AdminClient", return_value=admin):
            result = PIPELINE.create_stream_topics("localhost:9092")
        topics = admin.create_topics.call_args.args[0]
        self.assertEqual({t.topic for t in topics}, set(futures))
        self.assertTrue(all(t.num_partitions == 1 and t.replication_factor == 1 for t in topics))
        self.assertEqual(result["topics"], sorted(futures))
        for future in futures.values():
            future.result.assert_called_once_with(timeout=30)


if __name__ == "__main__":
    unittest.main()
