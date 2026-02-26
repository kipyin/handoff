# Chaos Queue

Chaos-tinged to-do app for juggling tasks across different engagements (projects). Personal use; runs locally with SQLite.

## Why this over a spreadsheet?

Unlike an ad-hoc Excel or Sheets tracker, this app is opinionated around
**multi-project, helper-centric work**:

- **Cross-project view**: All todos live in a single table so you can see your
  entire workload across engagements at once, without maintaining separate
  tabs.
- **Helper dimension**: The `helper` field treats "who is on the hook" as a
  first-class axis for filtering and planning (for example, "what have I
  delegated to Alice this week?").
- **Deadlines & focus presets**: Deadline filters (today, tomorrow, this week,
  custom ranges) and sorting are tuned for short-horizon planning rather than
  long-term Gantt charts.
- **Lightweight history & backups**: Todos and projects are stored in a local
  SQLite database with a built-in JSON/CSV export, so you can safely experiment
  without losing data.
- **Streamlit-native UX**: The UI is optimised for quick inline editing,
  filtering, and saving, not for cell-by-cell formulas or complex formatting.

If you find yourself stitching together multiple sheets or constantly
re-filtering to answer "what must ship this week across all projects?", this
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
uv run todo run
```

By default, the SQLite database is stored in your per-user data directory so app updates do not overwrite your data (for example on Windows: `%APPDATA%\todo-app\todo.db`). You can override the location by setting the `TODO_APP_DB_PATH` environment variable before starting the app.

`app.py` is intentionally kept thin and delegates version handling to `src/todo_app/version.py`, which exposes a single `__version__` constant used by the UI and tooling (for example the updater panel and build scripts).

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
`todo_app.ui_facade.setup()`.

- **During development**, run the app from a terminal to see logs live as you interact:
  ```bash
  uv run streamlit run app.py
  ```
- **What gets logged** (non-exhaustive):
  - Database initialisation and file location.
  - Project creation, rename, and delete operations.
  - Creating, updating, and deleting todos (with context, row number, and todo id).
  - Save summary counts and high-level query info.

For deeper diagnostics you can extend the existing `loguru` calls in
`src/todo_app/data.py`, `src/todo_app/db.py`, or `src/todo_app/ui_components.py`.

## Windows embedded zip build and code-only patches

On Windows you can build a self-contained zip that bundles an embedded Python runtime,
dependencies, and the app code:

```bash
uv run todo build-zip
```

This produces a zip under `dist/` (named like `todo-app-<version>-windows-embed.zip`).
Extract it, then double-click `run.bat` to start the app (the launcher already includes
`--server.baseUrlPath todo`). The SQLite database is still stored in your user data
directory, not inside the extracted folder.

For small logic-only changes you can ship a **code-only patch** zip instead of a full
embedded bundle:

```bash
uv run todo build-patch
```

This creates `dist/todo-app-<version>-patch.zip` containing `app.py`, `src/todo_app/`,
and (by default) the `pages/` directory, plus a `VERSION` marker.

On a client machine:

1. The user runs the app as usual (for example from the embedded zip via `run.bat`).
2. In the Streamlit sidebar, they open **Update app**, upload the patch zip, and click
   **Apply and Restart**. If there are unsaved changes on the main Todos table, the button is
   disabled until those changes are saved.
3. After applying the patch, the app extracts the update into the app directory and then
   exits automatically; reopen `run.bat` to start the updated version.

### Backups and future rollback

When applying a code-only patch, the updater currently creates a **timestamped backup**
of any overwritten files under a `backup/<YYYYMMDD-HHMMSS>/` directory inside the app
root. Today, rollback is a **manual** process (for example, by copying files from a
chosen backup folder back into the app directory).

A future enhancement is planned to expose a **rollback/restore-from-backup** control in
the app itself, so that an operator can select a backup snapshot from the UI and
automatically restore the corresponding files without touching the filesystem directly.

## Development

The Typer CLI under `scripts/cli.py` wraps common development commands:

```bash
# Run the app
uv run todo run

# Install/sync dependencies
uv run todo sync

# Lint and format
uv run todo check

# Tests
uv run todo test

# Build embedded Windows zip
uv run todo build-zip

# Build code-only patch zip
uv run todo build-patch

# Bump version in pyproject.toml and todo_app.version
uv run todo bump-version 2026.2.10
```

Version sync guard:

- `src/todo_app/version.py` contains `__version__`.
- `pyproject.toml` contains `[project].version`.
- `tests/test_version_sync.py` enforces they match.
- `scripts/bump_version.py` (and the `bump-version` CLI command) update both together.

## Project layout

- `app.py` ? Thin Streamlit entrypoint + updater panel
- `src/todo_app/ui_facade.py` ? Public Streamlit UI entrypoints
- `src/todo_app/` ? Package: `models.py`, `db.py`, `data.py`
- `tests/` ? Pytest tests

