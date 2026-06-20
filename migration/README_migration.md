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

Azure Deployment & GitHub Actions
---------------------------------

This repo includes a GitHub Actions workflow `.github/workflows/azure-deploy.yml` that:
- runs the migration scripts on a GitHub runner (needs network access to Supabase), then
- builds a Docker image and deploys it to an Azure Web App for Containers using a publish profile.

Required GitHub Secrets (set these in Settings → Secrets → Actions):
- `SUPABASE_URL` — your Supabase project URL (e.g. https://...supabase.co)
- `SUPA_PASS` — Postgres password for the `postgres` user (used by migration script)
- `SUPA_SERVICE_ROLE_KEY` — Supabase service role key (admin key for Storage & extensions)
- `SUPABASE_PUBLISHABLE_KEY` — Supabase anon/publishable key (used by the app where needed)
- `AZURE_WEBAPP_NAME` — the name of your Azure Web App for Containers
- `AZURE_WEBAPP_PUBLISH_PROFILE` — Azure publish profile XML (download from Azure Portal)

How to get the Azure publish profile
1. Open the Azure Portal and navigate to your Web App resource.
2. In the Overview page, click "Get publish profile" and download the XML file.
3. Open the XML file and copy its contents into the `AZURE_WEBAPP_PUBLISH_PROFILE` secret value.

Triggering the workflow
- Manually: go to the Actions tab → select "Build, Migrate and Deploy to Azure Web App (Container)" → Run workflow.
- Automatically: push to `main`.

Notes & recommendations
- The GitHub runner will run the migration using the secrets — do not store service-role keys in the repository. Keep your secrets rotated and restricted.
- Because the codebase includes heavy ML dependencies, consider splitting the attendance/ML pipeline into a separate service (VM or container) if build times or image size become problematic.

