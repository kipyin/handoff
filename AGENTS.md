# AGENTS.md

Agent and developer instructions for Handoff. Cursor Cloud and GitHub Copilot read this file for project context.

---

## Code style

The goal is not maximal abstraction or maximal cleverness. The goal is code that is small, calm, readable, and hard to break.

### Aesthetic

- Prefer **boring code over surprising code**.
- Keep modules **small in concept count**, even when they are not tiny in line count.
- Use **clear names** that match the product language. If the UI says "handoff", the code should usually say `handoff` too.
- Make the **main flow easy to scan**: read input → normalize/validate → perform one clear action → return a simple result.
- Prefer a **single obvious representation** for a piece of data. Avoid bouncing between ORM models, dicts, DataFrames, widget payloads, and ad hoc tuples unless there is a strong reason.
- Keep comments sparse. Add them when they explain **why** something exists or a non-obvious constraint, not to narrate obvious code.
- Avoid "magic helper" sprawl. A helper should either simplify the reader's job, or it should not exist.

### Hygienic

- Keep **boundaries explicit**: models define persisted shape; data-layer functions implement behavior and queries; **services** orchestrate between pages and data (pages must not import `handoff.data` directly); page/UI modules translate UI state into typed app-level inputs; UI-specific concerns should not leak into core modules.
- Prefer **typed contracts** for non-trivial flows (query objects, mutation inputs, serialized backup/import payloads).
- Do not create abstractions just to move code around. A new module or type should reduce ambiguity, coupling, or duplication.
- Preserve **one source of truth** for important behavior. Filtering, validation, and serialization should not be reimplemented differently in multiple layers.
- Keep public APIs and docstrings in sync. If behavior changes, update the docs/tests in the same change.
- When touching old names or legacy compatibility paths, prefer a **clear primary name** plus a compatibility shim rather than letting both concepts coexist indefinitely.

### Robust

- Validate inputs **before destructive actions**.
- Fail with **clean, actionable messages** for users and **specific logs** for developers.
- Prefer code that is easy to test with **targeted unit tests** and a few integration/smoke tests over code that only works when driven through the UI.
- Make hidden global state explicit when practical. Lazy factories or narrow context helpers are preferred to import-time side effects.
- Handle real edge cases: missing ids on not-yet-persisted models, malformed backup files, path traversal in patch zips, schema drift in lightweight migrations.
- If a refactor changes behavior in a subtle UI path, add or update a test so the intended behavior is locked in.

### Practical preferences

- Streamlit is the current UI, but the app should stay **portable in shape**. Favor patterns that would still make sense in a future CLI or Textual frontend.
- SQLite + SQLModel is intentionally simple. Keep migrations lightweight unless complexity truly demands more.
- **Ruff** is the formatter/linter authority. **Pyright** is the type-checking authority.
- When in doubt, choose: fewer layers, fewer representations, fewer special cases, more explicit names, more local reasoning.

**One-sentence summary:** Write code that looks calm, says exactly what it means, and keeps behavior in the smallest sensible number of places.

---

## Quick reference

| Task | Command |
|------|---------|
| Install deps | `uv sync` |
| Run app | `uv run handoff` (Streamlit on port 8501) |
| Lint + format | `uv run handoff check` (`--fix` to apply Ruff changes) |
| Type check | `uv run handoff typecheck` |
| Tests | `uv run handoff test` |
| Full CI suite | `uv run handoff ci` (`--fix` to apply Ruff changes first) |
| Bump version | `uv run handoff bump 2026.M.P` |
| Build Windows zip | `uv run handoff build --full` |
| Build patch zip | `uv run handoff build --patch` |
| Build macOS tar.gz | `uv run handoff build --full --platform mac` |
| Build dry-run (CI) | `uv run handoff build --full --dry-run` or `--patch --dry-run` |

---

## Project overview

**Handoff** is a single-user local handoff tracker built with Python 3.13+, Streamlit, and SQLite. No external services or Docker are needed.

### Core workflow

- A **handoff** stays open until its latest check-in is `concluded`.
- Check-ins are append-only (`on_track`, `delayed`, `concluded`) and form a per-handoff trail.
- The Now page is organized as **Risk | Action required | Upcoming | Concluded**.
- Terminology is canonical: use `pitchman` (who is responsible) and `need_back` (deliverable requested).

### Deployment philosophy

Handoff ships as a self-contained Windows zip (or macOS tar.gz) that bundles an embedded/standalone Python runtime, dependencies, and the app code. The `src/handoff` package is obfuscated with PyArmor, while `app.py` stays readable as a thin entrypoint and launcher target. Patch zips update the obfuscated code in place, with backups taken before each update.

### Prerequisites

