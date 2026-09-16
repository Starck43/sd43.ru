# Module: exhibition — Main Domain App

**Created:** 2026-09-16
**Last Updated:** 2026-09-16
**Status:** Active

## Description

The core app. It owns the exhibition domain — people, exhibitions, categories,
nominations, portfolio projects, winners, event galleries and SEO metadata — plus
the public site's views, upload flow, search and email notifications. When a task is
about "the site", it almost always lands here.

## Architecture

Layering is deliberate; respect it when adding code:

```
models.py / base_models.py   -> data + per-model save() side effects
logic.py                     -> files, images, uploads, email
services.py / cache.py       -> query services, cache invalidation, external pings
mixins.py                    -> reusable view and admin behaviour
views.py                     -> thin: mixins + querysets + template names
signals.py                   -> post-save cache/image/notification wiring
```

### Key models

- `Person` (via `base_models.UserModel` + `BaseImageModel`) is the shared identity
  base; `Exhibitors`, `Organizer`, `Jury`, `Partners` build on `Person` and
  optionally `Profile`. Changing `Person` affects all four.
- `Exhibitions` is the year-scoped event; `Categories` and `Nominations` classify
  work; `Portfolio` is a submitted project and is the pivot of the whole site —
  `Portfolio.nominations` is an M2M, and `Winners` records victories separately.
- `Image` / `Gallery` hold uploads; `MetaSEO` provides per-object SEO text.

### Services and helpers

- `services.ProjectsQueryService` / `services.WinnersService` — query construction.
- `services.delete_cached_fragment(name, *args)` — the canonical way to drop a
  `{% cache %}` fragment; `cache.py` composes those calls per business event.
- `logic.process_image` / `optimize_image_fields_async` — image resizing and WebP
  conversion; `MediaFileStorage` and the `*_upload_to` callables own media layout.
- `logic.send_email_async` — emails are sent on a background thread, never inline.
- `services.unicode_emoji` — emoji are stored in a `:NAME:` placeholder form rather
  than raw characters; round-trip through this helper when touching those fields.

### Mixins worth knowing

`MetaSeoMixin` (SEO context), `ExhibitionsYearsMixin` (year dropdown/filtering),
`ProjectsLazyLoadMixin` (infinite scroll), `BannersMixin` (sidebar ads),
`PersonAdminMixin` / `ImagePreviewMixin` / `MediaWidgetMixin` (admin UX),
`ImagesInlineAdminMixin`.

### Registration entry points

- `apps.py` registers models with `django-watson` search at app-ready time, using
  `self.get_model("...")` string lookups and custom `SearchAdapter`s. Its local
  variable names (`Exhibtitors`, `Exhibtions`) are misspelled but harmless — the
  strings passed to `get_model` are what matter.
- `signals.py` handles portfolio image persistence, cache invalidation on
  image/nomination/victory changes, and the sign-up notification email.
- `adapter.py` (`CustomAccountAdapter`) plus `forms.AccountSignupForm` /
  `CustomSocialSignupForm` override allauth behaviour.

## API / Interface

### Management commands

| Command | Purpose |
|---|---|
| `clear_template_cache --all [--verbose]` | Flush named template fragments (invalidates the fragment names hard-coded in the command) |
| `confirm_existing_emails` | Mark pre-existing allauth email addresses as confirmed |
| `fix_permissions` | Repair admin permissions (a copy also lives under `resources/backup/`) |

### Public HTTP surface

`exhibition/urls.py` is mounted at the site root. It exposes list views
(`/exhibitions/`, `/category/<slug>/`, `/jury/`, `/partners/`, `/exhibitors/`,
`/winners/`, `/events/` — each with `all/` and `<exh_year>/` variants), detail views,
`/policy/`, `/search/`, `/account/` and a set of AJAX endpoints under `/api/`.
`crm/urls.py` points `handler404`/`handler500` and `robots.txt` at views here.

## Configuration

| Variable | Meaning |
|---|---|
| `PORTFOLIO_COUNT_PER_PAGE` | Page size for `ProjectsList` (env-driven) |
| `MAX_UPLOAD_FILES_SIZE`, `FILE_UPLOAD_MAX_MEMORY_SIZE` | Upload limits enforced by `logic.limit_file_size` |
| `DEFAULT_NO_IMAGE` | Fallback image path used when a model has no picture |
| `FILES_UPLOAD_FOLDER` | Root subfolder for staged uploads |
| `EMAIL_RECIPIENTS` | Notification recipients for the `logic.send_email*` helpers |

## Gotchas

- **`services.update_google_sitemap()` was removed (2026-09-16)** — it used to be a
  `...` stub called from many model `save()` methods (a legacy of Google's sitemap
  ping, sunset Jan 2024; `django.contrib.sitemaps.ping_google` was removed in
  Django 5.1, deprecated in 5.0). If a "notify search engines" feature is ever
  needed, design it properly instead of reviving the stub.
- **Admin `save()` is not a safe place for extra queries.** The stub used to be
  called inline in `save()`; anything real added there runs on every write.
- **Cache fragments are keyed by argument tuple.** `delete_cached_fragment` must
  receive exactly the same args the template used, which is why `cache.py` deletes
  both `True` and `False` variants of `portfolio_list`. Missing a variant leaves a
  stale page behind.
- **`robots.txt` and sitemaps are generated per host** — the main domain gets
  `/sitemap.xml`, each designer subdomain gets `/designers/<slug>/sitemap.xml`.
  See [designers-subdomains](designers-subdomains.md).
- **Portfolio upload is a multi-step AJAX flow** (`ProgressBarUploadHandler`,
  `portfolio_upload`, `portfolio_upload_confirmation`) that stages files on the
  instance (`_images_to_save`) and persists them in a `post_save` signal. Upload
  limits are per-file *and* per-batch.
