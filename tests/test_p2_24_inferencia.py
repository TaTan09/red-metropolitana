"""Inferencia e invariancia con fixtures; nunca se ejecuta el test B oficial."""
import csv
import hashlib
import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch
import joblib
import numpy as np
import pandas as pd
from threadpoolctl import threadpool_limits
import predecir
from scripts import p2_24 as m, datos_p2_24 as inputs, invariancia_p2_24 as audit

def fixture_pack(folder):
    folder=Path(folder)
    folder.mkdir()
    sources={}
    for name, columns in inputs.SCHEMAS.items():
        rows=[]
        if name=='silver_cuarentena':
            rows=[{'fuente':'Transmetro','id_registro_crudo':'excluido'}]
        elif name=='silver_padron_transmetro_scd2':
            rows=[{'tarjeta_id':'0001','operacion':'INSERT','valid_from':'2026-06-01'}]
        else:
            key=next(c for c,_ in columns if c in ('tarjeta_id','id_tarjeta','user_hash','tarjeta_mr'))
            for i,instant in enumerate(('2026-08-28 12:00:00','2026-08-29 12:00:00')):
                row={c:'1' for c,_ in columns}
                row.update(bronze_record_id=f'id-{i}',tarifa_quetzales='2.50')
                row[key]='0001'
                if name=='silver_metroriel_viajes':
                    row.update(fecha_hora_ingreso=instant,fecha_hora_salida=instant.replace('12:','13:'))
                else:
                    row['fecha_hora']=instant
                rows.append(row)
        p=folder/f'{name}.csv'
        with p.open('w',encoding='utf-8',newline='') as f:
            w=csv.DictWriter(f,fieldnames=[c for c,_ in columns],lineterminator='\n')
            w.writeheader(); w.writerows(rows)
        sources[name]={'archivo':p.name,'filas':len(rows),'sha256':m.sha256(p)}
    m.write_json(folder/'manifest.json',{'formato':inputs.FORMAT,'fecha_corte':'2026-08-30','fuentes':sources})
    return folder

def feature_rows():
    return [dict(unidad_id=hashlib.md5((op+':0001').encode()).hexdigest(),tarjetas='0001',
                 operador=op,**{f:float(i+1) for i,f in enumerate(m.training.FEATURES)})
            for op in ('Transmetro','Transurbano','MetroRiel','Aerometro')]

class ContractTest(unittest.TestCase):
    def test_modelo_umbral_y_features_oficiales(self):
        d,e=m.official()
        self.assertEqual(d['modelo'],'rf_somero')
        self.assertEqual(d['umbral'],0.311210473799652)
        pipe=m.training.build_model(d['configuracion'])
        self.assertEqual(pipe.named_steps['clf'].get_params()['max_depth'],6)
        self.assertEqual(d['predictores'],list(m.training.PREDICTORS))

    def test_identidades_llaves_y_orden(self):
        d=m.validate_features(feature_rows())
        self.assertEqual(d.tarjetas.tolist(),['0001']*4)
        self.assertEqual(d.unidad_id.tolist(),sorted(d.unidad_id))
        bad=feature_rows(); bad[0]['unidad_id']='id-incorrecto'
        with self.assertRaises(ValueError): m.validate_features(bad)
        with self.assertRaises(ValueError): m.validate_features(feature_rows()+feature_rows()[:1])
        bad=feature_rows(); bad[0]['viajes_7d']=np.inf
        with self.assertRaises(ValueError): m.validate_features(bad)

    def test_probabilidades_y_contacto_inclusivo_sin_fit(self):
        d=m.validate_features(feature_rows())
        threshold=m.official()[0]['umbral']
        class Fake:
            def predict_proba(self,x):
                p=np.array([0,threshold,np.nextafter(threshold,0),1])
                return np.column_stack([1-p,p])
            def fit(self,*args): raise AssertionError('Inferencia reentrena')
        result=m.predict_frame(Fake(),d,threshold)
        self.assertEqual(result.contactar.tolist(),[0,1,0,1])
        self.assertEqual(list(result),m.OUTPUT_COLUMNS)

    def test_fecha_rechaza_b_y_valores_no_iso(self):
        self.assertEqual(inputs.cutoff('2026-08-30'),'2026-08-30')
        for v in ('2026-07-31','20260830','2026-08-30 00:00:00',"2026-08-30';drop table x"):
            with self.assertRaises(ValueError): inputs.cutoff(v)

    def test_manifest_hash_y_ruta_no_ignorados(self):
        with tempfile.TemporaryDirectory() as tmp:
            folder=fixture_pack(Path(tmp)/'entrada')
            inputs.read_manifest(folder,'2026-08-30')
            with (folder/'silver_cuarentena.csv').open('a') as f: f.write('alterado\n')
            with self.assertRaisesRegex(ValueError,'Hash'): inputs.read_manifest(folder,'2026-08-30')

    def test_salida_existente_no_se_sobrescribe(self):
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'existente.csv'; p.write_text('preservado')
            with self.assertRaises(FileExistsError): predecir.predict(tmp,'2026-08-30',p)
            self.assertEqual(p.read_text(),'preservado')

    def test_cli_exige_datos_y_fecha(self):
        with self.assertRaises(SystemExit) as exc: predecir.main([])
        self.assertEqual(exc.exception.code,2)

    def test_cli_recalcula_sin_fit_y_preserva_csv_identico(self):
        data=m.validate_features(feature_rows())
        d,_=m.official()
        class Fake:
            def predict_proba(self,x): return np.tile([.6,.4],(len(x),1))
            def fit(self,*args): raise AssertionError('Inferencia no debe ajustar')
        meta={'modelo_sha256':'hash','versiones':{}}
        with tempfile.TemporaryDirectory() as tmp, \
             patch.object(m,'load_model',return_value=(Fake(),d,meta)), \
             patch.object(inputs,'calculate',return_value=(data,{})) as calc:
            p=Path(tmp)/'salida.csv'
            predecir.predict(tmp,'2026-08-30',p)
            before=p.read_bytes(); evidence=p.with_suffix('.json').read_bytes()
            predecir.predict(tmp,'2026-08-30',p)
            self.assertEqual(calc.call_count,2)
            self.assertEqual(p.read_bytes(),before)
            self.assertEqual(p.with_suffix('.json').read_bytes(),evidence)

    def test_comparador_detecta_cambios_en_cada_campo(self):
        with tempfile.TemporaryDirectory() as tmp:
            a=Path(tmp)/'a.csv'; b=Path(tmp)/'b.csv'
            f=pd.DataFrame({'unidad_id':['a','b'],'tarjetas':['0001','0002'],
                            'puntaje':[.2,.4],'contactar':[0,1]})
            f.to_csv(a,index=False); f.to_csv(b,index=False)
            self.assertEqual(audit.compare(a,b)['diferencias'],0)
            for col,value in [('unidad_id','nuevo'),('tarjetas','otra'),('puntaje',.20000001),('contactar',1)]:
                changed=f.copy(); changed.loc[0,col]=value; changed.to_csv(b,index=False)
                with self.subTest(col=col),self.assertRaises(ValueError): audit.compare(a,b)

    def test_carga_modelo_real_sintetico_y_rechazo_hash(self):
        d,_=m.official(); data=m.validate_features(feature_rows())
        pipe=m.training.build_model(d['configuracion'])
        with threadpool_limits(limits=1): pipe.fit(data[d['predictores']],[0,1,0,1])
        with tempfile.TemporaryDirectory() as tmp:
            p=Path(tmp)/'modelo.joblib'; joblib.dump(pipe,p)
            meta={'modelo_version':m.VERSION,'modelo_sha256':m.sha256(p),
                  'decision_json_canonico_sha256':m.json_hash(d),'predictores':d['predictores'],
                  'configuracion':d['configuracion'],'versiones':m.versions()}
            m.write_json(p.with_suffix('.json'),meta)
            loaded,_,_=m.load_model(p,p.with_suffix('.json'))
            np.testing.assert_array_equal(loaded.predict_proba(data[d['predictores']]),pipe.predict_proba(data[d['predictores']]))
            with p.open('ab') as f: f.write(b'cambiado')
            with self.assertRaisesRegex(ValueError,'serializado'): m.load_model(p,p.with_suffix('.json'))

