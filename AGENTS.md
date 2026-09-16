# AGENTS.md — sd43.ru (Сфера Дизайна)

Instructions for AI agents and developers working in this repository.

## What This Project Is

A Django monolith that runs the **Сфера Дизайна** exhibition platform for the
design company «Арт-Сервис» (sd43.ru). It is a **server-rendered** site: Django
templates plus a small amount of vanilla JS/jQuery. There is no SPA, no REST
framework and no separate frontend application.

Two audiences share one codebase:

1. **Main site** (`sd43.ru`) — exhibitions, portfolio, nominations, winners, jury,
   partners, blog, ratings, banners.
2. **Designer sub-sites** (`<slug>.sd43.ru`) — personal designer pages, served by
   the same Django project through `designers.middleware.SubdomainMiddleware`.

## Required Before Any Work

1. Read `.agent/index.md` — project map, module docs, lessons, ADRs.
2. Read `.agent/task.md` and `.agent/state.json` if they exist (active task state).
3. Read `README.md` for the domain overview and `BUILD.md` for the asset pipeline.
   Both predate parts of the current stack — see *Known Stale Docs*.

## Commands

Python — **always use the repo venv** (`venv/`), never a system interpreter:

```bash
./venv/bin/python manage.py check
./venv/bin/python manage.py migrate
./venv/bin/python manage.py runserver 9000
./venv/bin/python manage.py collectstatic --noinput
```

`DEBUG=true` in `.env` makes `DOMAIN_URL` point at `http://localhost:9000`, so run
the dev server on port **9000** to keep links and sub-site URLs consistent.

Frontend — the pipeline is **esbuild**, driven by `build.mjs`:

```bash
npm run build        # production: minified, no sourcemaps -> static/
npm run build:dev    # development: sourcemaps
npm run watch:dev    # rebuild on change — use while developing
```

Deployment is CI-driven (`.github/workflows/main.yml`). Read
`.agent/modules/deployment.md` before touching anything deployment-related.

## Code Conventions

- **Python indentation: match the file you are editing.** Tabs are the predominant
  style across the apps, but `exhibition/cache.py`, `manage.py` and the `apps.py` of
  `ads`/`designers` use 4 spaces. No file mixes the two — never "fix" indentation in
  a file you are not otherwise changing.
- One app per package, `snake_case` for functions and modules, `PascalCase` for model
  and view classes. Model names are mostly **plural** (`Categories`, `Nominations`,
  `Exhibitions`, `Winners`, `Partners`) — follow the surrounding app rather than
  "fixing" it.
- Query and business logic lives on custom managers (`PersonManager`,
  `PortfolioManager`, `DesignerManager`) or in `exhibition/logic.py`,
  `exhibition/services.py`, `exhibition/cache.py`. Put new logic there, not in views.
- Templates are **global** in `templates/<app>/`; `APP_DIRS` is enabled but per-app
  `templates/` folders are not used by the main apps.
- SASS lives in `src/sass/`: `_`-prefixed files are partials and are excluded from
  entry-point discovery. `src/sass/main/*` and `src/sass/designer/*` are partials;
  the root `.sass` files and `src/sass/admin/*` are entry points.
- Admin styling compiles to a **separate** output tree (`static/admin/css`,
  `static/admin/js`) so it loads independently of the public site.
- JS/SASS entry naming: `name.js` → `name.min.js`. Keep the `.min` suffix when
  adding an entry point.

## Git & Commits

- Conventional Commits, English: `fix:`, `feat:`, `upd:`, `refactor:`, `chore:`.
  Older history mixes `feat:`/`upd:`/free text — prefer the conventional form.
- Single long-lived branch: `master`. CI runs on push and PR to `master` and
  **deploys on push**, so every merge to master is a production release.
- Version has one source of truth: `crm/project.py` (`VERSION`), exposed to
  templates by the `site_version` tag in `exhibition/templatetags/custom_tags.py`.
  `package.json` carries its own version that has drifted — update
  `crm/project.py`, never treat `package.json` as authoritative.
- Never commit `.env` or `prod.env`, and never paste their contents into issues,
  docs or `.agent/`. See *Security Constraints*.

## Non-Obvious Gotchas

These traps cost time. They are invariants, not preferences.

1. **`migrations/` is gitignored and excluded from rsync.** Local migration files
   exist on disk but are *not* tracked and *not* shipped. The server generates them:
   `.deploy/deployment_script.sh` runs `makemigrations --noinput` then `migrate`.
   Consequence: writing a migration locally does not deploy it. A model change must
   be something the server can derive the same migration from, and a manual data
   migration needs a different delivery mechanism entirely.
