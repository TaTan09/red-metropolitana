#!/usr/bin/env python3
"""Provisiona permisos Gold; habilita LOGIN sólo con TABLEAU_RO_PASSWORD externo."""
import os
from pathlib import Path

import psycopg
from psycopg import sql
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


def main() -> int:
    load_dotenv(ROOT / '.env')
    password = os.getenv('TABLEAU_RO_PASSWORD')
    if password is not None and len(password) < 16:
        raise ValueError('TABLEAU_RO_PASSWORD requiere al menos 16 caracteres')
    with psycopg.connect(
        host=os.getenv('POSTGRES_HOST', 'localhost'),
        port=os.getenv('POSTGRES_PORT', '5432'),
        dbname=os.environ['POSTGRES_DB'], user=os.environ['POSTGRES_USER'],
        password=os.environ['POSTGRES_PASSWORD'], connect_timeout=10,
    ) as conn:
        conn.execute((ROOT / 'sql/security/tableau_ro.sql').read_text(encoding='utf-8'))
        if password is not None:
            conn.execute(sql.SQL('ALTER ROLE tableau_ro LOGIN PASSWORD {}').format(sql.Literal(password)))
        can_login = conn.execute("SELECT rolcanlogin FROM pg_roles WHERE rolname='tableau_ro'").fetchone()[0]
    print(f'Permisos Gold provisionados. LOGIN={can_login}. No se cambió la conexión Tableau.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
