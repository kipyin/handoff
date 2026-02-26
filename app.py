"""Thin Streamlit entrypoint.

This file intentionally stays minimal so an updater can read APP_VERSION here.
"""

from todo_app.app_ui import main as run_app

# Keep this in sync with `[project].version` in pyproject.toml.
APP_VERSION = "2026.2.3"
def main() -> None:
    """Run the Streamlit app via the package UI module."""
    run_app(app_version=APP_VERSION)


if __name__ == "__main__":
    main()
