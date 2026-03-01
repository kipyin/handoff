# Release notes

## 2026.3.1 [Recommended]

- **Docstrings:** Standardized all module and function docstrings to Google style across the codebase. Summary lines, optional extended descriptions, and consistent Args/Returns/Raises (and Yields where relevant) are used in handoff, app, scripts, and tests. Sphinx/reST markup (:mod:, :func:, inline literals) has been removed in favour of plain prose so documentation is tooling-agnostic and readable in source.
- **Todo table autosave:** Reverted to snapshot-diff after render (no `on_change`): changes are saved when the table state differs from the last saved snapshot at the end of each run, matching pre-2026.2.24 behavior.
- **Code quality:** Removed unused code (`get_session`, no-op `_init_session_state`), fixed package `__version__` to re-export from `handoff.version`, re-enabled Analytics in the nav, and corrected `_clear_pycache` to only clear `app_root` and `app_root/src` (removed non-existent `pages` path).
- **Performance:** Todos now load projects in one query via `selectinload(Todo.project)` (fixes N+1). The Todos page calls `list_helpers()` once per run and passes the result to filters and column config. Doc markdown (README, RELEASE_NOTES) is cached in session state to avoid repeated file I/O.
- **DRY:** Shared `handoff.dates.week_bounds(reference)` for Monday–Sunday week logic used by todos deadline presets and the calendar. Updater zip parsing (VERSION + member list) extracted into `_read_patch_members(zf)` and reused by `extract_patch_to_staging` and `apply_patch_zip`.
- **Readability:** Todos page refactors: `_row_equals` uses `_normalize_str_field` and `_normalize_deadline_for_compare`; `_save_rows` uses `_parse_previous_snapshot`; `_apply_native_filters` delegates to `_apply_dataframe_filters`; `_render_editable_table` uses `_compute_defaults_from_filters` and `_sort_and_build_display_df`.
- **Test:** Calendar smoke test no longer expects a `date_input` widget (date picker is commented out in the UI).

## 2026.3.0 [Recommended]

- **Calendar:** Fixed `StreamlitAPIException` when using "Next week" or "Previous week": the date picker session state is now updated before the widget is created, so week navigation no longer triggers "cannot be modified after the widget with key ... is instantiated".

## 2026.2.24 [Recommended]

- **Calendar:** Fixed the "Next week" and "Previous week" buttons so the week view updates correctly (date picker session state is now synced when using week navigation).
- **Focus page removed:** The Focus page has been removed from the app; navigation no longer includes it.
- **UI module:** The public UI entrypoint module has been renamed from `handoff.ui_facade` to `handoff.ui`; use `handoff.ui.setup()` and the same render_* page functions.
- **Single helper:** The todo table uses a single Helper dropdown again (one helper per todo). The multiselect column was removed; existing multi-helper data is still read (first helper shown) and written as a single value.
- **Todo table save:** Changes are saved automatically when the table state differs from the last saved snapshot (snapshot-diff autosave on each run).
- **Refactor:** All todo table UI (filters, deadline presets, save logic) has been moved from `ui_components.py` into the Todos page (`handoff.pages.todos`). The `ui_components` module has been removed; `handoff.ui` delegates to the pages and inlines session init.
- **Simpler app:** Removed the urgency column and the formatted deadline display column from the todo table; the table now shows a single editable Deadline (date) column. Calendar keeps a minimal local urgency cue (overdue/today/soon) for display only.
- **Status rename:** Todo status previously stored as `delegated` is now stored and displayed as `handoff`. A one-time migration updates existing rows on first run. All UI and docs use "handoff" for this status.
- **Todo save optimisation:** When saving the todo table, only rows that actually changed are written to the database; unchanged rows are skipped.
- **Projects page:** Replaced the card layout with a table view. Edit project names and archive state in the table; check "Confirm delete" for projects to remove, then click **Save changes**. When one or more projects are marked for deletion, a confirmation step appears before applying (list of names and "Confirm and delete" / "Cancel"). Project statistics (handoff/done/canceled counts) have been removed from this page.
- **Calendar:** Deadline and Update controls for handoff todos are more compact (single row). Week navigation is aligned so "Previous week" lines up with Monday and "Next week" with Sunday. The current day column is labelled "— *Today*".
- **Todo table limit:** When more than 30 todos match the current filters, the table shows the first 30 and a caption; use filters to narrow the list.
- **Integration tests:** Added Streamlit AppTest-based smoke tests for the Todos, Projects, Calendar, and Settings pages (each page tested in isolation with a temporary database).
- **Update flow:** The in-app updater no longer applies the patch in-place. It extracts the patch zip to `./update/` and then exits after 2 seconds. The user runs `run.bat` again; the batch file applies the staged update (copies from `./update/` into the app directory and removes `./update/`) before starting the app, so PyArmor and other in-use files are replaced correctly on the next start.
- **Database filename:** The app still uses `todo.db` as the default database filename. A future release may rename it to e.g. `handoff.db` with a one-time migration; no change in this release.

