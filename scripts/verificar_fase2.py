#!/usr/bin/env python3
"""Evidencia PostgreSQL de Fase 2, sin credenciales ni identidades individuales.

Uso: --snapshot antes; repetir build; --snapshot despues; --report.
--registrar-dbt ETIQUETA guarda sólo estados de target/run_results.json.
"""
import argparse
import hashlib
import json
import os
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import psycopg
from psycopg import sql
from psycopg.rows import dict_row
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TARGET = ROOT / 'dbt/red_metropolitana/target'
STATE = TARGET / 'revision_fase2_estado.json'
OPERACIONES = {
    'Transmetro': ('silver_transmetro_validaciones', 'fecha_hora'),
    'Transurbano': ('silver_transurbano_transacciones', 'fecha_hora'),
    'Aerometro': ('silver_aerometro_boardings', 'fecha_hora'),
    'MetroRiel': ('silver_metroriel_viajes', 'fecha_hora_ingreso'),
}


def connect():
    load_dotenv(ROOT / '.env')
    return psycopg.connect(host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'), dbname=os.environ['POSTGRES_DB'],
        user=os.environ['POSTGRES_USER'], password=os.environ['POSTGRES_PASSWORD'],
        connect_timeout=10, row_factory=dict_row)


def fingerprints(conn):
    relations = {
        'silver.silver_features_usuario': [], 'gold.mart_multimodalidad': [],
        'gold.v_tableau_transbordos': [], 'gold.v_tableau_multimodalidad': [],
        'gold.dim_usuario': [],
        'silver.bridge_identidad_usuario': ['fecha_proceso'],
        'silver.silver_cuarentena': ['fecha_deteccion'],
    }
    result = {}
    for relation, audit in relations.items():
        query = sql.SQL('''select count(*) as filas,
            md5(coalesce(string_agg(md5((to_jsonb(t) - %s::text[])::text), ''
                order by md5((to_jsonb(t) - %s::text[])::text)), '')) as fingerprint_contenido
            from {} t''').format(sql.Identifier(*relation.split('.')))
        result[relation] = {**conn.execute(query, (audit, audit)).fetchone(), 'auditoria_excluida': audit}
    return result


def verificar_rbac(conn):
    role = conn.execute("select rolcanlogin, rolsuper, rolcreatedb, rolcreaterole from pg_roles where rolname='tableau_ro'").fetchone()
    if role is None:
        return {'implementado': False}
    permissions = conn.execute('''select
        has_database_privilege('tableau_ro', current_database(), 'CONNECT') as connect,
        has_schema_privilege('tableau_ro','gold','USAGE') as usage_gold,
        has_schema_privilege('tableau_ro','staging','USAGE') as usage_staging,
        has_schema_privilege('tableau_ro','silver','USAGE') as usage_silver,
        (select bool_and(has_table_privilege('tableau_ro',c.oid,'SELECT'))
         from pg_class c join pg_namespace n on n.oid=c.relnamespace
         where n.nspname='gold' and c.relkind in ('r','v','m','p','f')) as select_todo_gold''').fetchone()
    with conn.transaction():
        conn.execute('SAVEPOINT rbac_future')
        conn.execute('CREATE TABLE gold.__revision_rbac_futura (n integer)')
        future = conn.execute("select has_table_privilege('tableau_ro','gold.__revision_rbac_futura','SELECT') as ok").fetchone()['ok']
        conn.execute('SET LOCAL ROLE tableau_ro')
        conn.execute('SELECT count(*) FROM gold.v_tableau_multimodalidad').fetchone()
        denied = {}
        for layer, table in [('staging','transmetro_validaciones'),('silver','silver_features_usuario')]:
            conn.execute('SAVEPOINT denied_layer')
            try:
                conn.execute(sql.SQL('select count(*) from {}').format(sql.Identifier(layer, table))).fetchone()
                denied[layer] = False
            except psycopg.errors.InsufficientPrivilege:
                denied[layer] = True
            finally:
                conn.execute('ROLLBACK TO SAVEPOINT denied_layer')
        conn.execute('ROLLBACK TO SAVEPOINT rbac_future')
    result = {'implementado': True, **role, **permissions, 'select_futuro_gold': future, 'lectura_denegada': denied}
    assert permissions['connect'] and permissions['usage_gold'] and permissions['select_todo_gold']
    assert not permissions['usage_staging'] and not permissions['usage_silver']
    assert future and all(denied.values())
    return result


