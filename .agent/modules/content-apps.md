# Module: content apps — blog, rating, ads

**Created:** 2026-09-16
**Last Updated:** 2026-09-16
**Status:** Active

## Description

Three small apps that hang off the exhibition domain. They are mounted at the site
root by `crm/urls.py` and all depend on `exhibition` models — none of them can be
removed independently of the main app.

## blog — articles

- `Category` (db_table `article_category`) and `Article` (db_table `article`) —
  **explicit `db_table` names that do not match the app label**. Keep them if you
  touch migrations.
- Slugs are generated with `uuslug` in `save()` when empty.
- `Article.content` is a `RichTextUploadingField` (CKEditor), so uploads go to
  `CKEDITOR_UPLOAD_PATH` (`attachments/`) and the description is trusted HTML —
  never render it through `|safe` in a new context without checking that first.
- `Article.person()` resolves the author's `Exhibitors`, `Partners` or `Jury` record
  by user, with a fallback chain and a possible `None`.
- Routes (`app_name = 'blog'`): `/articles/`, `/articles/<pk>/`. Detail URLs use the
  **primary key**, not the slug, even though `slug` is unique.

## rating — scores and reviews

- `Rating` — one row per `(user, portfolio)` (`unique_together`), `star` 1–5,
  `is_jury_rating`, plus the rater's IP.
  `Rating.can_user_rate(user, portfolio)` returns a `(bool, reason)` tuple and encodes
  the business rules: login required, no self-rating, one rating per user, jury may
  **update** their rating.
- `Rating.calculate()` does not persist anything — it copies aggregate values from
  `Portfolio.get_rating_stats()` onto the instance for display.
- `Reviews` — threaded comments on a portfolio, using a self-FK pair
  (`parent` for replies, `group` for the thread root). Ordering is
  `['-posted_date', 'group_id', 'parent_id']`, so threads are flattened by ordering
  rather than nested in the template.
- Routes (`app_name = 'rating'`), mounted at the **site root**: `/add-rating/`,
  `/review/<pk>/`, `/review/edit/<pk>/`, `/review/delete/<pk>/`.

## ads — partner banners

- `Banner` (extends `exhibition.base_models.BaseImageModel`) with a display window
  (`show_start`/`show_end`), a target `pages` M2M to `ContentType`, an optional
  `article`, `is_general` (top-of-page partner banner) and `sort`.
- **There is no `ads/urls.py` and no `ads/views.py`.** Banners have no pages of their
  own; they are injected into other apps' views by
  `exhibition.mixins.BannersMixin`, which derives the target model from
  `self.model.__name__.lower()` and sets `ads_banners` / `general_banner` in context.
  `Banner.get_banners(model_name)` matches that same lowercased model name against
  `ContentType.model` — so **renaming a model class silently stops its banners from
  appearing**.
- `is_general` banners ignore the date window (the query ORs `is_general=True`).
- File replacement and deletion call `sorl.thumbnail.delete` to drop cached
  thumbnails, because sorl keys its cache by file path — replacing a banner file
  without that call leaves stale thumbnails. This is the pattern to copy for any
  image field that can be replaced in place.

## Cross-cutting notes

- Default page sizes for article lists come from `ARTICLES_COUNT_PER_PAGE`;
  portfolio lists use `PORTFOLIO_COUNT_PER_PAGE` (see
  [exhibition-app](exhibition-app.md)).
- All three apps appear in `JAZZMIN_SETTINGS.order_with_respect_to`, ordering the
  admin sidebar.
- Templates live in `templates/blog/`, `templates/rating/`, `templates/ads/`.

## Gotchas

- **`Article.modified_date` is `auto_now_add=True`** — despite the name it records the
  creation date and never changes. Do not use it as a "last edited" timestamp.
- **Ratings and reviews are cached in fragments** (`templates/blog/article_list.html`,
  `templates/exhibition/portfolio_detail.html`), so new review/rating flows must
  invalidate the matching fragment names (`delete_cached_fragment`) or the UI will
  show stale counts.
- **`Banner.pages` binds to `ContentType`**, which means banners break if an app label
  or model name changes (see above).
