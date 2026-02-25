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
uv run streamlit run app.py
```

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

## Windows embedded zip build (optional)

On Windows you can build a self-contained zip that bundles an embedded Python runtime, dependencies, and the app code:

```bash
uv run python build_zip.py
```

This produces a zip under `dist/` (named like `todo-app-2026.2.0-windows-embed.zip`). Extract it, then double-click `run.bat` to start the app. The SQLite database is still stored in your user data directory, not inside the extracted folder.

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
