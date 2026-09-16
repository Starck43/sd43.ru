# Module: crm — Project Configuration

**Created:** 2026-09-16
**Last Updated:** 2026-09-16
**Status:** Active

## Description

The Django project package. It holds no domain models (`crm/models.py` is empty) —
only configuration, cross-cutting middleware, context processors and shared helpers.
Every other module depends on it, so changes here have the widest blast radius.

## Structure

| File | Responsibility |
|---|---|
| `settings.py` | Single settings module; imports `crm/project.py`, then layers env vars over it |
| `project.py` | `VERSION` and `TITLE` constants — version source of truth, consumed by templates |
| `urls.py` | Root URLconf: admin, allauth, `designers/`, and the `exhibition`/`rating`/`blog` includes at root |
| `middleware.py` | `AjaxMiddleware`, `FixPermissionMiddleware` |
| `context_processors.py` | `common_context`, `yandex_captcha` — injected into every template |
| `captcha.py` | Yandex SmartCaptcha verification |
| `validators.py` | Shared form/file validators |
| `wsgi.py` / `asgi.py` | Entrypoints; production serves `crm.wsgi:application` via gunicorn |

## Configuration Notes

### Layering

`settings.py` does **not** use a settings-package split (no `base/dev/prod` modules).
Environment differences come purely from the env file: `.env` for local work,
`prod.env` supplied by CI as `.env` on the server. `DJANGO_SETTINGS_MODULE` is always
`crm.settings`.

### Conditional wiring

`INSTALLED_APPS`, `MIDDLEWARE` and `urlpatterns` are mutated at import time when
`DEBUG` is truthy: debug toolbar, `__debug__/` URLs and the media static route are
added only in debug. Any new conditional import must stay inside that block so
production never imports dev-only packages.

### Static files

`STATICFILES_STORAGE` was removed from settings (2026-09-16) — in Django 5.x the
setting does not exist; the effective storage is `STORAGES['staticfiles']`
(plain `StaticFilesStorage`, see `AGENTS.md` gotcha #7). Also note `STATIC_ROOT`
and `STATICFILES_DIRS` both point at `static/`, chosen by `DEBUG` — in production
`collectstatic` writes into the same tree nginx serves.

### Caching

Redis is the only cache backend (`REDIS_URL`, default db 0). Django's
`FetchFromCacheMiddleware` is enabled, and templates use fragment caching; invalidation
goes through `exhibition/services.py` (`delete_cached_fragment`) and
`exhibition/cache.py` (`invalidate_portfolio_cache`). The
`clear_template_cache --all` management command exists to flush fragments by name when
a deploy changes template structure.

### Email

Parsed from a single `EMAIL_URL` DSN. If it is empty, `EMAIL_BACKEND` is left at the
Django default (console) — useful locally, silent in production if the variable is
missing. `EMAIL_RECIPIENTS` also feeds `ADMINS`.

### i18n

`LANGUAGE_CODE = ru-RU`, `TIME_ZONE = Europe/Moscow`, `USE_TZ = True`. All
user-facing strings are Russian and live directly in templates — there is no
translation catalog workflow in this project, so do not introduce `{% trans %}` for
new copy.

## Middleware

- **`AjaxMiddleware`** — re-attaches an `is_ajax()` method to every request (the
  pre-1.0 Django API that was removed upstream). Views still call `request.is_ajax()`;
  keep the middleware if you touch those views.
- **`FixPermissionMiddleware`** — on `/admin/` paths it monkey-patches
  `ContentType.__str__` and `Permission.__str__` to work around broken admin
  rendering of permission names. It mutates global class state during the request and
  restores it in `process_response`; it is process-wide and not thread-safe by design.
- **`designers.middleware.SubdomainMiddleware`** — resolves the current designer;
  documented in [designers-subdomains](designers-subdomains.md).

## Dependencies

### Internal

- All apps — everything imports settings, and model code relies on `TITLE`/`VERSION`
  templates via the `site_version` tag.

### External

`django-jazzmin` (admin theme), `django-allauth` (auth), `django-ckeditor`
(rich text), `sorl-thumbnail`, `django-watson` (search),
`django-smart-selects` (dependent admin dropdowns), `crispy-forms` + bootstrap5 pack,
`django-cleanup` (removes files when model rows are deleted), `dj-database-url`,
`python-dotenv`.

## Gotchas

- Admin ordering and icons are hard-coded in `JAZZMIN_SETTINGS.order_with_respect_to`
  and `.icons`. Renaming a model silently drops it from that ordering.
- `DOMAIN_URL` is derived from `DEBUG` and the first `ALLOWED_HOSTS` entry — it is the
  value used in the admin "go to site" link, not the request host.