## 2026.2.23 [Recommended]

- **Rebrand to Handoff:** Rename the app to *Handoff* with the tagline “See who’s on the hook across all your projects.” Update all UI titles, sidebar, About section, and docs. CLI command is now `handoff` (was `todo`). User data directory is now `handoff` (e.g. `%APPDATA%\handoff`); `HANDOFF_DB_PATH` is the preferred env var (still support `TODO_APP_DB_PATH` for backward compatibility).
- **Deadline column format:** Format deadline columns in the UI as “Tue, Mar 4th” (moment-style `ddd, MMM Do`) via a display formatter; keep the date column editable.
- **Updater PermissionError fix:** When applying a patch zip, skip files that cannot be overwritten (e.g. PyArmor runtime `.pyd` locked by the running process on Windows) instead of failing; report skipped files in the success message and advise restart + re-apply if needed.
- **Patch version check:** When applying a code-only patch zip, the updater now compares the patch version (from a `VERSION` file in the zip) with the current app version. If the patch is older, applying is blocked with a clear message; a checkbox on the Settings page lets you confirm and apply anyway if you understand the risk.
- **Backup versioning:** Timestamped backups created before applying a patch now include the app version in the folder name (e.g. `backup/2026.2.22_20260228-143022`). Restore snapshot labels in the UI show both version and timestamp where available.
- **Export timestamps:** JSON and CSV exports from the Settings page now include a timestamp in the filename (e.g. `todo_backup_2026-02-28_143022.json`, `todo_todos_2026-02-28_143022.csv`).
- **Update panel location:** The in-app update and backup-restore panel has been moved from `handoff.update_ui` into the Settings page implementation (`pages/settings.py`). The `update_ui.py` module has been removed; Settings imports updater logic directly from `handoff.updater`.
- **Todo table height:** The main todos table now uses Streamlit’s `height="content"` so the editor grows with the number of rows instead of a fixed viewport.
- **Calendar improvements:** Week navigation uses a 7-column layout so “Previous week” aligns with Monday and “Next week” with Sunday; the “View week of” date picker sits in the centre. Deadline and Update controls for delegated todos are more compact (single row, smaller button). The current day is marked with “— *Today*” in the column header.
- **Focus page:** A short caption has been added under the title explaining the page’s purpose: choose a few delegated items to focus on today, then mark them done or defer in one go.

## 2026.2.22 [Optional]

- **Legacy pages cleanup:** Remove legacy root `pages/` Streamlit shims (`2_Projects.py`, `3_Calendar.py`); navigation is now via `app.py` and Streamlit's `st.navigation` API only.
- **Type checker config:** Move Pyright configuration into `[tool.pyright]` in `pyproject.toml` and remove the standalone `pyrightconfig.json` file.
- **Patch tooling simplification:** Remove the legacy `scripts/build_patch.py` helper and associated CLI docs; use `uv run handoff build-patch` (after `build-zip`) for patch builds.

## 2026.2.21 [Recommended]

- **Docs inside the app:** Add a `Docs` navigation page that renders the README and release notes from the installed app root, and update Settings/About copy so it points there for “What’s new?”.
- **Calendar week navigation:** Allow paging backwards/forwards by week and jumping to a specific “week of” on the Calendar page while keeping inline deadline editing.
- **Autosave banner correctness:** Fix the main todos table so the “All changes saved” / “Unsaved changes” banner starts in a saved state on first load and only flips after real edits.
- **Updater UI separation:** Move the update/backup Streamlit panel into `handoff.update_ui` so `handoff.updater` focuses on filesystem logic, keeping Settings layout but with clearer “App updates” and “Restore from backup” sections.

## 2026.2.20 [Optional]

- **CLI & CI workflow:** Add `typecheck` and `ci` commands to the `handoff` CLI and document the recommended check/typecheck/test flow for local and CI runs.
- **Distribution quality:** Include project docs (README and release notes) in build and patch zips, plus tests that verify the contents of build artifacts.
- **Internal cleanup:** Remove an obsolete sidebar backup hook and apply Ruff-driven formatting cleanups; there are no user-visible behaviour changes.

## 2026.2.19 [Recommended]

- **Settings page:** Add a dedicated Settings page with in-app update/rollback controls, data export (JSON/CSV), and an inline About section at the bottom.
- **Update/backup location:** Move the update and backup UI out of the global sidebar so operational controls now live only on the Settings page.

