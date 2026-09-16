# Module: Deployment

**Created:** 2026-09-16
**Last Updated:** 2026-09-16
**Status:** Active

## Description

Production runs on a single server (`/home/starck/domains/sd43.ru`, user `starck`):
nginx terminates TLS, gunicorn serves `crm.wsgi:application` over a unix socket, and
migrations/collectstatic run during deploy. Delivery is fully automated from GitHub
Actions on every push to `master` — **there is no staging environment**.

## Pipeline

`.github/workflows/main.yml` (`sd43 CI/CD`), triggered by push/PR to `master` and by
`workflow_dispatch`:

1. Checkout, SSH agent (`SSH_PRIVATE_KEY`), `ssh-keyscan` of `SSH_HOST`.
2. `npm ci` + `npm run build`, then a guarded check that `static/js` or `static/css`
   exist.
3. **Separate `rsync static/` to `$REMOTE_DIR/static/`** — no `--delete`, no excludes.
4. `rm -rf node_modules package-lock.json` (to keep the uploaded payload small).
5. Generate `.deploy/rsync_exclude.txt` (`.git/`, `.github/`, `*.md`, `*.jpg`, plus
   `find`-derived migration paths).
6. Write `.env` on the server from the `PROD_ENV_FILE` secret, `chmod 600`.
7. Main `rsync -avz --delete --exclude-from=.gitignore --exclude-from=.deploy/rsync_exclude.txt ./ $REMOTE_DIR/`
   with `--chmod=Du=rwx,Dg=rx,Do=rx,Fu=rw,Fg=r,Fo=r`.
8. `bash .deploy/deployment_script.sh sd43 $REMOTE_DIR <admin email> <admin user> <admin password>`.
9. Verify `sd43.service` is active and `/run/gunicorn/sd43.sock` exists.

### Required repository configuration

Secrets: `SSH_PRIVATE_KEY`, `PROD_ENV_FILE`, `DJANGO_ADMIN_PASSWORD`.
Variables: `SSH_USER`, `SSH_HOST`, `DJANGO_ADMIN_EMAIL`, `DJANGO_ADMIN_SUPERUSER`.
`PROJECT_NAME`/`DOMAIN_NAME`/`NODE_VERSION` are set in the workflow itself.

## deployment_script.sh

Runs **on the server**, `set -e`:

- Verifies `.env` exists and contains `ALLOWED_HOSTS` / `DJANGO_SECRET_KEY`.
- Creates `media`, `static`, `media/site`, `logs`, `temp` and chowns the tree.
- Installs `gunicorn.service` and `gunicorn.socket` from `.deploy/` (and installs the
  nginx config **only if it does not already exist** — see gotchas).
- Creates the venv if missing (`python3.12 -m venv`), always runs
  `pip install -r requirements.txt --upgrade`.
- Runs `makemigrations --noinput`, `migrate --noinput`, `collectstatic --noinput`;
  creates the superuser only on first run.
- `systemctl restart sd43.service` and prints its status.

Note it runs `makemigrations` **on the server** and that `collectstatic` runs with
`DEBUG=off`, so `STATIC_ROOT` (the same `static/` tree nginx serves) is the target.
This is why local migration files never ship — see `AGENTS.md` gotcha #1.

## Topology

| Piece | Value |
|---|---|
| systemd units | `sd43.service`, `sd43.socket` (socket-activated, mode 0660, `RuntimeDirectory=gunicorn`) |
| Gunicorn | `crm.wsgi:application`, 3 workers, `--bind unix:/run/gunicorn/sd43.sock`, access log to stdout |
| nginx upstream | `sd43_app` → `unix:/run/gunicorn/sd43.sock` |
| Static/media aliases | `/static` → `$REMOTE_DIR/static`, `/media` → `$REMOTE_DIR/media` |
| Main hosts | `sd43.ru`, `www.sd43.ru` (also `favicon.ico`, `/500.html` locations) |
| Subdomain block | `server_name ~^(?<subdomain>[a-z0-9-]+)\.sd43\.ru$`, sets `X-Subdomain`, aliases `/static/designers` to `static/designers/$subdomain` |
| Deploy user | `starck` (also owns the units' `User`/`Group`) |
| Python on server | 3.12 |

Logs: `sudo journalctl -u sd43.service -f`.

## Gotchas

- **nginx config changes in the repo do not propagate.** `setup_system_services`
  skips `/etc/nginx/sites-available/sd43.ru` when the file already exists. Editing
  `.deploy/nginx.conf` affects only a brand-new server; existing servers must be
  updated by hand (which is also why the site-specific `external_nginx.conf` is kept
  out of git).
- **`.gitignore` is reused as an rsync exclude file**, so `--delete` protects excluded
  paths but gitignore *negation* lines (`!static/designers/**`, `!media/site/**`) are
  **not** valid rsync syntax and are treated as literal patterns that never match.
  Practical effect: the main sync does not push `static/designers/**`; only the
  dedicated `rsync static/` step (which passes no excludes) does. Do not remove that
  step, and re-verify on the server after any change to the static ignore rules.
- **The early `static/` rsync has no `--delete`**, so files deleted from the repo stay
  on the server forever. Clean them up manually when removing assets.
- **`media/` is never synced** — no CI step rsyncs it and `.gitignore` excludes
  `media/*`. The fallback images tracked in git (`media/site/default-image.webp`,
  `no-image*`, `no-person.png`) must already exist on the server; CI will not create
  them. Verify on the server after any media-path change.
- **`*.md` is excluded from the rsync**, so `AGENTS.md` / `.agent/` knowledge is never
  deployed (`.agent/*` is also gitignored except the tracked knowledge files). Nothing
  on the server depends on them.
- **`--delete` plus a `.gitignore`-derived exclude list is fragile.** Any new ignore
  rule silently changes what the deploy deletes or keeps. Review `.gitignore` changes
  with the deploy in mind.
- **Deploys are not atomic and not rollback-capable** from CI — the script restarts
  gunicorn in place. Recovering from a bad release means reverting `master` and
  pushing again.
- The workflow runs on `pull_request` too, and every step (including deploy) is
  unconditional — treat any PR to `master` as touching production.