2. **`static/*` is gitignored, so built assets are mostly not in git.** CI builds
   them (`npm run build`) and rsyncs `static/` to the server. Deliberate exceptions
   that *are* tracked: `static/designers/**`, `static/fonts/`, `static/favicons/`.
   Two legacy artifacts, `static/css/base.min.css` and `static/js/base.min.js`, were
   committed before the ignore rule and remain tracked, so a local build dirties them.
3. **`DEBUG` parsing is strict.** `.env` uses `DEBUG=true`; `prod.env` uses
   `DEBUG=off`. Settings compares the lowercased value against `'true'`, so only the
   literal `true` enables debug mode (`off`, `False`, `0` all mean production).
4. **Production database is PostgreSQL, not MySQL.** `prod.env` keeps MySQL URLs as
   commented history. `DATABASE_URL` is parsed by `dj-database-url`; local dev
   defaults to SQLite (`db.sqlite3` in the repo root).
5. **Subdomain detection depends on the Sites framework.** `SubdomainMiddleware`
   reads `Site.objects.get_current().domain` (SITE_ID = 1) to decide whether a host
   is a subdomain, and also honours an `X-Subdomain` header (set by nginx). If the
   `Site` row does not contain the real domain, designer sub-sites silently stop
   resolving and `request.designer` becomes `None` everywhere.
6. **Thumbnails need Redis.** `THUMBNAIL_KVSTORE` points at the sorl Redis kvstore,
   so a missing or unreachable `THUMBNAIL_REDIS_URL` breaks image rendering, not
   just caching. Templates rely on sorl everywhere.
7. **`STATICFILES_STORAGE` was removed from settings (2026-09-16).** Django 5.x has
   no such setting — the effective storage comes from `STORAGES['staticfiles']`
   (plain `StaticFilesStorage`), and nginx serves `static/` in production. Verify
   the effective class instead of assuming:
   `./venv/bin/python -c "import os,django;os.environ.setdefault('DJANGO_SETTINGS_MODULE','crm.settings');django.setup();from django.contrib.staticfiles.storage import staticfiles_storage;print(type(staticfiles_storage))"`
8. **`DJANGORESIZED_*` settings are live custom config** — the `django-resized`
   package is NOT installed, but `exhibition/logic.py::process_image` reads these
   values as its defaults (quality 80, size 1200×900, keep_meta False). Removing
   them as "dead code" silently changes image processing.
9. **`requirements.txt` is not a complete snapshot of `venv/`** (e.g. `whitenoise`
   is importable from `venv/` but not pinned — nothing imports it since the
   `STATICFILES_STORAGE` removal). Re-derive drift before relying on it to build
   a fresh environment.

## Security Constraints

- `SECRET_KEY`, DB credentials, SMTP credentials and Yandex SmartCaptcha keys are
  real production secrets inside `.env` / `prod.env`. Both files are gitignored —
  keep it that way. `prod.env` duplicates the real secret key; rotating secrets
  happens on the server, not in the repo.
- The production `.env` is delivered by the `PROD_ENV_FILE` GitHub secret and
  written with `chmod 600` by CI. Never add a committed `.env.example` holding real
  values.
- `external_nginx.conf` is never committed (global policy).
- Production runs over HTTPS and `DEBUG` must stay off there.

## Documentation Layout

- `.agent/index.md`, `.agent/modules/`, `.agent/lessons/`, `.agent/decisions/` —
  agent knowledge, **tracked in git** (shared across machines and CI).
- `.agent/task.md`, `.agent/state.json`, `.agent/plans/`, `.agent/archive/` —
  ephemeral session state, gitignored.
- `README.md`, `BUILD.md` — human-facing docs at the repo root.
- `.gitignore` also ignores `docs/` and `resources/`, so `docs/` cannot currently
  be committed; `resources/` holds source design assets (PDFs, logos, backups) that
  are intentionally not in git.

### Known Stale Docs

`README.md` and `BUILD.md` describe an older stack. Do not trust these claims:

| Claim in docs | Reality |
|---|---|
| Django 4.x | Requirements pin Django 5.x — check `requirements.txt` |
| Gulp task runner, `gulpfile.js` | Replaced by `build.mjs` (esbuild); no gulpfile exists |
| MySQL 5.7+ as the database | Production is PostgreSQL; MySQL lines are commented-out history |
| Python 3.8+, Node 14+ | Local venv is Python 3.12, CI uses Node 22 |
| `pip install -r requirements.txt` | Local work uses the checked-in `venv/`; that file is incomplete |

Fix these in `README.md` when you touch a feature they describe, instead of
duplicating them into agent docs.