## 2026.2.18 [Recommended]

- **Urgency & helper view:** Add urgency buckets (overdue, today, soon) to the main todos table and weekly calendar, plus a per-helper summary panel showing delegated and urgent work under the current filters.
- **Smart defaults:** Remember the last-used project and helper for new rows in the main todos view so repeated entry flows require fewer clicks.
- **Archiving:** Introduce project and todo archiving with a Projects page toggle for showing archived projects, and ensure archived items are excluded from default queries and views.
- **Calendar refinements:** Enable inline deadline adjustments for delegated todos directly from the weekly calendar.
- **Analytics:** Add an Analytics page with completed-per-week charts, cycle time stats, and current helper load.
- **Focus mode:** Add a Focus page that guides a daily review of overdue/today items and later-this-week tasks, with quick actions to mark done or defer.

## 2026.2.17 [Optional]

- **Contributor docs:** Add a `CONTRIBUTING.md` guide describing the uv/CLI workflow, type
checking with pyright, and the branching/versioning expectations backed by the Cursor
rules, plus reference it from the README.

## 2026.2.16 [Optional]

- **DB tests:** Add tests for file-based DB initialisation and the lightweight `completed_at`
migration using a temporary SQLite database, guarding against regressions in init/migrate
behaviour.

## 2026.2.15 [Optional]

- **Type checking:** Add a basic `pyright` configuration for `src/` and `scripts/`, wiring it
into the dev environment and excluding dynamic ORM/UI modules for now so type checking can
run cleanly and be tightened incrementally.

## 2026.2.14 [Optional]

- **DB robustness:** Wrap database engine creation and schema initialisation in structured
error handling, logging failures with loguru and surfacing a friendly error message in
the UI when the DB cannot be created or migrated.

## 2026.2.13 [Recommended]

- **Rollback UI:** Add a **Restore from backup** section to the in-app **Update app** sidebar
so you can browse timestamped backup snapshots, restore a selected snapshot, and have the
app restart automatically into the restored state.
- **Updater tests:** Add unit tests for the updater's patch application, backup handling,
`__pycache_`_ cleanup, and the new backup-restore helper.

## 2026.2.12 [Recommended]

- **PyArmor obfuscation:** The Windows embedded zip build (`uv run handoff build-zip`) now obfuscates the `src/handoff` package with PyArmor so that distributed code is protected while `app.py` remains readable. The PyArmor runtime is included in the zip; no extra install is required on the target machine.
- **Obfuscated patches:** For installs that use the obfuscated embedded zip, code-only updates must be built with `uv run handoff build-patch` (after running `build-zip`) so that the patch contains obfuscated code and the PyArmor runtime. The standard `build-patch` command still produces source-only patches for development or non-obfuscated installs.
- **Build requirements:** Building the embedded zip now requires PyArmor in the dev environment (`uv sync` installs it from the dev dependency group). The trial/non-profit PyArmor build uses default obfuscation; a full license allows extra options (e.g. `--enable-jit`, `--mix-str`) if you edit `scripts/build_zip.py`.

## 2026.2.11 [Optional]

- **Updater cache cleanup:** After applying a code-only patch, the app now removes `__pycache__`
directories under the application root (including `src/` and `pages/`) so that Python regenerates
fresh bytecode for the updated sources on next start.
- **Internal cleanup:** Modernise models and data access to use `UTC`/`StrEnum` and tidy imports and
type hints across scripts and tests; there are no user-facing behaviour changes.

## 2026.2.10 [Optional]

- **Updater timing:** Fix the in-app **Update app** panel so that its "Apply and Restart" button
correctly reflects unsaved changes from the **current** rerun instead of lagging by one rerun.
- **Persistent patch upload:** Keep the selected patch zip in memory across reruns (for example
after clicking **Save changes** on the main Todos table) so the update button does not disappear
until the patch has been applied or the app is restarted.

## 2026.2.9 [Recommended]

- **Updater UX:** The in-app **Update app** panel now blocks applying a patch while there are
unsaved changes in the main Todos table and shows a clear warning asking you to save first.
- **Auto-restart flow:** After successfully applying a code-only patch, the app now exits
automatically so that the `run.bat` window closes; reopening `run.bat` starts the updated
version without requiring manual process termination.

## 2026.2.8 [Recommended]

- **CLI & scripts:** Add a Typer + Rich CLI under `scripts/cli.py` that wraps common developer commands (`run`, `sync`, `check`, `test`, `build-zip`, `build-patch`, `bump-version`), and move the embedded Windows build logic into `scripts/build_zip.py` with a small root-level shim for backwards compatibility.
- **Versioning:** Introduce a single canonical `handoff.version.__version__` constant, update `app.py` to import it, and update `scripts/bump_version.py` + `tests/test_version_sync.py` so `pyproject.toml` and the version module stay in sync.
- **Patch updates:** Add a `scripts/build_patch.py` helper and `build-patch` CLI command to produce small code-only patch zips, plus an in-app Streamlit sidebar “Update app” panel (`handoff.updater.render_update_panel`) that applies uploaded patch zips safely against the app directory.

