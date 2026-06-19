#!/usr/bin/env python3
"""Import CSVs and embeddings into Supabase/Postgres.

Reads `migration/csvs/` produced by export scripts and loads into target Postgres
using connection from environment variables: `SUPABASE_URL` and `SUPA-PASS`.

If pgvector is available the script will attempt to insert embeddings into `embeddings`.
Otherwise embeddings.jsonl will be loaded into `embeddings_json` as jsonb.
"""
import os
import sys
import psycopg2
from urllib.parse import urlparse, quote_plus
from pathlib import Path
import json

ROOT = Path(__file__).resolve().parents[1]
CSV_DIR = ROOT / 'migration' / 'csvs'
SCHEMA_SQL = ROOT / 'migration' / 'supabase_schema.sql'

SUPABASE_URL = os.getenv(
    'SUPABASE_URL', 'https://qktibkgpqnxbipmvsopd.supabase.co')
DB_PASS = os.getenv('SUPA_PASS') or os.getenv('SUPA-PASS')
env_file = Path(ROOT) / '.env'
if not DB_PASS and env_file.exists():
    for ln in env_file.read_text(encoding='utf-8').splitlines():
        if ln.strip().startswith('SUPA-PASS') or ln.strip().startswith('SUPA_PASS'):
            parts = ln.split('=', 1)
            if len(parts) == 2:
                DB_PASS = parts[1].strip().strip('"\'')

if not DB_PASS:
    print('SUPA-PASS not set in environment (.env). Aborting.')
    sys.exit(1)

# Build psycopg2 dsn
parsed = urlparse(SUPABASE_URL)
if not DB_PASS:
    print('SUPA-PASS not set in environment or .env. Aborting.')
    sys.exit(1)
db_host = f"db.{parsed.netloc.split('.', 1)[1]}" if parsed.netloc.startswith(
    'qktibkgpqnxbipmvsopd') else parsed.netloc
# Fallback: use known host pattern if user provided full url
db_host = f"db.{parsed.netloc}" if not parsed.netloc.startswith(
    'db.') else parsed.netloc
enc_pass = quote_plus(DB_PASS)
conn_str = f"postgresql://postgres:{enc_pass}@{db_host}:5432/postgres?sslmode=require"


def run_schema(conn):
    with open(SCHEMA_SQL, 'r', encoding='utf-8') as fh:
        sql = fh.read()
    with conn.cursor() as cur:
        print('Applying schema...')
        cur.execute(sql)
    conn.commit()


def copy_csv(conn, table, csv_path):
    with conn.cursor() as cur:
        print(f'Copying {csv_path} -> {table} ...')
        with open(csv_path, 'r', encoding='utf-8') as fh:
            # Using COPY with header
            cur.copy_expert(
                sql=f"COPY {table} FROM STDIN WITH CSV HEADER", file=fh)
    conn.commit()


def load_embeddings_jsonl(conn, jsonl_path):
    # Decide target table: embeddings or embeddings_json
    with conn.cursor() as cur:
        cur.execute("SELECT to_regclass('public.embeddings')")
        emb_exists = cur.fetchone()[0]
        cur.execute("SELECT to_regclass('public.embeddings_json')")
        emb_json_exists = cur.fetchone()[0]

    if emb_exists:
        print('Importing embeddings into `embeddings` as vectors (requires pgvector).')
        # Try inserting as vector literal
        with conn.cursor() as cur, open(jsonl_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                obj = json.loads(line)
                name = obj.get('name')
                emb = obj.get('embedding', [])
                if not emb:
                    continue
                # Build vector literal like '[0.1,0.2,...]'
                vec_str = '[' + ','.join(str(float(x)) for x in emb) + ']'
                try:
                    cur.execute(
                        "INSERT INTO embeddings (name, embedding) VALUES (%s, %s::vector)", (name, vec_str))
                except Exception as e:
                    # Fallback: try using the SQL literal cast
                    cur.execute(
                        "INSERT INTO embeddings (name, embedding) VALUES (%s, %s)", (name, emb))
        conn.commit()
    elif emb_json_exists:
        print('Importing embeddings into `embeddings_json` as jsonb.')
        with conn.cursor() as cur, open(jsonl_path, 'r', encoding='utf-8') as fh:
            for line in fh:
                obj = json.loads(line)
                name = obj.get('name')
                emb = obj.get('embedding', [])
                cur.execute(
                    "INSERT INTO embeddings_json (name, embedding) VALUES (%s, %s::jsonb)", (name, json.dumps(emb)))
        conn.commit()
    else:
        print('No embeddings target table found. Skipping embeddings import.')


def main():
    if not CSV_DIR.exists():
        print(f"CSV dir not found: {CSV_DIR}. Run export script first.")
        return
    try:
        conn = psycopg2.connect(conn_str)
    except Exception as e:
        print(f"Failed to connect to Postgres: {e}")
        return

    try:
        run_schema(conn)
    except Exception as e:
        print(f"Schema apply error (continuing): {e}")

    # Map known CSVs to target tables (names match)
    for csv_file in CSV_DIR.glob('*.csv'):
        table = csv_file.stem
        try:
            copy_csv(conn, table, csv_file)
        except Exception as e:
            print(f"Failed importing {csv_file}: {e}")

    # Also import recommendation CSVs if present in repo (Courses/Professors)
    repo_courses = ROOT / 'Recommendation_System_Data' / 'Courses.csv'
    repo_prof = ROOT / 'Recommendation_System_Data' / 'Professors.csv'
    if repo_courses.exists():
        try:
            copy_csv(conn, 'courses', repo_courses)
        except Exception as e:
            print(f"Failed importing repo Courses.csv: {e}")
    if repo_prof.exists():
        try:
            copy_csv(conn, 'professors', repo_prof)
        except Exception as e:
            print(f"Failed importing repo Professors.csv: {e}")

    # Load embeddings JSONL if present
    jsonl = CSV_DIR / 'embeddings.jsonl'
    if jsonl.exists():
        try:
            load_embeddings_jsonl(conn, jsonl)
        except Exception as e:
            print(f"Embeddings import failed: {e}")

    conn.close()
    print('Import finished.')


if __name__ == '__main__':
    main()
