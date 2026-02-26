# Chaos Queue

Chaos-tinged to-do app for juggling tasks across different engagements (projects). Personal use; runs locally with SQLite.

## Why this over a spreadsheet?

Unlike an ad-hoc Excel or Sheets tracker, this app is opinionated around
**multi?project, helper-centric work**:

- **Cross-project view**: All todos live in a single table so you can see your
  entire workload across engagements at once, without maintaining separate
  tabs.
- **Helper dimension**: The `helper` field treats ?who is on the hook? as a
  first-class axis for filtering and planning (for example, ?what have I
  delegated to Alice this week??).
- **Deadlines & focus presets**: Deadline filters (today, tomorrow, this week,
  custom ranges) and sorting are tuned for short-horizon planning rather than
  long-term Gantt charts.
- **Lightweight history & backups**: Todos and projects are stored in a local
  SQLite database with a built-in JSON/CSV export, so you can safely experiment
  without losing data.
- **Streamlit-native UX**: The UI is optimised for quick inline editing,
  filtering, and saving, not for cell-by-cell formulas or complex formatting.

If you find yourself stitching together multiple sheets or constantly
re-filtering to answer ?what must ship this week across all projects??, this
app aims to make that view a single click instead.

## Database: SQLite

The app uses **SQLite** (single file, no server). It's a good fit for:

- One user, one machine
- Simple CRUD (projects + todos)
- No extra setup

## Setup

Requires Python 3.13+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies (creates .venv and installs packages)
uv sync

# Run the app
uv run streamlit run app.py --server.baseUrlPath todo
```

For local development, pass `--server.baseUrlPath todo` so the app is served under `/todo` (for example: `http://localhost:8501/todo`).

By default, the SQLite database is stored in your per-user data directory so app updates do not overwrite your data (for example on Windows: `%APPDATA%\todo-app\todo.db`). You can override the location by setting the `TODO_APP_DB_PATH` environment variable before starting the app.

`app.py` is intentionally kept thin and exposes an `APP_VERSION` constant so external tooling (for example an updater) can read a stable version value from a single place.

## Features

1. **Projects** ? Create and manage engagements/projects on the Projects page.
2. **Todos per project** ? Each project has many todos. Each todo has:
  - Name
  - Deadline (optional)
  - Creation timestamp (auto)
  - Status: `delegated` | `done` | `canceled`
  - Helper (assignee)
  - Notes (text; you can paste links, file paths, etc.)
3. **Unified table view** ? One main table lists todos across all projects. Use the filter bar to narrow by:
   - **Search** ? Text in name, notes, helper, or project.
   - **Statuses** ? Multiselect (defaults to delegated).
   - **Projects** ? Multiselect.
   - **Helper** ? Dropdown of known helpers (or "All helpers").
   - **Deadline** ? Optional date range (popover: enable range, then pick From/To dates).
   Sort by clicking column headers. Edit inline and click **Save changes** to create, update, or delete todos.

## Logging & debugging

The app uses **loguru** for logging, configured to write to:

- **Standard output** (what you see in the terminal when running Streamlit).
- **Rotating log file** under your user data directory (for example on Windows:
  `%APPDATA%\todo-app\logs\todo-app.log`).

The configuration lives in `src/todo_app/logging.py` and is initialised from
`todo_app.ui.setup()`.

- **During development**, run the app from a terminal to see logs live as you interact:
  ```bash
  uv run streamlit run app.py --server.baseUrlPath todo
  ```
- **What gets logged** (non-exhaustive):
  - Database initialisation and file location.
  - Project creation, rename, and delete operations.
  - Creating, updating, and deleting todos (with context, row number, and todo id).
  - Save summary counts and high-level query info.

For deeper diagnostics you can extend the existing `loguru` calls in
`src/todo_app/data.py`, `src/todo_app/db.py`, or `src/todo_app/ui_components.py`.

## Windows embedded zip build (optional)

On Windows you can build a self-contained zip that bundles an embedded Python runtime, dependencies, and the app code:

```bash
uv run python build_zip.py
```

This produces a zip under `dist/` (named like `todo-app-2026.2.4-windows-embed.zip`). Extract it, then double-click `run.bat` to start the app (the launcher already includes `--server.baseUrlPath todo`). The SQLite database is still stored in your user data directory, not inside the extracted folder.

## Development

```bash
# Lint and format
uv run ruff check . && uv run ruff format .

# Tests
uv run pytest
```

Version sync guard:

- `app.py` contains `APP_VERSION`.
- `pyproject.toml` contains `[project].version`.
- `tests/test_version_sync.py` enforces they match.
- `scripts/bump_version.py` updates both together:
  ```bash
  uv run python scripts/bump_version.py 2026.3.0
  ```

## Project layout

- `app.py` ? Thin Streamlit entrypoint + `APP_VERSION`
- `src/todo_app/ui.py` ? Public Streamlit UI entrypoints (implementation in `app_ui.py`)
- `src/todo_app/` ? Package: `models.py`, `db.py`, `data.py`
- `tests/` ? Pytest tests

