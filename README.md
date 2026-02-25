# Engagement To-Do App

Minimal to-do app for managing tasks across different engagements (projects). Personal use; runs locally with SQLite.

## Database: SQLite

The app uses **SQLite** (single file, no server). It’s a good fit for:

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

## Features

1. **Projects** – Create engagements/projects in the sidebar.
2. **Todos per project** – Each project has many todos. Each todo has:
   - Name
   - Deadline (optional)
   - Creation timestamp (auto)
   - Status: `delegated` | `done` | `cancelled`
   - Helper (assignee)
   - Notes (text; you can paste links, file paths, etc.)
3. **Three views**
   - **By project** – Select a project; done todos are grayed out; due today or overdue are highlighted in red.
   - **By helper** – Type a helper name to see all their tasks across projects.
   - **By timeframe** – Choose “Today”, “This week”, or a custom range to see all tasks in that period.

## Main flows

- **By project**: Select a project in the main view to see all its todos. Edit fields inline in the table and click **Save changes** to create new todos or update existing ones for that project.
- **By helper**: Choose or type a helper name to see their tasks across all projects. Use the editable table (including the Project column) to adjust status, deadlines, and assignments, then save.
- **By timeframe**: Pick a preset (Today/This week) or a custom date range to list todos whose deadlines fall in that window. Edits in the table are applied back to the underlying projects when you save.

## Logging & debugging

The app uses **loguru** for logging (to standard output by default).

- **During development**, run the app from a terminal to see logs as you interact:

  ```bash
  uv run streamlit run app.py --server.baseUrlPath todo
  ```

- **What gets logged** (non-exhaustive):
  - View switches (By project / By helper / By timeframe)
  - Project creation
  - Creating and updating todos from any of the editable views
  - High-level query info (for example, how many todos were fetched for a helper, project, or timeframe)

For deeper diagnostics you can extend the existing `loguru` calls in `app.py`, `src/todo_app/data.py`, or `src/todo_app/db.py`.

## Windows embedded zip build (optional)

On Windows you can build a self-contained zip that bundles an embedded Python runtime, dependencies, and the app code:

```bash
uv run python build_zip.py
```

This produces a zip under `dist/` (named like `todo-app-2026.2.0-windows-embed.zip`). Extract it, then double-click `run.bat` to start the app (the launcher already includes `--server.baseUrlPath todo`). The SQLite database is still stored in your user data directory, not inside the extracted folder.

## Development

```bash
# Lint and format
uv run ruff check . && uv run ruff format .

# Tests
uv run pytest
```

## Project layout

- `app.py` – Streamlit UI entrypoint
- `src/todo_app/` – Package: `models.py`, `db.py`, `data.py`
- `tests/` – Pytest tests
