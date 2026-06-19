#!/usr/bin/env python3
"""Convert face-embedding pickle DB to JSONL for import.

Writes `embeddings.jsonl` with objects: {"name": NAME, "embedding": [f0,f1,...]}
If pgvector is available in destination, a separate script will convert JSON to vector rows.
"""
import os
import sys
import pickle
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SAS_DIR = ROOT / 'Smart-Attendance-System'

# Try to import Smart-Attendance-System config; otherwise default to database/database.pkl
DB_PATH = SAS_DIR / 'database' / 'database.pkl'
try:
    if str(SAS_DIR) not in sys.path:
        sys.path.insert(0, str(SAS_DIR))
    import config as sa_config
    DB_PATH = Path(sa_config.DATABASE_PATH)
except Exception:
    # fallback: keep DB_PATH as default
    pass
OUT_DIR = Path(__file__).resolve().parents[0] / 'csvs'
OUT_DIR.mkdir(parents=True, exist_ok=True)
OUT_FILE = OUT_DIR / 'embeddings.jsonl'


def load_pickle(path):
    if not path.exists():
        print(f"Embeddings DB not found at {path}")
        return {}
    with open(path, 'rb') as fh:
        data = pickle.load(fh)
    return data


def main():
    data = load_pickle(DB_PATH)
    if not data:
        print("No embeddings to export.")
        return
    with open(OUT_FILE, 'w', encoding='utf-8') as fh:
        for name, emb in data.items():
            arr = None
            try:
                import numpy as _np
                arr = _np.array(emb, dtype=float).tolist()
            except Exception:
                try:
                    arr = list(emb)
                except Exception:
                    arr = []
            obj = {"name": name, "embedding": arr}
            fh.write(json.dumps(obj) + '\n')
    print(f"Wrote embeddings JSONL to {OUT_FILE}")


if __name__ == '__main__':
    main()
