import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

import numpy as np
import pandas as pd
from sklearn.metrics import adjusted_rand_score

from scripts.auditar_fuga_p2_13 import FEATURES
from scripts.segmentar_p2_23 import describe, fit_segments, load_a, plot_results, write_report


class SegmentationTest(unittest.TestCase):
    def setUp(self):
        rng = np.random.default_rng(42)
        self.x = np.r_[rng.normal(-3, .15, size=(60, 2)), rng.normal(3, .15, size=(60, 2))]

    def fit(self, x=None):
        return fit_segments(self.x if x is None else x, ks=(2, 3, 4), sample_size=80)

    def test_elige_separacion_conocida_y_es_repetible(self):
        first, second = self.fit(), self.fit()
        self.assertEqual(first['k'], 2)
        self.assertEqual(first['curvas'], second['curvas'])
        np.testing.assert_array_equal(first['etiquetas_cluster'], second['etiquetas_cluster'])
        np.testing.assert_allclose(first['pca'], second['pca'])
        self.assertLessEqual(sum(first['varianza_explicada']), 1 + 1e-12)

    def test_escalado_evitar_que_unidades_dominen_distancias(self):
        original, rescaled = self.fit(), self.fit(self.x * [1000, .001])
        self.assertEqual(adjusted_rand_score(original['etiquetas_cluster'], rescaled['etiquetas_cluster']), 1)
        np.testing.assert_allclose(original['varianza_explicada'], rescaled['varianza_explicada'])

    def test_rechaza_nulos_infinitos_muestra_invalida_y_sin_diversidad(self):
        for x in (np.full((10, 2), np.nan), np.full((10, 2), np.inf), np.zeros((10, 2)), self.x[:2]):
            with self.subTest(x=x.shape), self.assertRaises(ValueError):
                self.fit(x)
        with self.assertRaises(ValueError):
            fit_segments(self.x, sample_size=2)

    def test_etiqueta_solo_cambia_descripcion_y_acciones_son_distintas(self):
        frame = pd.DataFrame({col: np.r_[np.ones(60), np.full(60, 10)] for col in FEATURES})
        frame['etiqueta'] = np.r_[np.zeros(60), np.ones(60)]
        labels = self.fit()['etiquetas_cluster']
        before = describe(frame, labels)
        frame['etiqueta'] = 1 - frame['etiqueta']
        after = describe(frame, labels)
        for left, right in zip(before, after):
            self.assertEqual((left['nombre'], left['medianas']), (right['nombre'], right['medianas']))
            self.assertEqual(left['tasa_abandono'] + right['tasa_abandono'], 1)
        self.assertEqual(sum(row['tamano'] for row in before), len(frame))
        self.assertGreaterEqual(len({row['accion_retencion'] for row in before}), 2)

    def test_carga_exclusivamente_a_y_rechaza_duplicados(self):
        row = dict(unidad_id='a', corte='A', fecha_corte='2026-07-01', etiqueta=0,
                   operador='Transmetro', **dict.fromkeys(FEATURES, 1))
        conn = MagicMock()
        conn.execute.return_value.fetchall.return_value = [row]
        frame, fingerprint = load_a(conn)
        self.assertIn("where corte='A'", conn.execute.call_args.args[0])
        self.assertEqual(len(frame), 1)
        self.assertEqual(len(fingerprint), 64)
        conn.execute.return_value.fetchall.return_value = [row, row]
        with self.assertRaises(ValueError):
            load_a(conn)

    def test_reporte_y_tres_figuras_se_generan(self):
        result = self.fit()
        frame = pd.DataFrame(dict.fromkeys(FEATURES, np.arange(120) + 1))
        frame['etiqueta'] = np.arange(120) % 2
        segments = describe(frame, result['etiquetas_cluster'])
        report = {k: v for k, v in result.items() if k not in ('etiquetas_cluster', 'pca')}
        report.update(filas=120, segmentos=segments, justificacion_k='Fixture de dos grupos')
        with tempfile.TemporaryDirectory() as temp:
            target = Path(temp)
            write_report(report, target)
            plot_results(result, segments, target)
            self.assertEqual(json.loads((target / 'resultados.json').read_text(encoding='utf-8'))['k'], 2)
            for name in ('codo.png', 'silueta.png', 'pca.png'):
                self.assertGreater((target / name).stat().st_size, 1000)


if __name__ == '__main__':
    unittest.main()
