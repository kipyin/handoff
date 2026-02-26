"""Public UI entrypoints for the engagement to-do app.

This module provides a stable, concise import path for the Streamlit UI while
delegating concrete page implementations to :mod:`todo_app.pages`.
"""

from __future__ import annotations

import streamlit as st

from .logging import configure_logging
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
from .db import init_db
from .pages.projects import render_projects_page as _render_projects_page_impl
from .pages.todos import render_todos_page as _render_todos_page_impl
from .pages.calendar import render_calendar_page as _render_calendar_page_impl


def setup(app_version: str) -> None:
    """Initialise global layout, database, and sidebar.

    This function should be called once per Streamlit page before rendering any
    concrete content.

    Args:
        app_version: Application version string for display.
    """
    configure_logging()
    st.set_page_config(page_title="Chaos Queue", page_icon="📥", layout="wide")
    init_db()
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