- Python 3.13+
- [uv](https://docs.astral.sh/uv/) for dependency and virtualenv management

### CLI commands

- `uv run handoff run` – start the app (Streamlit UI).
- `uv run handoff sync` – sync dependencies.
- `uv run handoff check` – Ruff format/lint (`--fix` to apply).
- `uv run handoff typecheck` – pyright over `src/` and `scripts/`.
- `uv run handoff test` – pytest suite.
- `uv run handoff ci` – checks + typecheck + tests (`--fix` for Ruff fixes first).
- `uv run handoff build --full` – Windows embedded zip or macOS tar.gz (`--platform mac`).
- `uv run handoff build --patch` – patch zip from obfuscated build.
- `uv run handoff bump 2026.M.P` – bump version in `pyproject.toml` and `handoff.version`.

Version sync: `src/handoff/version.py` and `pyproject.toml` must match; `tests/test_version_sync.py` enforces this.

Project layout: `app.py` (entrypoint), `src/handoff/` (package), `pages/`, `services/`, `tests/`. Pages import from `handoff.services`, never from `handoff.data` directly; the architecture test enforces this.

### Branching, commits, and releases

1. Branch from `main`: `git checkout -b release/YYYY.M.MINOR`.
2. Make focused commits.
3. Bump CalVer when shipping user-visible changes (use `bump`).
4. Add `## YYYY.M.MINOR [Tag]` to `RELEASE_NOTES.md` — use **Fix**, **Feature**, **Improvement**, **Internal** bullets.
5. Impact tags: `[Breaking]` if launcher, Python version, deps, or build layout changed (full reinstall required); `[Recommended]` if user-visible changes that patch can deliver; `[Optional]` if internal-only (refactor, tests, build/CI, docs).

### Release workflow checklist

1. Branch from `main`.
2. `uv sync` (if deps changed).
3. `uv run handoff bump 2026.M.P`.
4. Update `RELEASE_NOTES.md`.
5. Update README if user-visible behavior changed.
6. `uv run handoff ci`.
7. `uv run handoff build --full` and `uv run handoff build --patch` (for distribution).
8. Merge to `main` when passing.

### Code tools

- **Ruff**: `uv run handoff check` / `uv run handoff check --fix`.
- **Docstrings**: Google style.
- **Pyright**: `uv run handoff typecheck` over `src/` and `scripts/`.

### macOS build

macOS builds produce a `.tar.gz` with python-build-standalone:

```bash
uv run handoff build --full --platform mac
```

Extract and run `./handoff.sh`. Future work may add a signed `.app` bundle.

---

## Non-obvious caveats

- **Python 3.13+ required.** Use `uv python install 3.13` if needed; `uv sync` will use it.
- **`uv` must be on PATH.** Install via `curl -LsSf https://astral.sh/uv/install.sh | sh` and ensure `~/.local/bin` on PATH.
- **Streamlit headless mode.** In cloud/CI: `--server.headless true` or `STREAMLIT_SERVER_HEADLESS=true`.
- **SQLite DB location.** Via `platformdirs`; override with `HANDOFF_DB_PATH` for testing.
- **No login required.** Single-user, local-only. No `.env`, no API keys.
- **Throw-away DB for dev.** `HANDOFF_DB_PATH=/tmp/handoff-dev.db uv run handoff run`.

---

## Active pages

The navigation in `app.py` exposes five pages: Now and Dashboard in the first (unlabeled) group, and Projects, About, and System Settings under the "Settings" group.

| Page | Icon | Module |
|------|------|--------|
| Now | 🎯 | `pages/now.py` (`render_now_page`) |
| Projects | 📁 | `pages/projects.py` |
| Dashboard | 📊 | `pages/dashboard.py` (`render_dashboard_page`) |
| About | 📖 | `pages/about.py` (`render_about_page`) |
| System Settings | ⚙️ | `pages/system_settings.py` (`render_system_settings_page`) |

There is no Calendar page.

---

## Testing workflows by area

**Data layer:** `uv run pytest tests/test_models.py tests/test_db.py tests/test_data.py` — in-memory SQLite. When adding a column, add inline migration in `db.py:init_db()` and a migration test.

**Pages / UI:** `uv run pytest tests/test_pages_projects.py tests/test_pages_now.py tests/test_dashboard.py`

**Services:** `uv run pytest tests/test_todo_service.py tests/test_services_architecture.py` (handoff service tests; legacy filename retained)

**Integration:** `cd /workspace && uv run pytest tests/test_app_integration.py` (from project root).

**Build:** `tests/test_build_artifacts.py` and `tests/test_launchers.py` require PyArmor and Windows embed — not expected to pass on Linux. Use `--dry-run` for CI.

**Version sync:** `uv run pytest tests/test_version_sync.py`

---

## Full CI

```bash
uv run handoff ci          # format/lint + typecheck + pytest
uv run handoff ci --fix    # apply Ruff fixes first
uv run handoff check       # Ruff only
uv run handoff typecheck   # pyright only
uv run handoff test        # pytest only
```

**pyright exclusions:** `data.py`, `pages/dashboard.py`, `services/dashboard_service.py` — do not remove without understanding the consequences.

---

## Keeping this file up to date

When you discover a new testing trick, environment quirk, or runbook step, add it here. Prefer concrete commands over prose, note platform-specific limitations, and remove stale entries when the codebase changes.
