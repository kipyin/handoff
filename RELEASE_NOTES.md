# Release notes

## 2026.2.2

- Unified todo view: single main table with Search, Statuses (default: delegated), Projects, Helper (dropdown), and Deadline range filters.
- Native Streamlit table (`st.data_editor`) with column-header sorting; internal row-id mapping kept for reliable save/update/delete.
- Remove streamlit-aggrid dependency; add `query_todos()` in data layer for unified filtering.

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

