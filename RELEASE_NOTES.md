# Release notes

## 2026.2.11

- **Updater cache cleanup:** After applying a code-only patch, the app now removes `__pycache__`
  directories under the application root (including `src/` and `pages/`) so that Python regenerates
  fresh bytecode for the updated sources on next start.
- **Internal cleanup:** Modernise models and data access to use `UTC`/`StrEnum` and tidy imports and
  type hints across scripts and tests; there are no user-facing behaviour changes.

## 2026.2.10

- **Updater timing:** Fix the in-app **Update app** panel so that its "Apply and Restart" button
  correctly reflects unsaved changes from the **current** rerun instead of lagging by one rerun.
- **Persistent patch upload:** Keep the selected patch zip in memory across reruns (for example
  after clicking **Save changes** on the main Todos table) so the update button does not disappear
  until the patch has been applied or the app is restarted.

## 2026.2.9

- **Updater UX:** The in-app **Update app** panel now blocks applying a patch while there are
  unsaved changes in the main Todos table and shows a clear warning asking you to save first.
- **Auto-restart flow:** After successfully applying a code-only patch, the app now exits
  automatically so that the `run.bat` window closes; reopening `run.bat` starts the updated
  version without requiring manual process termination.

## 2026.2.8

- **CLI & scripts:** Add a Typer + Rich CLI under `scripts/cli.py` that wraps common developer commands (`run`, `sync`, `check`, `test`, `build-zip`, `build-patch`, `bump-version`), and move the embedded Windows build logic into `scripts/build_zip.py` with a small root-level shim for backwards compatibility.
- **Versioning:** Introduce a single canonical `todo_app.version.__version__` constant, update `app.py` to import it, and update `scripts/bump_version.py` + `tests/test_version_sync.py` so `pyproject.toml` and the version module stay in sync.
- **Patch updates:** Add a `scripts/build_patch.py` helper and `build-patch` CLI command to produce small code-only patch zips, plus an in-app Streamlit sidebar “Update app” panel (`todo_app.updater.render_update_panel`) that applies uploaded patch zips safely against the app directory.

## 2026.2.7

- **Branding:** Rename the app to *Chaos Queue* and update titles, description, and navigation to better reflect multi-project, hectic-day usage.
- **Logging:** Centralise loguru configuration so logs go to both stdout and a rotating file under the user data directory (e.g. `%APPDATA%\todo-app\logs`).
- **Todo lifecycle:** Track when todos are marked as done via a new `completed_at` timestamp and apply a lightweight migration for existing SQLite databases.
- **Calendar view:** Add a simple weekly calendar page that shows todos grouped by deadline day, annotated when completed this week.
- **UI components:** Extract shared Streamlit UI helpers into `ui_components.py` and clean up imports for the todos and calendar pages.

## 2026.2.6

- **Deadlines:** When you pick a date-only deadline in the todos table, it is now stored at 18:00 local time instead of midnight so that \"today\" does not show up as already in the past in relative views.
- **Helpers:** The `Helper` column in the todos table is now a free-text field instead of a dropdown, while the Helper filter above the table still offers a dropdown of all known helpers (updated after new helpers are saved).

## 2026.2.5

- **Projects page:** Add a dedicated Projects page with project creation, rename, delete, and per-project todo summaries.
- **UI façade:** Introduce `todo_app.pages` for page implementations and a `todo_app.ui_facade` façade with `setup`, `render_todos_page`, and `render_projects_page` entrypoints suitable for Streamlit multipage usage.
- **Entry scripts:** Keep `app.py` as a thin entrypoint and add `pages/1_Todos.py` and `pages/2_Projects.py` as minimal Streamlit page shims.

## 2026.2.4

- **Logging:** Log applied filters in `query_todos` and include todo ids/names in save and delete logs for better traceability.
- **UI naming:** Expose a concise `todo_app.ui_facade` module and rename the main view function to `view`.
- **Table behavior:** Remove the explicit Delete column and rely on built-in `st.data_editor` row deletion while keeping robust id mapping.
- **Streamlit chrome:** Hide the Deploy toolbar button via `.streamlit/config.toml`.
- **Docs:** Add a high-level UI flow diagram and clarify that notes support Markdown/links.

## 2026.2.3

- **Column order:** Project, name, status, helper, deadline, notes; Delete column hidden by default (show via table column menu eye icon).
- **Filters:** Helper is a multiselect like Projects/Statuses (no \"All helpers\"); empty selection shows all. Deadline filter has label above dropdown with presets: Any, Today, Tomorrow, This week, Custom range. Custom range uses a single date-range picker (one calendar).
- **New row defaults:** When a single project, status, or helper is selected in the filter bar, new rows default to that value.
- **Deadline column** displays in relative \"distance\" format by default.
- **Sorting:** Sort by column and order via controls above the table (session state + pre-sort).

## 2026.2.2

- Unified todo view: single main table with Search, Statuses (default: delegated), Projects, Helper (dropdown), and Deadline range filters.
- Native Streamlit table (`st.data_editor`) with column-header sorting; internal row-id mapping kept for reliable save/update/delete.

## 2026.2.1

- Refactor the Streamlit entrypoint by moving UI composition and view logic into `src/todo_app/app_ui.py`, keeping `app.py` intentionally minimal for runtime bootstrapping.
- Expose a stable `APP_VERSION` constant in `app.py` for updater/version checks and add a test (`tests/test_version_sync.py`) to enforce parity with `pyproject.toml`.
- Add `scripts/bump_version.py` to update `pyproject.toml` and `app.py` together in one command, reducing version drift risk.

## 2026.2.0

- Refine build packaging and embedded Python setup, improving `build_zip.py` documentation, dependency management, and path configuration while making application code copying more resilient.
- Improve todo editing behavior so that original IDs are preserved, ID columns are hidden from the UI, and save logic more accurately maps edited rows back to their underlying records, with clearer documentation of save parameters.
- Update the project Python requirement to 3.13 for compatibility with newer dependencies.
- Switch to CalVer versioning (YYYY.M.MINOR) starting with this release.
- Move SQLite database to a per-user data directory so updates do not overwrite user data.
- Add build script for Windows zip distribution with embedded Python (`build_zip.py`).

