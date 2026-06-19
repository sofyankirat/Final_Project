#!/usr/bin/env python3
"""Export SQLite tables used by the Flask app into CSV files for import."""
import sqlite3
import csv
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FRONTEND = ROOT / 'front-end'
DB_NAME = os.getenv('DB_NAME', 'student_system')
# Try explicit path first, then discover any .db file under front-end
candidate = FRONTEND / f"{DB_NAME}.db"
if candidate.exists():
    DB_PATH = candidate
else:
    # discover any .db in front-end
    dbs = list(FRONTEND.glob('*.db'))
    DB_PATH = dbs[0] if dbs else candidate

OUT_DIR = Path(__file__).resolve().parents[0] / 'csvs'
OUT_DIR.mkdir(parents=True, exist_ok=True)

TABLES = [
    'users',
    'attendance',
    'courses',
    'recommendations',
    'user_additional_info',
    'user_ai_chat_state',
    'user_recommendation_history',
    'help_requests',
    'user_course_schedule',
    'user_tasks'
]


def export_table(conn, table, outdir):
    cur = conn.cursor()
    try:
        cur.execute(f'SELECT * FROM {table}')
    except Exception as e:
        print(f"Skipping {table}: {e}")
        return
    rows = cur.fetchall()
    cols = [d[0] for d in cur.description]
    out_path = outdir / f"{table}.csv"
    with open(out_path, 'w', newline='', encoding='utf-8') as fh:
        writer = csv.writer(fh)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([str(x) if x is not None else '' for x in r])
    print(f"Exported {table} -> {out_path}")


def main():
    if not DB_PATH.exists():
        print(
            f"Database not found at {DB_PATH}. No SQLite DB to export. You can skip export or run app to create DB.")
        return
    conn = sqlite3.connect(str(DB_PATH))
    for t in TABLES:
        export_table(conn, t, OUT_DIR)
    conn.close()
    print(f"All exports written to {OUT_DIR}")


if __name__ == '__main__':
    main()
