# Retrospective: Project Initialization (`/init`)

**Date:** 2026-09-16
**Task:** Bootstrap `.agent/` knowledge base and project-specific `AGENTS.md` for sd43.ru
**Complexity:** Medium
**Duration:** single session

## What Was Done

Created the agent workspace and a project-specific instruction file for an existing
Django monolith that had no agent context at all.

- `.agent/` skeleton: `index.md`, `modules/`, `lessons/`, `decisions/`, `plans/`,
  `archive/{tasks,lessons,plans}`.
- `.gitignore` gained a split-ignore block: `.agent/*` ignored, with `index.md`,
  `lessons/`, `decisions/`, `modules/` re-included so knowledge is tracked while
  `task.md` / `state.json` / `plans/` / `archive/` stay ephemeral.
- `AGENTS.md` (root): what the project is, required reading, commands, conventions,
  git/versioning rules, 9 verified gotchas, security constraints, documentation layout
  and a stale-docs table.
- `.agent/index.md` with stack **pointers** instead of values, plus six module docs:
  `crm-config`, `exhibition-app`, `designers-subdomains`, `content-apps`,
  `frontend-assets`, `deployment`.

Detection: **existing project** — Django 5.x monolith, server-rendered templates,
esbuild asset pipeline, subdomain tenancy for designer sites, CI-driven deploy.

## Unexpected Problems

### Problem 1: Documentation described a different stack than the code

- **Description:** `README.md` and `BUILD.md` claim Django 4.x, Gulp, MySQL, Python 3.8+.
  The repository actually pins Django 5.x, builds with esbuild via `build.mjs`, runs
  PostgreSQL in production and has no `gulpfile.js` at all.
- **Impact:** Any agent trusting the docs would write for the wrong framework and
  reference a non-existent build system.
- **Root Cause:** Docs were never updated when the stack was migrated; nothing enforced
  freshness.

### Problem 2: A safety check produced a false result

- **Description:** The tab-vs-space indentation scan used `grep -P`, which macOS BSD
  grep does not support. It exited non-zero for every file, so every file looked
  space-indented. The initial `AGENTS.md` draft stated "Python: tabs", which would
  have been wrong for `exhibition/cache.py`, `manage.py` and two `apps.py` files.
- **Impact:** Nearly documented a false convention; caught before finalizing.
- **Root Cause:** Assumed GNU grep behaviour on a BSD userland, and the failure was
  silent because stderr was redirected to `/dev/null`.

### Problem 3: A suspected bug that was not a bug

- **Description:** `exhibition/apps.py` assigns `Exhibtitors = self.get_model("Exhibitors")`
  and `Exhibtions = self.get_model("Exhibitions")` — misspelled *local* names. It looked
  like a `NameError` waiting to happen.
- **Impact:** Almost recorded as a gotcha/bug, which would have sent a future agent
  chasing a non-issue.
- **Root Cause:** Variable names differ from the strings passed to `get_model()`, so the
  typo is harmless; only reading the whole file settled it.

### Problem 4: Editor payload limit

- **Description:** A single `AGENTS.md` write of ~8k characters was rejected
  (limit ~6000).
- **Impact:** One wasted call; no rework.
- **Root Cause:** Underestimating file size when writing long documents in one shot.

## Solution

### Solution 1: Verify every non-trivial claim against the running code

- **Approach:** Each gotcha was checked empirically: `manage.py check` for the storage
  setting, `inspect.getsource()` to prove `update_google_sitemap` is a stub, `awk` for
  indentation, `git check-ignore` for ignore semantics, `pip freeze` vs `requirements.txt`
  for drift, and reading `nginx.conf` for the subdomain/static rewrite contract.
- **Trade-offs:** Slower than trusting docs; the only way to produce context that does
  not mislead.
- **Alternatives Considered:** Copying the README claims — rejected outright, they are
  provably stale.

### Solution 2: Store pointers instead of volatile values

- **Approach:** `index.md` maps concerns to sources of truth ("Django version → pin in
  `requirements.txt`"). Module docs describe invariants and gotchas, never versions,
  counts or file listings.
- **Trade-offs:** Docs are less immediately scannable for facts, but they cannot rot.
- **Alternatives Considered:** Snapshotting the dependency list for convenience —
  rejected per the *derive, don't store* rule.

### Solution 3: Write large documents in chunks

- **Approach:** Create a partial file, then append using `old_text` anchors.
- **Trade-offs:** More calls, but no truncation or timeout risk.

## Lessons Learned

1. **Docs in a repo are claims, not facts — verify before propagating.**
   Every stack fact here (framework version, DB engine, build tool) was wrong in the
   committed docs. Derive from `requirements.txt`, `package.json`, configs and CI.
   In future: run the check before writing the sentence.

2. **Silent command failures on macOS produce confident wrong answers.**
   `grep -P` unsupported → non-zero exit → the loop reported one branch for all files.
   Prefer `awk`/`sed` for text scanning, and never discard stderr when the result feeds
   documentation.

3. **`manage.py check` passing does not mean settings are effective.**
   Django 5.2 has no `STATICFILES_STORAGE` setting at all, yet the line sits in
   `settings.py` and the check stays silent. Verify effective runtime state
   (here: `type(staticfiles_storage)`), not just the absence of errors.

4. **`.gitignore` doubles as the deploy's rsync exclude list.**
   This couples VCS bookkeeping to production file sync: `--delete` plus `.gitignore`
   means a new ignore rule can delete files on the server, and gitignore negation
   (`!…`) does not work in rsync at all. That is why CI rsyncs `static/` separately.
   Any `.gitignore` edit here must be reviewed as a deployment change.

5. **Watch for cross-module coupling hiding in string keys.**
   `Banner.pages` → `ContentType.model`, admin ordering in
   `JAZZMIN_SETTINGS.order_with_respect_to`, cache fragment names, and the designer
   subdomain↔static-directory contract all break silently on renames. Renames in this
   codebase are never local.

## References

- **Commits:** not yet committed (documentation-only change)
- **Related Tasks:** none — first recorded task for this project
- **Documentation:** `AGENTS.md`, `.agent/index.md`, `.agent/modules/`

## Recommendations

- Refresh `README.md` / `BUILD.md` (Django 5.x, esbuild, PostgreSQL, no Gulp) — the
  stale-docs table in `AGENTS.md` is a holding measure, not a fix.
- Consider an ADR for "migrations are generated on the server" — the most surprising
  invariant in the project, and it deserves an explicit decision record.
- Treat `settings.py`'s `STATICFILES_STORAGE`, the `DJANGORESIZED_*` block and
  `services.update_google_sitemap` as cleanup candidates (dead/inert code), separately
  from this task.
- Remove `docs/` from `.gitignore` if project documentation is ever needed in git —
  currently the `docs/` convention cannot be used at all.

---

**Tags:** #initialization #documentation #django #verification
