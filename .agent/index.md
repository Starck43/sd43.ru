# Project Index

**Last Updated:** 2026-09-16

## Overview

`sd43.ru` — Django monolith serving the **Сфера Дизайна** design exhibition
platform (company «Арт-Сервис»). Server-rendered templates, esbuild-managed assets,
and one project serving both the main site and per-designer subdomains.

Project-wide rules for agents live in [`../AGENTS.md`](../AGENTS.md).

## Current Status

- **Active Task:** None
- **Active Plans:** 0
- **Recent Lessons:** 2
- **Decisions:** 1

## Stack Pointers (derive, don't trust)

| Concern | Source of truth |
|---|---|
| Python dependencies | `requirements.txt` + the checked-in `venv/` (they drift) |
| Django version | the pin in `requirements.txt` |
| Node dependencies & scripts | `package.json` |
| App version | `crm/project.py` (`VERSION`) |
| Environment variables | `.env` (dev) / `prod.env` (prod, secrets — gitignored) |
| Asset pipeline | `build.mjs` + `BUILD.md` |
| Deployment | `.github/workflows/main.yml` + `.deploy/` |
| URL map | `crm/urls.py` and each app's `urls.py` |

## Module Documentation

- [crm — project configuration](modules/crm-config.md) — settings, middleware, context processors, captcha, shared helpers
- [exhibition — main domain app](modules/exhibition-app.md) — exhibitions, portfolio, SEO, search, uploads, emails
- [designers — subdomain tenancy](modules/designers-subdomains.md) — `<slug>.sd43.ru`, `request.designer`, designer static/URL tags
- [content apps — blog, rating, ads](modules/content-apps.md) — articles, reviews/ratings, partner banners
- [frontend assets](modules/frontend-assets.md) — `src/` → `static/` esbuild pipeline and conventions
- [deployment](modules/deployment.md) — GitHub Actions → rsync → systemd/gunicorn/nginx

## Recent Lessons

1. [2026-09-16] - [Post-init recommendations: docs refresh, ADR-0001, dead-code cleanup](lessons/2026-09-16-post-init-recommendations.md)
2. [2026-09-16] - [Project initialization](lessons/2026-09-16-project-initialization.md)

## Active Plans

- None.

## Active Decisions

- [ADR-0001 — Migrations are generated on the server](decisions/0001-server-generated-migrations.md)
- Candidate for a future ADR: "designer sub-sites are subdomains of one Django project rather than separate sites".

## Quick Links

- [All Lessons](lessons/)
- [All Decisions](decisions/)
- [All Modules](modules/)
- [Archive](archive/)
- [Project rules](../AGENTS.md)