def auditar_par_bronze_raw(conn):
    import csv
    import pyarrow.dataset as ds
    pair = conn.execute('''select modo_origen, modo_destino, bronze_record_id_origen, bronze_record_id_destino
        from gold.mart_multimodalidad order by transbordo_sk limit 1''').fetchone()
    if pair is None:
        return {'pares_disponibles': 0}
    source_map = {'Transmetro': ('transmetro_validaciones', True), 'Transurbano': ('transurbano_transacciones', False),
                  'Aerometro': ('aerometro_boardings', True), 'MetroRiel': ('metroriel_viajes', False)}
    checks = []
    for side in ['origen', 'destino']:
        mode, rid = pair['modo_' + side], pair['bronze_record_id_' + side]
        folder, streaming = source_map[mode]
        dataset = ds.dataset(str(ROOT / 'data/bronze' / folder), format='parquet', partitioning='hive')
        if streaming:
            filter_expr = ds.field('_event_id') == rid
        else:
            sha, number = rid.split(':')
            filter_expr = (ds.field('_source_sha256') == sha) & (ds.field('_record_number') == int(number))
        rows = dataset.to_table(filter=filter_expr).to_pylist()
        assert rows, 'No se encontró el registro en Bronze'
        row = rows[0]
        raw = ROOT / 'data/raw' / Path(row['_source_file']).name
        assert hashlib.sha256(raw.read_bytes()).hexdigest() == row['_source_sha256'], 'Hash Raw no coincide'
        number = int(row['_record_number'])
        with raw.open(encoding='utf-8-sig', newline='') as stream:
            if raw.suffix == '.csv':
                record = next(r for i, r in enumerate(csv.DictReader(stream), 1) if i == number)
            else:
                record = next(json.loads(r) for i, r in enumerate(stream, 1) if i == number)
        if 'raw_json' in row:
            payload = json.loads(row['raw_json'])
            payload = payload.get('data', payload)
        else:
            # Batch CSV conserva las columnas crudas como texto; sólo JSONL y
            # streaming usan raw_json. No atribuirles un formato inexistente.
            payload = {key: row[key] for key in record}
        assert payload == record, 'Payload Bronze difiere del registro Raw'
        checks.append({'lado': side, 'modo': mode, 'archivo': raw.name, 'numero_registro': number,
                       'sha256_verificado': True, 'payload_coincide': True})
    return {'pares_auditados': 1, 'eventos': checks, 'alcance': 'Un par real, no auditoría exhaustiva de todos los pares'}


