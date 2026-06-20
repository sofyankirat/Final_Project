#!/usr/bin/env python3
"""Set GitHub Actions secrets from a .env file and trigger the Azure deploy workflow.

Usage examples:
  ./gh_secrets.py --env .env --repo sofyankirat/Final_Project

Requirements:
  - `gh` (GitHub CLI) installed and authenticated (`gh auth login`).

This script prefers the `gh` CLI because it handles secret encryption for you.
"""
import argparse
import subprocess
import sys
from pathlib import Path


def parse_env(path: Path):
    values = {}
    with path.open() as f:
        for line in f:
            s = line.strip()
            if not s or s.startswith('#'):
                continue
            if '=' in s:
                k, v = s.split('=', 1)
                values[k.strip()] = v.strip().strip('"').strip("'")
    return values


def gh_available():
    from shutil import which
    return which('gh') is not None


def set_secret_gh(repo: str, name: str, value: str):
    cmd = ['gh', 'secret', 'set', name, '--repo', repo, '--body', value]
    print(f"Setting secret {name} in {repo}...")
    return subprocess.run(cmd)


def run_workflow(repo: str, workflow_file: str, ref: str = 'main'):
    cmd = ['gh', 'workflow', 'run', workflow_file, '--repo', repo, '--ref', ref]
    print(f"Triggering workflow {workflow_file} on {repo}@{ref}...")
    return subprocess.run(cmd)


def main():
    p = argparse.ArgumentParser(description='Set GitHub Actions secrets from .env and run workflow')
    p.add_argument('--env', default='.env', help='Path to .env file (KEY=VALUE lines)')
    p.add_argument('--repo', default='sofyankirat/Final_Project', help='GitHub repo (owner/repo)')
    p.add_argument('--workflow', default='azure-deploy.yml', help='Workflow filename under .github/workflows')
    p.add_argument('--trigger', action='store_true', help='Trigger the workflow after setting secrets')
    args = p.parse_args()

    env_path = Path(args.env)
    if not env_path.exists():
        print(f"Env file not found: {env_path}")
        sys.exit(2)

    values = parse_env(env_path)
    if not values:
        print("No secrets found in env file.")
        sys.exit(0)

    if not gh_available():
        print("Error: `gh` CLI not found. Install from https://cli.github.com/ and run `gh auth login`.")
        sys.exit(3)

    # Which secrets to set — common names used by the repo's workflows
    wanted = [
        'SUPABASE_URL', 'SUPA_PASS', 'SUPA_SERVICE_ROLE_KEY', 'SUPABASE_PUBLISHABLE_KEY',
        'AZURE_WEBAPP_NAME', 'AZURE_WEBAPP_PUBLISH_PROFILE'
    ]

    for k in wanted:
        if k in values:
            res = set_secret_gh(args.repo, k, values[k])
            if res.returncode != 0:
                print(f"Failed to set {k} (exit {res.returncode})")
        else:
            print(f"Warning: {k} not found in {env_path}")

    if args.trigger:
        res = run_workflow(args.repo, args.workflow)
        if res.returncode != 0:
            print(f"Workflow trigger failed (exit {res.returncode})")


if __name__ == '__main__':
    main()