## 2026.2.7 [Recommended]

- **Branding:** Rename the app to *Chaos Queue* and update titles, description, and navigation to better reflect multi-project, hectic-day usage.
- **Logging:** Centralise loguru configuration so logs go to both stdout and a rotating file under the user data directory (e.g. `%APPDATA%\todo-app\logs`).
- **Todo lifecycle:** Track when todos are marked as done via a new `completed_at` timestamp and apply a lightweight migration for existing SQLite databases.
- **Calendar view:** Add a simple weekly calendar page that shows todos grouped by deadline day, annotated when completed this week.
- **UI components:** Extract shared Streamlit UI helpers into `ui_components.py` and clean up imports for the todos and calendar pages.

## 2026.2.6 [Optional]

- **Deadlines:** When you pick a date-only deadline in the todos table, it is now stored at 18:00 local time instead of midnight so that today does not show up as already in the past in relative views.
- **Helpers:** The `Helper` column in the todos table is now a free-text field instead of a dropdown, while the Helper filter above the table still offers a dropdown of all known helpers (updated after new helpers are saved).

## 2026.2.5 [Recommended]

- **Projects page:** Add a dedicated Projects page with project creation, rename, delete, and per-project todo summaries.
- **UI façade:** Introduce `handoff.pages` for page implementations and a `handoff.ui_facade` façade with `setup`, `render_todos_page`, and `render_projects_page` entrypoints suitable for Streamlit multipage usage.
- **Entry scripts:** Keep `app.py` as a thin entrypoint and (historically) add `pages/1_Todos.py` and `pages/2_Projects.py` as minimal Streamlit page shims for classic multipage usage; modern installs rely on `app.py` and Streamlit navigation instead.

## 2026.2.4 [Optional]

- **Logging:** Log applied filters in `query_todos` and include todo ids/names in save and delete logs for better traceability.
- **UI naming:** Expose a concise `handoff.ui_facade` module and rename the main view function to `view`.
- **Table behavior:** Remove the explicit Delete column and rely on built-in `st.data_editor` row deletion while keeping robust id mapping.
- **Streamlit chrome:** Hide the Deploy toolbar button via `.streamlit/config.toml`.
- **Docs:** Add a high-level UI flow diagram and clarify that notes support Markdown/links.

## 2026.2.3 [Recommended]

- **Column order:** Project, name, status, helper, deadline, notes; Delete column hidden by default (show via table column menu eye icon).
- **Filters:** Helper is a multiselect like Projects/Statuses (no All helpers); empty selection shows all. Deadline filter has label above dropdown with presets: Any, Today, Tomorrow, This week, Custom range. Custom range uses a single date-range picker (one calendar).
- **New row defaults:** When a single project, status, or helper is selected in the filter bar, new rows default to that value.
- **Deadline column** displays in relative distance format by default.
- **Sorting:** Sort by column and order via controls above the table (session state + pre-sort).

## 2026.2.2 [Recommended]

- Unified todo view: single main table with Search, Statuses (default: delegated), Projects, Helper (dropdown), and Deadline range filters.
- Native Streamlit table (`st.data_editor`) with column-header sorting; internal row-id mapping kept for reliable save/update/delete.

## 2026.2.1 [Recommended]

- Refactor the Streamlit entrypoint by moving UI composition and view logic into `src/handoff/app_ui.py`, keeping `app.py` intentionally minimal for runtime bootstrapping.
- Expose a stable `APP_VERSION` constant in `app.py` for updater/version checks and add a test (`tests/test_version_sync.py`) to enforce parity with `pyproject.toml`.
- Add `scripts/bump_version.py` to update `pyproject.toml` and `app.py` together in one command, reducing version drift risk.

## 2026.2.0 [Breaking]

- Refine build packaging and embedded Python setup, improving `build_zip.py` documentation, dependency management, and path configuration while making application code copying more resilient.
- Improve todo editing behavior so that original IDs are preserved, ID columns are hidden from the UI, and save logic more accurately maps edited rows back to their underlying records, with clearer documentation of save parameters.
- Update the project Python requirement to 3.13 for compatibility with newer dependencies.
- Switch to CalVer versioning (YYYY.M.MINOR) starting with this release.
- Move SQLite database to a per-user data directory so updates do not overwrite user data.
- Add build script for Windows zip distribution with embedded Python (`build_zip.py`).

