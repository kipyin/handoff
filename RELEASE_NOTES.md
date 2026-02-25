# Release notes

## 2026.2.0

- Refine build packaging and embedded Python setup, improving `build_zip.py` documentation, dependency management, and path configuration while making application code copying more resilient.
- Improve todo editing behavior so that original IDs are preserved, ID columns are hidden from the UI, and save logic more accurately maps edited rows back to their underlying records, with clearer documentation of save parameters.
- Update the project Python requirement to 3.13 for compatibility with newer dependencies.
- Switch to CalVer versioning (YYYY.M.MINOR) starting with this release.
- Move SQLite database to a per-user data directory so updates do not overwrite user data.
- Add build script for Windows zip distribution with embedded Python (`build_zip.py`).

