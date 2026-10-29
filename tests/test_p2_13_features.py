"""Contrato y auditoría del SQL de producción, incluyendo PostgreSQL real.

P2_TEST_POSTGRES=1 habilita las pruebas de integración; usan sólo tablas TEMP.
"""
import importlib.util
import os
import unittest
from decimal import Decimal
from pathlib import Path
from unittest.mock import patch

from jinja2 import Environment

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location('p2_13', ROOT / 'scripts/auditar_fuga_p2_13.py')
MODULE = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(MODULE)


class ComparatorTest(unittest.TestCase):
    def row(self):
        return dict(unidad_id='id', fecha_corte='corte', corte='A', operador='Transmetro',
                    etiqueta=0, **dict.fromkeys(MODULE.FEATURES, Decimal('1')))

    def test_identifica_columna_y_fila_ausente_sin_redondear(self):
        a, b = self.row(), self.row()
        b['gasto_28d_gtq'] += Decimal('0.0000000001')
        self.assertEqual(MODULE.compare_rows([a], [b])['diferencias_por_columna'], {'gasto_28d_gtq': 1})
        b['unidad_id'] = 'otra'
        self.assertEqual(MODULE.compare_rows([a], [b])['diferencias_por_columna'], {'__fila_ausente__': 2})

    def test_etiqueta_futura_no_es_predictor(self):
        a, b = self.row(), self.row()
        b['etiqueta'] = 1
        self.assertEqual(MODULE.compare_rows([a], [b])['diferencias'], 0)

    def test_rechaza_duplicados_vacios_y_columnas_nuevas_sin_auditar(self):
        for left, right in (([], []), ([self.row()] * 2, [self.row()]),
                            ([dict(self.row(), nueva_feature=1)], [self.row()])):
            with self.subTest(left=left), self.assertRaises(ValueError):
                MODULE.compare_rows(left, right)


