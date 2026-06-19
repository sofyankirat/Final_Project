Migration to Supabase
=====================

Prereqs
- Add your Supabase DB password to `.env` as `SUPA-PASS`.
- (Optional but recommended) Add Supabase service role key as `SUPA_SERVICE_ROLE_KEY` for storage and to enable extensions.

Quick steps
1. Export SQLite and embeddings:
   ```bash
   python3 migration/export_sqlite_to_csv.py
   python3 migration/embeddings_to_jsonl.py
   ```
2. Create schema and import CSVs into Supabase:
   ```bash
   python3 migration/import_to_supabase.py
   ```
3. Upload model files / static uploads to Supabase Storage (requires service role key). See `migration/upload_to_storage.py`.

Notes
- Enabling `pgvector` (for storing face embeddings as vectors) requires a Supabase service role key. The import script will attempt to create the extension but will continue if it lacks permission and store embeddings as JSON instead.
- After data import you still need to update the app to connect to Postgres instead of SQLite. I can prepare code patches for that once you confirm.
