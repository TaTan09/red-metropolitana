"""Validación de la plantilla y LOGIN, sin conexión PostgreSQL ni secretos reales."""
import importlib.util
import os
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from psycopg import sql

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('tableau_ro_under_test', ROOT / 'scripts/configurar_tableau_ro.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class TableauRoleTest(unittest.TestCase):
    def test_placeholder_y_password_corta_rechazados_antes_de_conectar(self):
        for value in ('corta', 'REEMPLAZAR_CON_PASSWORD_SEGURO_DE_16_O_MAS_CARACTERES'):
            with self.subTest(value=value), patch.dict(os.environ, {'TABLEAU_RO_PASSWORD': value}), \
                 patch.object(MODULE, 'load_dotenv'), patch.object(MODULE.psycopg, 'connect') as connect:
                with self.assertRaises(ValueError):
                    MODULE.main()
                connect.assert_not_called()

    def test_login_solo_con_variable_externa_y_composicion_segura(self):
        for enable in (False, True):
            env = {'POSTGRES_DB': 'fixture_db', 'POSTGRES_USER': 'fixture_owner', 'POSTGRES_PASSWORD': 'fixture'}
            if enable:
                env['TABLEAU_RO_PASSWORD'] = 'fixture-no-real-password'
            connection = MagicMock()
            connection.execute.return_value.fetchone.return_value = (enable,)
            manager = MagicMock()
            manager.__enter__.return_value = connection
            with self.subTest(enable=enable), patch.dict(os.environ, env, clear=True), \
                 patch.object(MODULE, 'load_dotenv'), patch.object(MODULE.psycopg, 'connect', return_value=manager):
                self.assertEqual(MODULE.main(), 0)
            queries = [call.args[0] for call in connection.execute.call_args_list]
            self.assertEqual(sum(isinstance(query, sql.Composed) for query in queries), int(enable))


if __name__ == '__main__':
    unittest.main()