@unittest.skipUnless(os.getenv('P2_TEST_POSTGRES') == '1', 'Requiere P2_TEST_POSTGRES=1 y PostgreSQL local')
class PostgreSQLTest(unittest.TestCase):
    def setUp(self):
        self.conn = MODULE.connect()
        self.addCleanup(self.conn.close)
        self.conn.execute('set transaction isolation level repeatable read')
        self.conn.execute('''
            create temp table silver_transmetro_validaciones(
                tarjeta_id text, fecha_hora timestamp, bronze_record_id text,
                tarifa_quetzales numeric, estacion_id text);
            create temp table silver_transurbano_transacciones(
                id_tarjeta text, fecha_hora timestamp, bronze_record_id text,
                tarifa_quetzales numeric, cod_parada text);
            create temp table silver_aerometro_boardings(
                user_hash text, fecha_hora timestamp, bronze_record_id text,
                tarifa_quetzales numeric, station_code text);
            create temp table silver_metroriel_viajes(
                tarjeta_mr text, fecha_hora_ingreso timestamp, fecha_hora_salida timestamp,
                bronze_record_id text, tarifa_quetzales numeric, origen_estacion_id text);
            create temp table silver_cuarentena(fuente text, id_registro_crudo text);
            create temp table silver_padron_transmetro_scd2(tarjeta_id text, valid_from timestamp, operacion text);
            insert into silver_transmetro_validaciones values
                ('t', '2026-06-03', 'a', 1, 'p1'),
                ('t', '2026-06-24 08:00', 'b', 2, 'p2'),
                ('t', '2026-06-30 18:00', 'c', 3, 'p1'),
                ('t', '2026-07-01', 'futuro', 999, 'p3'),
                ('t', '2026-06-02 23:59:59', 'viejo', 1000, 'p4'),
                ('t', '2026-06-28', 'cuarentena', 2000, 'p5'),
                ('t', '2026-08-03', 'c1', 1, 'p1'),
                ('t', '2026-08-29', 'c2', 1, 'p1');
            insert into silver_cuarentena values ('Transmetro', 'cuarentena');
            insert into silver_metroriel_viajes values
                ('mr','2026-06-10 08:00','2026-06-10 09:00','mr1',4,'m1'),
                ('mr','2026-06-20 08:00','2026-06-20 09:00','mr2',4,'m1'),
                ('mr','2026-06-30 23:00','2026-07-01','mr3',99,'m2');
            insert into silver_padron_transmetro_scd2 values ('t','2026-07-01','DELETE');
        ''')

    def build(self, variables=None):
        refs = {key: f'pg_temp.{key}' for key in (*MODULE.BASES, 'silver_cuarentena')}
        for name in MODULE.MODELS:
            self.conn.execute(f'create temp table {name} as ' + MODULE.render_model(name, refs=refs, variables=variables))
            refs[name] = f'pg_temp.{name}'
        return self.conn.execute('select * from silver_p2_features_tarjeta order by corte, operador').fetchall()

    def test_features_limites_gasto_pico_cuarentena_y_etiqueta(self):
        rows = self.build()
        t = next(r for r in rows if r['corte'] == 'A' and r['operador'] == 'Transmetro')
        self.assertEqual((t['viajes_28d'], t['viajes_7d'], t['viajes_14d']), (3, 2, 2))
        self.assertEqual((t['gasto_28d_gtq'], t['tarifa_media_gtq'], t['puntos_origen_28d']), (6, 2, 2))
        self.assertEqual((t['dias_activos_28d'], t['dias_desde_ultimo_uso'], t['etiqueta']), (3, Decimal('0.25'), 0))
        self.assertAlmostEqual(float(t['proporcion_hora_pico']), 2/3)
        mr = next(r for r in rows if r['operador'] == 'MetroRiel')
        self.assertEqual((mr['viajes_28d'], mr['gasto_28d_gtq']), (2, 8))

    def test_c_sin_etiqueta_y_delete_previo_excluye(self):
        self.conn.execute("delete from silver_padron_transmetro_scd2")
        c, = [r for r in self.build() if r['corte'] == 'C']
        self.assertIsNone(c['etiqueta'])
        self.assertEqual(c['viajes_28d'], 2)

    def test_delete_previo_incluso_reactivado_excluye(self):
        self.conn.execute("insert into silver_padron_transmetro_scd2 values ('t','2026-06-01','DELETE'),('t','2026-06-02','INSERT')")
        self.assertFalse(any(r['operador'] == 'Transmetro' for r in self.build()))

    def test_cortes_parametrizables(self):
        rows = self.build({'p2_cortes': {'A': '2026-06-30', 'B': '2026-07-30', 'C': '2026-08-29'}})
        t = next(r for r in rows if r['corte'] == 'A' and r['operador'] == 'Transmetro')
        self.assertEqual((t['viajes_28d'], t['gasto_28d_gtq']), (3, 1003))

    def test_etiquetas_ab_se_conservan_y_pruebas_dbt_detectan_defectos(self):
        self.conn.execute("delete from silver_padron_transmetro_scd2")
        self.conn.execute("""insert into silver_transmetro_validaciones values
            ('t','2026-07-03','b1',1,'p1'), ('t','2026-07-30','b2',1,'p1'),
            ('t','2026-08-01','b3',1,'p1')""")
        rows = self.build()
        self.assertEqual({r['corte']: r['etiqueta'] for r in rows if r['operador'] == 'Transmetro'},
                         {'A': 0, 'B': 0, 'C': None})
        env = Environment()
        env.globals.update(config=lambda **kwargs: '', ref=lambda name: f'pg_temp.{name}')
        sql = env.from_string((MODULE.PROJECT / 'tests/p2_13_integridad.sql').read_text(encoding='utf-8')).render()
        self.assertEqual(self.conn.execute(sql).fetchall(), [])
        self.conn.execute("update silver_p2_features_tarjeta set etiqueta=1 where corte='C'")
        self.assertEqual(len(self.conn.execute(sql).fetchall()), 1)

    def test_repetir_transformacion_conserva_resultados(self):
        before = self.build()
        for name in reversed(MODULE.MODELS):
            self.conn.execute(f'drop table {name}')
        self.assertEqual(self.build(), before)

    def test_auditoria_recorta_fuentes_y_compara_features_reales(self):
        result = MODULE.audit(self.conn, source_schema='pg_temp')
        self.assertEqual((result['filas_comparadas'], result['cantidad_columnas'], result['diferencias']), (2, 11, 0))
        self.assertGreater(result['registros_eliminados_por_fuente']['silver_metroriel_viajes'], 0)

    def test_control_positivo_detecta_fuga_introducida_en_sql(self):
        original = MODULE.render_model
        def leaking(name, **kwargs):
            sql = original(name, **kwargs)
            if name == 'silver_p2_features_tarjeta':
                sql = sql.replace('and u.fecha_uso < p.fecha_corte', '').replace('and u.disponible_desde < p.fecha_corte', '')
            return sql
        with patch.object(MODULE, 'render_model', side_effect=leaking):
            result = MODULE.audit(self.conn, source_schema='pg_temp')
        self.assertGreater(result['diferencias_por_columna']['viajes_28d'], 0)
        self.assertGreater(result['diferencias_por_columna']['gasto_28d_gtq'], 0)


if __name__ == '__main__':
    unittest.main()
