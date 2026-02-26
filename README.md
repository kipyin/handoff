# Engagement To-Do App

Minimal to-do app for managing tasks across different engagements (projects). Personal use; runs locally with SQLite.

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

1. **Projects** ? Create engagements/projects in the sidebar.
2. **Todos per project** ? Each project has many todos. Each todo has:
   - Name
   - Deadline (optional)
   - Creation timestamp (auto)
   - Status: `delegated` | `done` | `canceled`
   - Helper (assignee)
   - Notes (text; you can paste links, file paths, etc.)
3. **Unified table view** ? One main table lists todos across all projects (columns: Project, name, status, helper, deadline, notes; use the column menu eye icon to show the Delete column). Use the filter bar to narrow by:
   - **Search** ? Text in name, notes, helper, or project.
   - **Statuses** ? Multiselect (defaults to delegated).
   - **Projects** ? Multiselect. **Helper** ? Multiselect.
   - **Deadline** ? Any, Today, Tomorrow, This week, or custom range (single calendar). New rows default to the single selected filter when one is active. Sort via controls above the table.

## Logging & debugging

The app uses **loguru** for logging (to standard output by default).

- **During development**, run the app from a terminal to see logs as you interact:

  ```bash
  uv run streamlit run app.py --server.baseUrlPath todo
  ```

- **What gets logged** (non-exhaustive):
  - Project creation
  - Creating, updating, and deleting todos (with context and row/todo id)
  - Save summary counts and high-level query info

For deeper diagnostics you can extend the existing `loguru` calls in `app.py`, `src/todo_app/data.py`, or `src/todo_app/db.py`.

## Windows embedded zip build (optional)

On Windows you can build a self-contained zip that bundles an embedded Python runtime, dependencies, and the app code:

```bash
uv run python build_zip.py
```

This produces a zip under `dist/` (named like `todo-app-2026.2.3-windows-embed.zip`). Extract it, then double-click `run.bat` to start the app (the launcher already includes `--server.baseUrlPath todo`). The SQLite database is still stored in your user data directory, not inside the extracted folder.

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
- `src/todo_app/app_ui.py` ? Streamlit UI composition and view logic
- `src/todo_app/` ? Package: `models.py`, `db.py`, `data.py`
- `tests/` ? Pytest tests
