"""Main entrypoint for the Chaos Queue app.

This file intentionally exposes a stable APP_VERSION constant so an updater can
read it, while delegating UI rendering to :mod:`todo_app.ui_facade` and
Streamlit's :func:`st.navigation` API.
"""

from __future__ import annotations

import streamlit as st

from todo_app.ui_facade import (
    render_calendar_page,
    render_projects_page,
    render_todos_page,
    setup,
)

# Keep this in sync with `[project].version` in pyproject.toml.
APP_VERSION = "2026.2.7"


def _todos_page() -> None:
    """Configure global layout and render the Todos view."""
    setup(APP_VERSION)
    render_todos_page()


def _projects_page() -> None:
    """Configure global layout and render the Projects view."""
    setup(APP_VERSION)
    render_projects_page()


def _calendar_page() -> None:
    """Configure global layout and render the Calendar view."""
    setup(APP_VERSION)
    render_calendar_page()


def main() -> None:
    """Run the Chaos Queue app using the Streamlit navigation API."""
    pages = [
        st.Page(_todos_page, title="Todos", icon="✅"),
        st.Page(_projects_page, title="Projects", icon="📁"),
        st.Page(_calendar_page, title="Calendar", icon="📅"),
    ]
    nav = st.navigation(pages, position="top")
    nav.run()


if __name__ == "__main__":
    main()
