"""Contrato CLI/evidencia del flujo completo, sin Kafka, PostgreSQL ni Prefect server."""
import copy
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / 'dbt/red_metropolitana/target'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
SPEC = importlib.util.spec_from_file_location('pipeline_under_test', ROOT / 'orchestration/flows/fase1_pipeline.py')
PIPELINE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(PIPELINE)


def artifact(invocation='fixture', statuses=None):
    statuses = statuses or [('test', 'pass'), ('model', 'success'), ('operation', 'success')]
    return {'metadata': {'generated_at': '2026-10-12T12:00:00Z', 'invocation_id': invocation},
            'args': {'which': 'build'}, 'elapsed_time': 1.0,
            'results': [{'unique_id': f'{kind}.fixture.node{i}', 'status': status}
                        for i, (kind, status) in enumerate(statuses)]}


def run_fixture():
    metrics = {key: {} for key in PIPELINE.COMPARISON_KEYS}
    metrics['gold'] = {name: 1 for name in PIPELINE.GOLD}
    metrics['gold'].update(fact_abordajes=1393448, fact_viajes_metroriel=295511)
    metrics['gold_abordajes_por_modo'] = {'Transmetro': 362106, 'Transurbano': 827788, 'Aerometro': 203554}
    metrics['tableau'] = {name: 1 for name in PIPELINE.TABLEAU}
    metrics['fingerprints_negocio'] = {'gold.mart_multimodalidad':
        {'filas': 1, 'fingerprint': 'fixture-a', 'auditoria_excluida': []}}
    stages = {'dbt_build': {'segundos': 1, 'codigo_salida': 0,
                           'resumen_dbt': PIPELINE.summarize_dbt_results(artifact())}}
    for mode in ('transmetro', 'aerometro'):
        stages[f'streaming_{mode}'] = {'producer': {'segundos': 1}, 'consumer': {'segundos': 1},
            'mensajes_consumidos': 1, 'eventos_nuevos': 0, 'duplicados_tecnicos': 1}
    return {'fecha_fin': '2026-10-12T06:00:01-06:00', 'duracion_total_segundos': 3,
            'etapas': stages, 'metricas': metrics}


class PipelineTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(dir=TEMP_ROOT)
        self.directory = Path(self.temp.name).resolve()
        self.assertTrue(self.directory.is_relative_to(TEMP_ROOT.resolve()))
        self.patch = patch.object(PIPELINE, 'EVIDENCE', self.directory)
        self.patch.start()
        self.addCleanup(self.temp.cleanup)
        self.addCleanup(self.patch.stop)

    def test_prefix_obligatorio_y_nombres(self):
        with self.assertRaises(SystemExit) as error:
            PIPELINE.build_parser().parse_args([])
        self.assertEqual(error.exception.code, 2)
        self.assertEqual([p.name for p in PIPELINE.evidence_paths('006-defensa')],
                         ['006-defensa-corrida-1.json', '006-defensa-corrida-2.json', '006-defensa-idempotencia.md'])
        for bad in ('../003', 'x/y', 'x\\y', '', 'a b', 'C:datos'):
            with self.subTest(bad=bad), self.assertRaises(ValueError):
                PIPELINE.evidence_paths(bad)

    def test_destino_existente_aborta_antes_del_flow(self):
        for index in range(3):
            with self.subTest(index=index):
                paths = PIPELINE.evidence_paths(f'006-existente-{index}')
                paths[index].write_text('preservar', encoding='utf-8')
                with patch.object(PIPELINE, 'fase1_pipeline') as flow:
                    with self.assertRaises(SystemExit):
                        PIPELINE.main(['--evidence-prefix', f'006-existente-{index}'])
                    flow.assert_not_called()
                self.assertEqual(paths[index].read_text(encoding='utf-8'), 'preservar')

    def test_dos_corridas_nuevo_prefix_y_reporte_dinamico(self):
        with patch.object(PIPELINE, 'fase1_pipeline', side_effect=[run_fixture(), run_fixture()]) as flow:
            self.assertEqual(PIPELINE.main(['--evidence-prefix', '006-test']), 0)
            self.assertEqual(flow.call_count, 2)
        first, second, report = PIPELINE.evidence_paths('006-test')
        self.assertTrue(first.exists() and second.exists())
        content = report.read_text(encoding='utf-8')
        self.assertIn('flujo completo del proyecto', content)
        self.assertIn('| 1 | 1 | 1 | 1 | 0 | 0 | 0 |', content)
        self.assertIn('006-test-corrida-1.json', content)
        self.assertNotIn('PASS=40', content)
        self.assertNotIn('PASS=189', content)
        self.assertFalse(report.read_bytes().startswith(b'\xef\xbb\xbf'))

    def test_resume_conserva_primera_y_ejecuta_solo_segunda(self):
        first, _, _ = PIPELINE.evidence_paths('006-resume')
        run = run_fixture()
        run['evidence_prefix'] = '006-resume'
        first.write_text(json.dumps(run), encoding='utf-8')
        before = first.read_bytes()
        with patch.object(PIPELINE, 'fase1_pipeline', return_value=run_fixture()) as flow:
            self.assertEqual(PIPELINE.main(['--evidence-prefix', '006-resume', '--resume-second']), 0)
            flow.assert_called_once()
        self.assertEqual(first.read_bytes(), before)
        with patch.object(PIPELINE, 'fase1_pipeline') as flow:
            with self.assertRaises(SystemExit):
                PIPELINE.main(['--evidence-prefix', '006-resume', '--resume-second'])
            flow.assert_not_called()

    def test_resume_rechaza_prefix_o_formato_incorrectos(self):
        first, _, _ = PIPELINE.evidence_paths('006-resume')
        for value in ({}, {'evidence_prefix': 'otro'}, {'evidence_prefix': '006-resume', 'metricas': {}}):
            first.write_text(json.dumps(value), encoding='utf-8')
            with self.subTest(value=value), patch.object(PIPELINE, 'fase1_pipeline') as flow:
                with self.assertRaises(SystemExit):
                    PIPELINE.main(['--evidence-prefix', '006-resume', '--resume-second'])
                flow.assert_not_called()

    def test_overwrite_es_explicito_y_resume_no_reemplaza_primera(self):
        with patch.object(PIPELINE, 'fase1_pipeline', side_effect=[run_fixture(), run_fixture()]):
            PIPELINE.main(['--evidence-prefix', '006-overwrite'])
        first, _, _ = PIPELINE.evidence_paths('006-overwrite')
        before = first.read_bytes()
        with patch.object(PIPELINE, 'fase1_pipeline', return_value=run_fixture()) as flow:
            self.assertEqual(PIPELINE.main(['--evidence-prefix', '006-overwrite', '--resume-second', '--overwrite']), 0)
            flow.assert_called_once()
        self.assertEqual(first.read_bytes(), before)

    def test_contenido_distinto_con_igual_conteo_falla(self):
        first, second = run_fixture(), run_fixture()
        second['metricas']['fingerprints_negocio']['gold.mart_multimodalidad']['fingerprint'] = 'fixture-b'
        with patch.object(PIPELINE, 'fase1_pipeline', side_effect=[first, second]):
            self.assertEqual(PIPELINE.main(['--evidence-prefix', '006-distinto']), 1)
        self.assertIn('DIFERENTES', PIPELINE.evidence_paths('006-distinto')[2].read_text(encoding='utf-8'))

    def test_escritura_exclusiva_no_sobrescribe(self):
        PIPELINE.write_json('006.json', {'first': True})
        with self.assertRaises(FileExistsError):
            PIPELINE.write_json('006.json', {'second': True})
        self.assertEqual(json.loads((self.directory / '006.json').read_text(encoding='utf-8')), {'first': True})

    def test_resumen_dbt_distingue_estados_y_no_copia_secretos(self):
        raw = artifact(statuses=[('test','pass'), ('model','success'), ('operation','success'),
                                 ('test','warn'), ('test','fail'), ('model','error'), ('test','skipped')])
        raw['results'][0]['compiled_code'] = 'secreto_fixture'
        result = PIPELINE.summarize_dbt_results(raw)
        self.assertEqual([result[k] for k in ('pruebas_pass','modelos_success','hooks_success','warnings','errores','skips')],
                         [1,1,1,1,2,1])
        self.assertNotIn('secreto_fixture', json.dumps(result))

    def test_dbt_build_rechaza_artefacto_anterior(self):
        path = self.directory / 'dbt/red_metropolitana/target/run_results.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(artifact()), encoding='utf-8')
        with patch.object(PIPELINE, 'ROOT', self.directory), patch.object(PIPELINE, 'run_script', return_value={}):
            with self.assertRaisesRegex(RuntimeError, 'nuevo dbt build'):
                PIPELINE.dbt_build.fn()

    def test_dbt_build_captura_nuevo_artefacto(self):
        path = self.directory / 'dbt/red_metropolitana/target/run_results.json'
        path.parent.mkdir(parents=True)
        path.write_text(json.dumps(artifact('antes')), encoding='utf-8')
        def execute(*args):
            path.write_text(json.dumps(artifact('despues')), encoding='utf-8')
            return {'segundos': 2, 'codigo_salida': 0}
        with patch.object(PIPELINE, 'ROOT', self.directory), patch.object(PIPELINE, 'run_script', side_effect=execute):
            result = PIPELINE.dbt_build.fn()
        self.assertEqual(result['resumen_dbt']['invocation_id'], 'despues')

    def test_fingerprint_excluye_solo_auditoria_y_cubre_contrato(self):
        connection = MagicMock()
        connection.execute.return_value.mappings.return_value.one.return_value = {'filas': 2, 'contenido': 'fixture'}
        result = PIPELINE.relation_fingerprints(connection, 'silver',
            ('bridge_identidad_usuario','silver_cuarentena','silver_features_usuario'))
        self.assertEqual(result['silver.bridge_identidad_usuario']['auditoria_excluida'], ['fecha_proceso'])
        self.assertEqual(result['silver.silver_cuarentena']['auditoria_excluida'], ['fecha_deteccion'])
        self.assertEqual(result['silver.silver_features_usuario']['auditoria_excluida'], [])
        self.assertNotIn('stg_cat_usuarios_minimos', PIPELINE.STAGING)
        self.assertEqual((len(PIPELINE.STAGING),len(PIPELINE.SILVER),len(PIPELINE.GOLD),len(PIPELINE.TABLEAU)), (13,10,12,6))
        for call in connection.execute.call_args_list:
            self.assertIn('ORDER BY md5', str(call.args[0]))


if __name__ == '__main__':
    unittest.main()
