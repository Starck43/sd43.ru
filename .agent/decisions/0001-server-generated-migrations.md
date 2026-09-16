# ADR 0001: Migrations are generated on the server

- **Status:** Accepted
- **Date:** 2026-09-16
- **Scope:** Deployment / database schema management

## Context

Model migrations are not stored in git: `migrations/` of every app is in
`.gitignore`, and the rsync deployment uses that same `.gitignore` as its
exclude list — so locally generated migration files never reach the server.
Instead, `.deploy/deployment_script.sh` runs `manage.py makemigrations --noinput`
followed by `manage.py migrate --noinput` on the server on every deploy.

## Decision

Keep migration generation on the server. The server-side `makemigrations` run
is the single source of truth for schema changes.

## Consequences

- Model changes in a PR are not accompanied by migration files; the schema
  change is applied on the first deploy after merge. Predict it locally with
  `manage.py makemigrations --check --dry-run --verbosity 3` before pushing.
- The local `migrations/` directory is machine-local scratch state; it is safe
  to delete and regenerates.
- Because `.gitignore` doubles as the rsync exclude list, **any new ignore
  entry also excludes files from deployment**, and rsync negation (`!`) does
  not work. See `.agent/modules/deployment.md`.
- Never rely on tracked files under ignored `migrations/` paths — they are
  silently absent on the server.

## Alternatives considered

- **Track migrations in git** (standard Django practice) — rejected for now:
  requires removing `migrations/` from both `.gitignore` and the effective
  rsync exclude set, plus a one-time reconciliation of server-generated state
  with developer machines. Revisit if multiple developers change models
  concurrently.
