"""Main entrypoint for the Chaos Queue app.

This file intentionally exposes a stable APP_VERSION constant so an updater can
read it, while delegating UI rendering to :mod:`todo_app.ui_facade` and
Streamlit's :func:`st.navigation` API.
"""

from __future__ import annotations

import streamlit as st

from todo_app.ui_facade import (
    render_analytics_page,
    render_calendar_page,
    render_focus_page,
    render_projects_page,
    render_todos_page,
    setup,
)
from todo_app.updater import render_update_panel
from todo_app.version import __version__ as APP_VERSION


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


def _analytics_page() -> None:
    """Configure global layout and render the Analytics view."""
    setup(APP_VERSION)
    render_analytics_page()


def _focus_page() -> None:
    """Configure global layout and render the Focus view."""
    setup(APP_VERSION)
    render_focus_page()


def main() -> None:
    """Run the Chaos Queue app using the Streamlit navigation API."""
    render_update_panel(APP_VERSION)
    pages = [
        st.Page(_todos_page, title="Todos", icon="✅"),
        st.Page(_projects_page, title="Projects", icon="📁"),
        st.Page(_calendar_page, title="Calendar", icon="📅"),
        st.Page(_analytics_page, title="Analytics", icon="📊"),
        st.Page(_focus_page, title="Focus", icon="🎯"),
    ]
    nav = st.navigation(pages, position="top")
    nav.run()


if __name__ == "__main__":
    main()
