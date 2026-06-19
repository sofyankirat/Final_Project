#!/usr/bin/env python3
"""Upload static files and model artifacts to Supabase Storage (requires service role key).

Uses `supabase` Python client when `SUPA_SERVICE_ROLE_KEY` is set.
"""
import os
from pathlib import Path

try:
    from supabase import create_client
except Exception:
    create_client = None

ROOT = Path(__file__).resolve().parents[1]
STATIC_UPLOADS = ROOT / 'front-end' / 'app' / 'static' / 'uploads'
MODELS_DIR = ROOT / 'front-end' / 'models'

SUPABASE_URL = os.getenv('SUPABASE_URL')
SERVICE_KEY = os.getenv('SUPA_SERVICE_ROLE_KEY')


def upload_dir(client, bucket, src_dir: Path):
    if not src_dir.exists():
        print(f"No files in {src_dir}")
        return
    for p in src_dir.rglob('*'):
        if p.is_file():
            key = str(p.relative_to(src_dir))
            with open(p, 'rb') as fh:
                print(f"Uploading {p} -> {bucket}/{key}")
                res = client.storage.from_(bucket).upload(key, fh)
                print(res)


def main():
    if not SUPABASE_URL or not SERVICE_KEY:
        print('SUPABASE_URL or SUPA_SERVICE_ROLE_KEY not set. Upload skipped.')
        return
    if create_client is None:
        print('supabase package not installed. Run `pip install supabase`')
        return

    client = create_client(SUPABASE_URL, SERVICE_KEY)

    # Ensure buckets exist (you may create them in dashboard manually)
    # This will attempt to upload to 'uploads' and 'models' buckets.
    upload_dir(client, 'uploads', STATIC_UPLOADS)
    upload_dir(client, 'models', MODELS_DIR)


if __name__ == '__main__':
    main()
