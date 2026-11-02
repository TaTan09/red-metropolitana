import unittest
from datetime import datetime

from scripts.auditar_fuga_p2_13 import FEATURES
from scripts.generar_evidencia_p2_13 import summarize


class SummaryTest(unittest.TestCase):
    def rows(self):
        return [dict(unidad_id='tarjeta', corte=cut, fecha_corte=datetime(2026, month, day),
                     operador='Transmetro', etiqueta=None if cut == 'C' else 0,
                     **dict.fromkeys(FEATURES, 1))
                for cut, month, day in [('A', 7, 1), ('B', 7, 31), ('C', 8, 30)]]

    def test_huella_repetible_y_detecta_cambios_de_valor(self):
        rows = self.rows()
        before = summarize(rows)
        self.assertEqual(before, summarize(rows))
        rows[0]['gasto_28d_gtq'] = 20
        after = summarize(rows)
        self.assertNotEqual(before[0]['sha256_filas_ordenadas'], after[0]['sha256_filas_ordenadas'])
        self.assertEqual(before[1:], after[1:])
        self.assertEqual(after[2]['etiquetas_nulas'], 1)

    def test_rechaza_cortes_faltantes_duplicados_nulos_y_etiqueta_c(self):
        bad = [self.rows()[:2], [self.rows()[0]] + self.rows()]
        for column, value in [('etiqueta', 1), ('viajes_28d', None)]:
            rows = self.rows()
            rows[2][column] = value
            bad.append(rows)
        for rows in bad:
            with self.subTest(rows=rows), self.assertRaises(ValueError):
                summarize(rows)


if __name__ == '__main__':
    unittest.main()
