"""Sólo datos sintéticos y mocks: ninguna prueba consulta etiquetas reales de B."""
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd
from sklearn.metrics import confusion_matrix, precision_score, recall_score

from scripts import umbral_p2_22 as m
from tests.test_p2_21_ensemble import fixture


class EconomicsTest(unittest.TestCase):
    def test_formula_manual_tp_fp_tn_fn(self):
        r = m.at_threshold([1, 1, 0, 0], [.9, .1, .8, .2], .5)
        self.assertEqual([r[k] for k in ('tp', 'fp', 'tn', 'fn')], [1, 1, 1, 1])
        self.assertEqual(r['ganancia_gtq'], 5)  # 15*1 - 5*2 = 10*1 - 5*1
        self.assertEqual(r['precision'], .5)
        self.assertEqual(r['recall'], .5)

    def test_beneficio_teorico_y_punto_equilibrio(self):
        self.assertEqual(.25 * 60, 15)
        self.assertEqual(15 * (1 / 3) - 5, 0)
        self.assertGreater(15 * .4 - 5, 0)
        self.assertLess(15 * .2 - 5, 0)
        self.assertEqual(m.COSTS['beneficio_esperado_tp_gtq'], 15)

    def test_extremos_scores_cero_uno_contacto_inclusivo(self):
        self.assertEqual(m.at_threshold([0, 1], [0, 1], 0)['contactadas'], 2)
        self.assertEqual(m.at_threshold([0, 1], [0, 1], 1)['tp'], 1)
        none = m.at_threshold([0, 1], [0, 1], np.nextafter(1., np.inf))
        self.assertEqual(none['ganancia_gtq'], 0)
        self.assertEqual(none['precision'], 0)
        self.assertEqual(m.at_threshold([0, 0], [.4, .6], .5)['recall'], 0)

    def test_tabla_acumulada_igual_fuerza_bruta_y_sklearn(self):
        rng = np.random.default_rng(2026)
        y = rng.integers(0, 2, 200)
        p = rng.integers(0, 11, 200) / 10
        table = m.threshold_table(y, p)
        for row in table.to_dict('records'):
            actual = m.at_threshold(y, p, row['umbral'])
            self.assertEqual({k: row[k] for k in actual}, actual)
            pred = p >= row['umbral']
            self.assertEqual(confusion_matrix(y, pred).tolist(),
                             [[row['tn'], row['fp']], [row['fn'], row['tp']]])
            self.assertEqual(row['precision'], precision_score(y, pred, zero_division=0))
            self.assertEqual(row['recall'], recall_score(y, pred, zero_division=0))
        self.assertEqual(m.select_threshold(table), m.select_threshold(table.sample(frac=1, random_state=7)))

    def test_empate_menos_contactos_y_mayor_umbral(self):
        table = m.threshold_table([1, 0, 0], [.5, .5, .5])
        best = m.select_threshold(table)
        self.assertEqual(best['ganancia_gtq'], 0)
        self.assertEqual(best['contactadas'], 0)
        self.assertEqual(best['umbral'], np.nextafter(1., np.inf))

    def test_nadie_supera_todos_negativos(self):
        self.assertEqual(m.select_threshold(m.threshold_table([0, 0], [.1, .9]))['contactadas'], 0)

    def test_no_separar_scores_empatados(self):
        table = m.threshold_table([1, 0, 1], [.5, .5, .2])
        self.assertNotIn(1, table['contactadas'].tolist())

    def test_rechazar_vectores_invalidos(self):
        for y, p in [([], []), ([1], [np.nan]), ([0], [-.1]), ([1], [1.01]), ([2], [.5]),
                     ([1, 0], [.3]), ([[1]], [[.3]])]:
            with self.subTest(y=y, p=p), self.assertRaises(ValueError):
                m.threshold_table(y, p)


