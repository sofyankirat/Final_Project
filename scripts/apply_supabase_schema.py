#!/usr/bin/env python3
import os
import sys
from urllib.parse import urlparse, quote_plus
import psycopg2
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SQL_FILE = ROOT / 'migration' / 'supabase_schema.sql'

if not SQL_FILE.exists():
    print('Schema file not found:', SQL_FILE)
    sys.exit(1)

SUPABASE_URL = os.getenv('SUPABASE_URL')
DB_PASS = os.getenv('SUPA_PASS') or os.getenv('SUPA-PASS')
# fallback to .env
envf = ROOT / '.env'
if envf.exists():
    for ln in envf.read_text(encoding='utf-8').splitlines():
        if not SUPABASE_URL and ln.strip().startswith('SUPABASE_URL'):
            SUPABASE_URL = ln.split('=', 1)[1].strip().strip('"\'')
        if not DB_PASS and (ln.strip().startswith('SUPA-PASS') or ln.strip().startswith('SUPA_PASS')):
            DB_PASS = ln.split('=', 1)[1].strip().strip('"\'')

if not SUPABASE_URL or not DB_PASS:
    print('Missing SUPABASE_URL or SUPA_PASS. Provide in environment or .env')
    sys.exit(2)

parsed = urlparse(SUPABASE_URL)
netloc = parsed.netloc
db_host = netloc if netloc.startswith('db.') else 'db.' + netloc
enc = quote_plus(DB_PASS)
conn_str = f"postgresql://postgres:{enc}@{db_host}:5432/postgres?sslmode=require"

print('Connecting to', db_host)
try:
    conn = psycopg2.connect(conn_str)
    cur = conn.cursor()
    sql = SQL_FILE.read_text(encoding='utf-8')
    print('Applying schema SQL...')
    cur.execute(sql)
    conn.commit()
    cur.close()
    conn.close()
    print('Schema applied successfully.')
except Exception as e:
    print('Schema apply failed:', e)
    sys.exit(3)