def metricas(conn):
    bounds = []
    for mode, (table, date) in OPERACIONES.items():
        q = sql.SQL('select count(*) as eventos, min({}) as minimo, max({}) as maximo from {}').format(
            sql.Identifier(date), sql.Identifier(date), sql.Identifier('silver', table))
        bounds.append({'modo': mode, **conn.execute(q).fetchone()})
    mr = conn.execute('select min(fecha_hora_salida) minimo, max(fecha_hora_salida) maximo from silver.silver_metroriel_viajes').fetchone()
    features = conn.execute('''select count(*) filas, count(distinct usuario_canonico_id) usuarios_unicos,
        min(fecha_corte) cutoff_min, max(fecha_corte) cutoff_max,
        count(*) filter(where es_multimodal) usuarios_multimodales,
        sum(total_eventos) eventos, sum(eventos_ultimos_7_dias) eventos_7d,
        sum(eventos_ultimos_30_dias) eventos_30d, sum(eventos_ultimos_90_dias) eventos_90d,
        count(*) filter(where ultimo_evento > fecha_corte) usuarios_posteriores_cutoff
        from silver.silver_features_usuario''').fetchone()
    columns = conn.execute("select column_name from information_schema.columns where table_schema='silver' and table_name='silver_features_usuario' order by ordinal_position").fetchall()
    nulls = {}
    for item in columns:
        name = item['column_name']
        q = sql.SQL('select count(*) as n from silver.silver_features_usuario where {} is null').format(sql.Identifier(name))
        nulls[name] = conn.execute(q).fetchone()['n']
    features['nulos_por_columna'] = nulls
    features['distribucion_modos'] = conn.execute('select modos_utilizados, count(*) usuarios from silver.silver_features_usuario group by 1 order by 1').fetchall()
    modal = conn.execute('''select count(*) total_usuarios_observados,
        count(*) filter(where modos_observados>1) usuarios_multimodales,
        count(*) filter(where modos_observados=1) usuarios_unimodales,
        round(100.0*count(*) filter(where modos_observados>1)/nullif(count(*),0),2) pct_usuarios_multimodales
        from gold.dim_usuario''').fetchone()
    modal['distribucion_modos'] = conn.execute('select modos_observados, count(*) usuarios from gold.dim_usuario group by 1 order by 1').fetchall()
    modal['distribucion_identidad'] = conn.execute('select metodo_identidad, count(*) usuarios from gold.dim_usuario group by 1 order by 1').fetchall()
    modal['vista'] = conn.execute('select * from gold.v_tableau_multimodalidad order by 1,2').fetchall()
    transfers = conn.execute('''select count(*) total, min(tiempo_transferencia_minutos) minimo_minutos,
        max(tiempo_transferencia_minutos) maximo_minutos, round(avg(tiempo_transferencia_minutos),6) promedio_minutos,
        count(*) filter(where incluye_aerometro) incluye_aerometro_true
        from gold.mart_multimodalidad''').fetchone()
    transfers['combinaciones'] = conn.execute('select combinacion_modos, count(*) transbordos from gold.mart_multimodalidad group by 1 order by 2 desc,1').fetchall()
    monthly_sql = (ROOT / 'sql/utilities/eventos_movilidad_mes.sql').read_text(encoding='utf-8')
    monthly1, monthly2 = conn.execute(monthly_sql).fetchone(), conn.execute(monthly_sql).fetchone()
    assert monthly1 == monthly2
    assert modal['usuarios_multimodales'] + modal['usuarios_unimodales'] == modal['total_usuarios_observados']
    assert features['filas'] == features['usuarios_unicos'] and not any(nulls.values())
    return {'fuentes_silver': bounds, 'salidas_metroriel': mr,
        'fecha_minima_global': min(x['minimo'] for x in bounds),
        'fecha_maxima_global': max([x['maximo'] for x in bounds] + [mr['maximo']]),
        'features': features, 'multimodalidad_gold': modal, 'transbordos_inferidos': transfers,
        'prueba_mes': {'corrida_1': monthly1, 'corrida_2': monthly2, 'iguales': True},
        'rbac': verificar_rbac(conn), 'trazabilidad_par': auditar_par_bronze_raw(conn)}


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--snapshot', choices=['antes','despues'])
    parser.add_argument('--registrar-dbt')
    parser.add_argument('--report', action='store_true')
    args = parser.parse_args()
    TARGET.mkdir(parents=True, exist_ok=True)
    state = json.loads(STATE.read_text(encoding='utf-8')) if STATE.exists() else {}
    if args.registrar_dbt:
        raw = json.loads((TARGET / 'run_results.json').read_text(encoding='utf-8'))
        results = raw['results']
        state.setdefault('dbt', {})[args.registrar_dbt] = {'elapsed_time': raw['elapsed_time'],
            'conteo': len(results), 'estados': {status: sum(r['status']==status for r in results)
                for status in sorted({r['status'] for r in results})},
            'resultados': [{'unique_id': r['unique_id'], 'status': r['status']} for r in results]}
    if args.snapshot:
        with connect() as conn:
            state.setdefault('idempotencia', {})[args.snapshot] = fingerprints(conn)
    STATE.write_text(json.dumps(state, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
    if args.report:
        with connect() as conn:
            report = metricas(conn)
        report['fecha_verificacion'] = datetime.now(ZoneInfo('America/Guatemala')).isoformat(timespec='seconds')
        report.update(state)
        snapshots = state.get('idempotencia', {})
        report['idempotencia_igual'] = bool(snapshots.get('antes')) and snapshots.get('antes') == snapshots.get('despues')
        assert report['idempotencia_igual'], 'Los snapshots de negocio no coinciden o faltan'
        output = ROOT / 'docs/metricas/validacion_fase2.json'
        output.write_text(json.dumps(report, ensure_ascii=False, indent=2, default=str)+'\n', encoding='utf-8')
        print(json.dumps({k:v for k,v in report.items() if k not in {'dbt','idempotencia'}}, ensure_ascii=False, indent=2, default=str))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