class OOFTest(unittest.TestCase):
    def setUp(self):
        data = m.training.prepare_cut_a(fixture())
        folds = m.training.make_folds(data['etiqueta'].to_numpy())
        e = m.evidence()
        self.oof = m.training.build_oof(data, folds, np.linspace(0, 1, len(data)), e['recomendado'])
        e['filas'], e['positivos'] = len(data), int(data['etiqueta'].sum())
        e['folds_sha256'] = m.training.sha256(self.oof[['unidad_id', 'fold']].to_csv(index=False, lineterminator='\n'))
        e['folds'] = [{'fold': i, 'validacion': len(valid),
                       'positivos_validacion': int(data['etiqueta'].iloc[valid].sum())}
                      for i, (_, valid) in enumerate(folds)]
        self.e = e

    def test_oof_valido_reordenado_y_configuracion_equivalente(self):
        self.assertEqual(len(m.validate_oof(self.oof.sample(frac=1), self.e)), len(self.oof))

    def test_rechaza_corrupciones(self):
        for column, value in [('unidad_id', self.oof.loc[1, 'unidad_id']), ('corte', 'B'),
                              ('fecha_corte', '2026-07-31'), ('etiqueta', 2), ('fold', 9),
                              ('modelo', 'rf_flexible'), ('configuracion_modelo', '{}'),
                              ('probabilidad_abandono', np.inf), ('unidad_id', ''),
                              ('probabilidad_abandono', np.nan)]:
            d = self.oof.copy()
            d.loc[0, column] = value
            with self.subTest(column=column, value=value), self.assertRaises(ValueError):
                m.validate_oof(d, self.e)

    def test_hash_incorrecto_bloquea_antes_de_parsear(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'wrong.csv'
            p.write_text('incorrecto', encoding='utf-8')
            with patch.object(m, 'OOF', p), self.assertRaises(ValueError):
                m.load_oof(self.e)


class SingleTestGuard(unittest.TestCase):
    def test_reserva_previa_bloquea_incluso_si_hubo_error(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'journal.jsonl'
            p.touch()
            with patch.object(m, 'JOURNAL', p), patch.object(m, 'verify_freeze') as verify:
                with self.assertRaises(FileExistsError):
                    m.evaluate_once('abc')
                verify.assert_not_called()

    def test_fallo_entrenamiento_no_abre_b_y_no_permite_reintento(self):
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'journal.jsonl'
            with patch.object(m, 'JOURNAL', p), patch.object(m, 'RESULT', Path(tmp) / 'result'), \
                 patch.object(m, 'MODEL_PATH', Path(tmp) / 'model'), \
                 patch.object(m, 'PREDICTIONS', Path(tmp) / 'predictions'), \
                 patch.object(m, 'verify_freeze', return_value=({}, 'freeze')), \
                 patch.object(m, 'git', return_value='code'), \
                 patch.object(m, 'digest', return_value='hash'), \
                 patch.object(m.training, 'load_cut_a', side_effect=RuntimeError('sin conexión')), \
                 patch.object(m, 'load_b') as b:
                with self.assertRaisesRegex(RuntimeError, 'sin conexión'):
                    m.evaluate_once('freeze')
                b.assert_not_called()
                events = [json.loads(line) for line in p.read_text(encoding='utf-8').splitlines()]
                self.assertEqual(events[-1]['etapa_fallida'], 'entrenamiento_a')
                self.assertFalse(events[-1]['etiquetas_b_acceso_posible'])
                self.assertFalse(events[-1]['metricas_b_producidas'])
                with self.assertRaises(FileExistsError):
                    m.evaluate_once('freeze')

    def test_flujo_completo_sintetico_con_modelo_real_una_vez(self):
        a = m.training.prepare_cut_a(fixture())
        b = a.copy().assign(corte='B', fecha_corte=pd.Timestamp('2026-07-31'))
        e = m.evidence()
        e['entrada_sha256'] = m.training.sha256(a.to_csv(index=False, lineterminator='\n'))
        decision = {'configuracion': e['recomendado']['configuracion'], 'predictores': e['predictores'],
                    'umbral': .3, 'modelo': 'rf_somero', 'costos': m.COSTS, 'a': {}}
        with tempfile.TemporaryDirectory() as tmp:
            paths = {name: Path(tmp) / name for name in ('JOURNAL', 'RESULT', 'MODEL_PATH', 'PREDICTIONS')}
            with patch.multiple(m, **paths), patch.object(m, 'verify_freeze', return_value=(decision, 'freeze')), \
                 patch.object(m, 'git', return_value='code'), patch.object(m, 'evidence', return_value=e), \
                 patch.object(m, 'digest', return_value='hash'), \
                 patch.object(m.training, 'load_cut_a', return_value=a), \
                 patch.object(m, 'load_oof', return_value=a), patch.object(m, 'load_b', return_value=(b, 'hash')) as loader:
                with redirect_stdout(io.StringIO()):
                    m.evaluate_once('freeze')
                result = json.loads(paths['RESULT'].read_text(encoding='utf-8'))
                self.assertEqual(result['evaluaciones_b'], 1)
                self.assertEqual(result['tp'] + result['fn'], int(b['etiqueta'].sum()))
                self.assertEqual(result['ganancia_gtq'], 10 * result['tp'] - 5 * result['fp'])
                self.assertEqual(loader.call_count, 1)
                with self.assertRaises(FileExistsError):
                    m.evaluate_once('freeze')
                self.assertEqual(loader.call_count, 1)

    def test_sql_b_solo_corte_correcto_y_limites_temporales_13(self):
        sql = m.b_query()
        self.assertIn("corte = 'B'", sql)
        self.assertIn("timestamp '2026-07-31 00:00:00'", sql)
        self.assertNotIn("corte = 'A'", sql)
        self.assertIn('u.disponible_desde < p.fecha_corte', sql)
        self.assertIn('u.fecha_uso < p.fecha_corte', sql)
        self.assertIn("interval '28 days'", sql)

    def test_decision_corrupta_costos_o_umbral_rechazada(self):
        e = m.evidence()
        oof = pd.DataFrame({'etiqueta': [1, 0, 1], 'probabilidad_abandono': [.8, .3, .2]})
        best = m.select_threshold(m.threshold_table(oof.etiqueta, oof.probabilidad_abandono))
        d = {'modelo': e['recomendado']['modelo'], 'costos': dict(m.COSTS),
             'umbral': best['umbral'], 'a': {'seleccionado': best}}
        m.validate_decision(d, e, oof)
        d['umbral'] = .7
        with self.assertRaises(ValueError):
            m.validate_decision(d, e, oof)
        d['umbral'] = best['umbral']
        d['costos']['contacto_gtq'] = 6
        with self.assertRaises(ValueError):
            m.validate_decision(d, e, oof)

    def test_verify_freeze_rechaza_decision_modificada_antes_de_sql(self):
        def fake_git(*args):
            if args[0] == 'branch':
                return 'p2/hector-22'
            if args[0] == 'status':
                return ''
            return 'freeze'
        with tempfile.TemporaryDirectory() as tmp:
            p = Path(tmp) / 'decision.json'
            p.write_text('{"modificado":true}', encoding='utf-8')
            with patch.object(m, 'ROOT', Path(tmp)), patch.object(m, 'DECISION', p), \
                 patch.object(m, 'git', side_effect=fake_git), \
                 patch.object(m.subprocess, 'run'), \
                 patch.object(m.subprocess, 'check_output', return_value=b'{"original":true}'), \
                 patch.object(m, 'load_b') as loader:
                with self.assertRaisesRegex(ValueError, 'Decisión distinta'):
                    m.verify_freeze('freeze')
                loader.assert_not_called()


if __name__ == '__main__':
    unittest.main()
