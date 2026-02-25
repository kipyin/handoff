# Engagement To-Do App

Minimal to-do app for managing tasks across different engagements (projects). Personal use; runs locally with SQLite.

## Database: SQLite

The app uses **SQLite** (single file, no server). It’s a good fit for:

- One user, one machine
- Simple CRUD (projects + todos)
- No extra setup

**DuckDB** is better for analytics and large read-heavy workloads; for this app SQLite is simpler and sufficient.

## Setup

Requires Python 3.11+ and [uv](https://docs.astral.sh/uv/).

```bash
# Install dependencies (creates .venv and installs packages)
uv sync

# Run the app
uv run streamlit run app.py
```

The database file is created at `src/todo_app/todo.db` on first run.

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
