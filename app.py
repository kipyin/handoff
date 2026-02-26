"""Thin Streamlit entrypoint.

This file intentionally stays minimal so an updater can read APP_VERSION here.
"""

from todo_app.ui import render_todos_page, setup

# Keep this in sync with `[project].version` in pyproject.toml.
APP_VERSION = "2026.2.7"


def main() -> None:
    """Run the Streamlit app via the package UI module."""
    setup(APP_VERSION)
    render_todos_page()


if __name__ == "__main__":
    main()
