# AGENTS.md

## Cursor Cloud specific instructions

**Handoff** is a single-user local to-do app built with Python 3.13+, Streamlit, and SQLite. No external services or Docker are needed.

### Quick reference

| Task | Command |
|---|---|
| Install deps | `uv sync` |
| Run app | `uv run handoff` (Streamlit on port 8501) |
| Lint + format | `uv run handoff check` |
| Type check | `uv run handoff typecheck` |
| Tests | `uv run handoff test` |
| Full CI suite | `uv run handoff ci` |
| Bump version | `uv run handoff bump 2026.M.P` |
| Build Windows zip | `uv run handoff build --full` |
| Build patch zip | `uv run handoff build --patch` |

All commands are documented in `CONTRIBUTING.md`.

### Coding style summary

Follow the canonical style guide in `STYLE.md`.

Short version:

- Keep the code small in concept count and easy to scan.
- Prefer one clear representation of data over multiple ad hoc ones.
- Keep boundaries explicit between models, data-layer logic, and UI adapters.
- Validate inputs before destructive actions and produce clean user-facing errors.
- Favor patterns that would still make sense in a future CLI or Textual frontend.

### Non-obvious caveats

- **Python 3.13+ required.** The VM may ship with an older Python. Use `uv python install 3.13` to get the right version; `uv sync` will then use it automatically.
- **`uv` must be on PATH.** Install via `curl -LsSf https://astral.sh/uv/install.sh | sh` and ensure `~/.local/bin` is on PATH.
- **Streamlit headless mode.** When starting the app in a cloud/CI context, pass `--server.headless true` to avoid browser-open prompts. The CLI command `uv run handoff run` does not set this automatically — use `uv run python -m streamlit run app.py --server.headless true` directly, or set `STREAMLIT_SERVER_HEADLESS=true`.
- **SQLite DB location.** By default stored in the platform data dir (via `platformdirs`). Override with `HANDOFF_DB_PATH` env var for testing or isolation.
- **No login required.** The app is single-user and local-only. No `.env` files, no API keys, no external services.
- **App starts with a throw-away DB.** For development, run `HANDOFF_DB_PATH=/tmp/handoff-dev.db uv run handoff run` to avoid touching the user's real data directory.

### Active pages

The navigation in `app.py` exposes five pages:

| Page | Icon | Module |
|---|---|---|
| Todos | ✅ | `pages/todos.py` |
| Projects | 📁 | `pages/projects.py` |
| Dashboard | 📊 | `pages/dashboard.py` (`render_dashboard_page`) |
| Settings | ⚙️ | `pages/settings.py` |
| Docs | 📖 | `pages/docs.py` |

There is no Calendar page. The Dashboard page uses `pages/dashboard.py` and `render_dashboard_page`.

### Testing workflows by area

**Data layer** (`models.py`, `db.py`, `data.py`):

```bash
uv run pytest tests/test_models.py tests/test_db.py tests/test_data.py
```

All use an in-memory SQLite fixture — no file-system side effects. When adding a column, also add an inline migration in `db.py:init_db()` via `PRAGMA table_info` checks, and a test that confirms migration on an old schema.

**Pages / UI** (`pages/`):

```bash
uv run pytest tests/test_pages_todos.py tests/test_pages_projects.py tests/test_dashboard.py
```

Integration smoke tests use Streamlit's `AppTest` with a real temp-file DB:

```bash
# Always run from the project root to avoid FileNotFoundError in docs.py
cd /workspace && uv run pytest tests/test_app_integration.py
```

**Runtime health** (`tests/test_application_runtime_health.py`): Spawns the real Streamlit process, monitors stdout for error patterns (Traceback, Error), and asserts the "You can now view" ready message appears. The subprocess does not exit on its own—it runs ~10 seconds then is terminated. Included in `uv run handoff test`.

**UI helpers, dates, updater:**

```bash
uv run pytest tests/test_ui.py tests/test_ui_setup.py tests/test_updater.py
```

**Build scripts** (`scripts/`): `tests/test_build_artifacts.py` and `tests/test_launchers.py` require PyArmor and a Windows Python embed zip — **not expected to pass on Linux**. Skip if they fail.

**Version sync:** `uv run pytest tests/test_version_sync.py` — enforces `pyproject.toml` and `src/handoff/version.py` stay in sync. Use `uv run handoff bump <version>` to update both atomically.

### Full CI

```bash
uv run handoff ci          # lint + format + typecheck + pytest
uv run handoff check       # Ruff format + lint (auto-fixes in place)
uv run handoff typecheck   # pyright over src/ and scripts/
uv run handoff test        # pytest with coverage (-x, --ff)
```

**pyright exclusions:** `data.py`, `pages/dashboard.py`, `pages/todos.py`, and `services/dashboard_service.py` are excluded from type checking (heavy SQLModel/Streamlit/pandas dynamic usage). Do not remove them from the exclusion list in `pyproject.toml` without understanding the consequences.

### Keeping this file up to date

When you discover a new testing trick, environment quirk, or runbook step, add it here before ending your session. Prefer concrete commands over prose, note any platform-specific limitations, and remove stale entries when the codebase changes.
