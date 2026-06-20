GH Secrets helper
=================

What this does
---------------

Small CLI to set GitHub Actions secrets from a local `.env` file and optionally trigger the Azure deployment workflow. It uses the `gh` CLI (GitHub CLI) so secret encryption is handled automatically.

Prerequisites
-------------
- Install `gh`: https://cli.github.com/
- Authenticate: `gh auth login`

Usage
-----

From the repository root:

```bash
./scripts/gh_secrets.py --env .env --repo sofyankirat/Final_Project --trigger
```

This will read keys from `.env` and set the commonly used secrets:

- SUPABASE_URL
- SUPA_PASS
- SUPA_SERVICE_ROLE_KEY
- SUPABASE_PUBLISHABLE_KEY
- AZURE_WEBAPP_NAME
- AZURE_WEBAPP_PUBLISH_PROFILE

If `gh` is not available, the script will print an error and exit. You can still set secrets manually in the GitHub repository settings.
