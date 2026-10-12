"""Regresión del inventario: resultados completos, honestos y sin rutas privadas."""
import importlib.util
import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
TEMP_ROOT = ROOT / 'dbt/red_metropolitana/target'
TEMP_ROOT.mkdir(parents=True, exist_ok=True)
SCRIPT = ROOT / 'scripts/validar_raw.py'
SPEC = importlib.util.spec_from_file_location('validar_raw', SCRIPT)
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class InventarioTest(unittest.TestCase):
    def test_archivo_existente_se_incluye_en_reporte(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp).resolve()
            self.assertTrue(root.is_relative_to(TEMP_ROOT.resolve()))
            raw, reports = root / 'raw', root / 'reports'
            raw.mkdir()
            (raw / 'ejemplo.csv').write_text('id,valor\n1,x\n', encoding='utf-8')
            expected = {'ejemplo.csv': {'type': 'csv', 'columns': ['id','valor'], 'expected_rows': 1}}
            with patch.object(MODULE, 'EXPECTED', expected), patch.object(MODULE, 'REPORT_DIR', reports), \
                 patch('sys.argv', ['validar_raw.py', '--raw-dir', str(raw)]):
                self.assertEqual(MODULE.main(), 0)
            result = json.loads((reports / 'inventario_raw.json').read_text(encoding='utf-8'))
            self.assertEqual(len(result['resultados']), 1)
            self.assertEqual(result['resultados'][0]['registros'], 1)
            self.assertEqual(len(result['resultados'][0]['sha256']), 64)
            self.assertNotIn('raw_dir', result)
            self.assertIn('ejemplo.csv', (reports / 'inventario_raw.md').read_text(encoding='utf-8'))

    def test_directorio_faltante_no_deja_ok(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            root = Path(tmp).resolve()
            self.assertTrue(root.is_relative_to(TEMP_ROOT.resolve()))
            expected = {'ejemplo.csv': {'type': 'csv', 'columns': ['id'], 'expected_rows': 1}}
            with patch.object(MODULE, 'EXPECTED', expected), patch.object(MODULE, 'REPORT_DIR', root / 'reports'), \
                 patch('sys.argv', ['validar_raw.py', '--raw-dir', str(root / 'ausente')]):
                self.assertEqual(MODULE.main(), 2)
            result = json.loads((root / 'reports/inventario_raw.json').read_text(encoding='utf-8'))
            self.assertEqual(result['estado_general'], 'REVISAR')
            self.assertEqual(result['resultados'][0]['estado'], 'ERROR')

    def test_jsonl_valida_llaves_en_todas_las_filas(self):
        with tempfile.TemporaryDirectory(dir=TEMP_ROOT) as tmp:
            self.assertTrue(Path(tmp).resolve().is_relative_to(TEMP_ROOT.resolve()))
            path = Path(tmp) / 'datos.jsonl'
            path.write_text('{"id":1,"exit":null}\n{"id":2}\n', encoding='utf-8')
            count, invalid, _, ok = MODULE.validate_jsonl(path, ['id','exit'])
            self.assertEqual((count, invalid, ok), (2, 0, False))


if __name__ == '__main__':
    unittest.main()
