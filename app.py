"""Main entrypoint for the Handoff app.

This file intentionally exposes a stable APP_VERSION constant so an updater can
read it, while delegating UI rendering to :mod:`handoff.ui` and
Streamlit's :func:`st.navigation` API.
"""

from __future__ import annotations

import streamlit as st

from handoff.ui import (
    render_analytics_page,
    render_calendar_page,
    render_docs_page,
    render_projects_page,
    render_settings_page,
    render_todos_page,
    setup,
)
from handoff.version import __version__ as APP_VERSION


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


def _settings_page() -> None:
    """Configure global layout and render the Settings view."""
    setup(APP_VERSION)
    render_settings_page()


def _docs_page() -> None:
    """Configure global layout and render the Docs view."""
    setup(APP_VERSION)
    render_docs_page()


def main() -> None:
    """Run the Handoff app using the Streamlit navigation API."""
    pages = [
        st.Page(_todos_page, title="Todos", icon="✅"),
        st.Page(_projects_page, title="Projects", icon="📁"),
        st.Page(_calendar_page, title="Calendar", icon="📅"),
        # st.Page(_analytics_page, title="Analytics", icon="📊"),
        st.Page(_settings_page, title="Settings", icon="⚙️"),
        st.Page(_docs_page, title="Docs", icon="📖"),
    ]
    nav = st.navigation(pages, position="top")
    nav.run()


if __name__ == "__main__":
    main()
