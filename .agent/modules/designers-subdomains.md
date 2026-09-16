# Module: designers — Subdomain Tenancy

**Created:** 2026-09-16
**Last Updated:** 2026-09-16
**Status:** Active

## Description

Gives every published designer a personal site at `<slug>.sd43.ru` — same Django
project, same templates tree, different content and per-designer static assets.
There is **no separate deployment per designer**; tenancy is resolved per request.

## Architecture

```
request -> nginx (subdomain regex server block)
        -> sets X-Subdomain + Host
        -> SubdomainMiddleware resolves request.subdomain / request.designer
        -> DesignerAccessMixin guards the view, sets self.object
        -> templates render, using designer_static / designer_url tags
```

### Request resolution

`designers/middleware.py::SubdomainMiddleware`:

1. Prefers the `X-Subdomain` header (nginx sets it — see `.deploy/nginx.conf`).
2. Otherwise compares `Host` against `Site.objects.get_current().domain`
   (SITE_ID = 1): a host with exactly one label more than the site domain is a subdomain.
3. Sets `request.subdomain = <label>` and `request.designer = Designer or None` via
   `Designer.objects.get_by_slug()`.

`get_by_slug` filters `status=2` (published) — so an unpublished designer's subdomain
silently yields `request.designer = None` rather than an error.

### Access control

`designers/mixins.py::DesignerAccessMixin.dispatch` takes the slug from view kwargs,
then `request.subdomain`, then the `?subdomain=` query param (a **development-only
convenience** — the request is not authenticated, it only chooses which designer page
to render). Non-published designers are redirected to their owner's exhibition page;
unknown slugs raise 404.

## API / Interface

### URL layout

`designers/urls.py` is mounted under `/designers/` (app_name `designers`):

| Path | View |
|---|---|
| `/designers/<slug>/` | `MainPage` |
| `/designers/<slug>/portfolio/` | `PortfolioPage` |
| `/designers/<slug>/portfolio/<project_id>/` | `PortfolioDetailPage` |
| `/designers/<slug>/send_message` | `send_message` (AJAX contact form) |

On a production subdomain these URLs are rewritten to root-relative paths by the
`designer_url` tag, so the same templates serve both layouts.

### Template tags (`designers/templatetags/designer_tags.py`)

- **`{% designer_static path slug %}`** — returns a static URL only if the file
  exists on disk, otherwise `''` (so templates can omit optional assets). Returns
  `/static/designers/<slug>/<path>` in development and on the main domain, but
  `/static/designers/<path>` on a production subdomain — nginx then maps that to
  `static/designers/<slug>/<path>`. Both halves must agree; changing one without the
  other 404s every designer asset.
- **`{% designer_url view_name slug %}`** — reverses a URL and strips the
  `/designers/<slug>` prefix when running on a production subdomain.

### Sitemaps

`designers/sitemap.py::designer_sitemap_view` builds a per-designer sitemap served at
`/designers/<slug>/sitemap.xml`; `exhibition/views.py::robots_txt` advertises the
subdomain's own sitemap. The former `services.update_google_sitemap` ping stub was
removed (2026-09-16) — Google's ping endpoint is dead, sitemaps are fetched live.

## Static Assets

- Per-designer assets live in `static/designers/<slug>/` (`css/`, `favicons/`,
  `favicon.ico`, plus verification files such as `yandex_*.html`).
- These directories **are tracked in git** — they are the deliberate exception to the
  `static/*` ignore rule (see `AGENTS.md` gotcha #2).
- nginx serves them via a dedicated block whose regex captures the subdomain:
  `location /static/designers { alias .../static/designers/$subdomain; }`.

## Configuration

| Item | Notes |
|---|---|
| `Designer.slug` | `SlugField(max_length=20, unique=True)` — the subdomain label; nginx regex is `[a-z0-9-]+` |
| `Site` row (SITE_ID = 1) | Must contain the real domain or subdomain detection fails |
| `ACCOUNT_EMAIL_VERIFICATION` / allauth | Designer accounts are ordinary allauth users |
| `X-Subdomain` header | Set by nginx; trusted when present |
| `?subdomain=` | Development-only override in `DesignerAccessMixin` |

## Gotchas

- **Adding a designer requires three things, not one:** a `Designer` row with
  `status=2`, a `static/designers/<slug>/` directory if the site has custom assets,
  and DNS/wildcard coverage for `<slug>.sd43.ru`. Missing any one produces a blank or
  missing-asset site with no error.
- **`send_message` returns `None` for non-AJAX requests**, which surfaces as a 500.
  It depends on `crm.middleware.AjaxMiddleware` re-adding `request.is_ajax()` and
  reads its data from **GET** parameters.
- **`Designer.exh_portfolio` / `add_portfolio` are `ChainedManyToManyField`s**
  (django-smart-selects) that depend on `owner`; they behave differently from plain
  M2M fields in admin and in querysets.
- Media for designers goes to `media/`, while their look-and-feel assets go to
  `static/` — do not mix the two.
- Designer static URLs must be **cache-busted manually**; two different designers can
  serve the same relative path, and nginx aliases per subdomain, so a shared
  `css/style.css` is not shared between them.