@unittest.skipUnless(os.getenv('P2_TEST_POSTGRES')=='1','Requiere PostgreSQL; sólo datos sintéticos TEMP')
class PostgresInferenceTest(unittest.TestCase):
    def test_inferencia_copia_ampliada_30_dias_y_control_positivo_fuga(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_pack(Path(tmp)/'base')
            base,meta=inputs.calculate(source,'2026-08-30')
            self.assertEqual(len(base),4)
            self.assertTrue(base.viajes_28d.eq(2).all())
            extended=Path(tmp)/'mas30'
            changes=audit.extend(source,extended,'2026-08-30')
            self.assertTrue(all(c['filas_agregadas']>0 for c in changes.values()))
            future,_=inputs.calculate(extended,'2026-08-30')
            pd.testing.assert_frame_equal(base,future)
            real_render=inputs.render
            def broken(*args,**kwargs):
                return (real_render(*args,**kwargs)
                        .replace('and u.fecha_uso < c.fecha_corte\n','and true\n')
                        .replace('and u.fecha_uso < p.fecha_corte\n','and true\n')
                        .replace('and u.disponible_desde < c.fecha_corte\n','and true\n')
                        .replace('and u.disponible_desde < p.fecha_corte\n','and true\n'))
            with patch.object(inputs,'render',side_effect=broken):
                leaked,_=inputs.calculate(extended,'2026-08-30')
            self.assertNotEqual(m.frame_hash(base),m.frame_hash(leaked))

    def test_datos_modificados_antes_del_corte_cambian_features(self):
        with tempfile.TemporaryDirectory() as tmp:
            source=fixture_pack(Path(tmp)/'base')
            base,_=inputs.calculate(source,'2026-08-30')
            p=source/'silver_transmetro_validaciones.csv'
            with p.open('a',encoding='utf-8',newline='') as f: f.write('id-nuevo,0001,2026-08-29 14:00:00,9.0,1\n')
            manifest=json.loads((source/'manifest.json').read_text())
            manifest['fuentes']['silver_transmetro_validaciones'].update(filas=3,sha256=m.sha256(p))
            (source/'manifest.json').write_text(json.dumps(manifest),encoding='utf-8')
            changed,_=inputs.calculate(source,'2026-08-30')
            self.assertNotEqual(m.frame_hash(base),m.frame_hash(changed))

if __name__=='__main__': unittest.main()
