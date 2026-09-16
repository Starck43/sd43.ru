# 2026-09-16 — Post-init recommendations (docs refresh, ADR, dead-code cleanup)

## Task

Execute the recommendations from project initialization: refresh README/BUILD,
record the "migrations are generated on the server" ADR, remove dead code.

## What was done

- `crm/settings.py`: removed `STATICFILES_STORAGE` (inert in Django 5.x) and the
  commented-out WhiteNoise middleware line.
- `exhibition/models.py` + `exhibition/services.py`: removed the
  `update_google_sitemap` stub, its import and all 6 `save()` call sites
  (4 no-op `save()` overrides deleted entirely).
- `README.md`: rewritten to the real stack (Django 5.x, Postgres/SQLite via
  `DATABASE_URL`, esbuild instead of Gulp, Yandex Metrika instead of Google
  Analytics, real repo URL, env-var names, deploy flow; removed claims about
  `.env.example`, LICENSE file, REST API).
- `BUILD.md`: added Gotchas (build rewrites tracked legacy bundles;
  `static/css/swiper.min.css` is built from a JS import — do not delete;
  nginx serves static/media in prod).
- `ADR-0001`: server-generated migrations recorded in `.agent/decisions/`.
- Knowledge: `AGENTS.md` gotchas #7/#8/#9 corrected; modules `crm-config`,
  `frontend-assets`, `designers-subdomains`, `exhibition-app` updated.

## Lessons

- **Verify doc claims against code — including your own docs.** Gotcha #8 in
  `AGENTS.md` claimed `DJANGORESIZED_*` was inert; `exhibition/logic.py::
  process_image` actually reads them as defaults. The claim was corrected before
  it could cause a harmful cleanup.
- **Text-edit anchors must be read, not assumed.** Two model `Meta` blocks have
  fields *after* `db_table` (`ordering`, `unique_together`), so
  `db_table`-anchored old_text failed twice; save-block + following-method
  anchors worked.
- **State files that exist cannot be "created"** — `state.json` needed a full
  body replace, not an insert.
- Sitemap archaeology: the `update_google_sitemap` stub was once a real
  `ping_google()` call (see untracked `resources/backup/`). Google sunset the
  ping endpoint (Jan 2024) and Django removed the helper in 5.1 (deprecated in
  5.0) — removal is correct; sitemaps are still served live via
  `django.contrib.sitemaps`.

## Follow-ups

- [x] 2026-09-16: changes committed locally in four conventional commits
      (.gitignore `0bba32a`, refactor `55c5ed6`, docs `8dee895`, knowledge base).
      **Not pushed** — a push to `master` deploys to production.
- Revisit the migrations-in-git decision when a second developer touches models.
