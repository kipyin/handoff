"""Public UI entrypoints for the Chaos Queue app.

This module provides a stable, concise import path for the Streamlit UI while
delegating concrete page implementations to :mod:`todo_app.pages` and shared
components in :mod:`todo_app.ui_components`.
"""

from __future__ import annotations

import streamlit as st

from .db import DatabaseInitializationError, init_db
from .logging import configure_logging
from .pages.calendar import render_calendar_page as _render_calendar_page_impl
from .pages.projects import render_projects_page as _render_projects_page_impl
from .pages.todos import render_todos_page as _render_todos_page_impl
from .ui_components import (
    DEADLINE_ANY,
    DEADLINE_CUSTOM,
    DEADLINE_THIS_WEEK,
    DEADLINE_TODAY,
    DEADLINE_TOMORROW,
    _deadline_preset_bounds,
    _init_session_state,
    _render_sidebar_backup,
)


def setup(app_version: str) -> None:
    """Initialise global layout, database, and sidebar.

    This function should be called once per Streamlit page before rendering any
    concrete content.

    Args:
        app_version: Application version string for display.
    """
    configure_logging()
    st.set_page_config(page_title="Chaos Queue", page_icon="📥", layout="wide")
    try:
        init_db()
    except DatabaseInitializationError:
        st.error(
            "The database could not be initialised.\n\n"
            "Check that the app has write access to its data directory or to the path "
            "configured in TODO_APP_DB_PATH.\n\n"
            "See the log file for technical details.",
        )
        st.stop()
    _init_session_state()

    st.sidebar.title("Chaos Queue")
    st.sidebar.caption(f"Version: {app_version}")
    st.sidebar.divider()
    _render_sidebar_backup()


def render_todos_page() -> None:
    """Render the main todos page."""
    _render_todos_page_impl()


def render_projects_page() -> None:
    """Render the projects management page."""
    _render_projects_page_impl()


def render_calendar_page() -> None:
    """Render the calendar/weekly view page."""
    _render_calendar_page_impl()


__all__ = [
    "DEADLINE_ANY",
    "DEADLINE_CUSTOM",
    "DEADLINE_THIS_WEEK",
    "DEADLINE_TODAY",
    "DEADLINE_TOMORROW",
    "_deadline_preset_bounds",
    "setup",
    "render_todos_page",
    "render_projects_page",
    "render_calendar_page",
]
