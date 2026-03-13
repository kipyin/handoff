"""Public UI entrypoints for the Handoff app.

This module provides a stable, concise import path for the Streamlit UI while
delegating concrete page implementations to handoff.interfaces.streamlit.pages.
"""

from __future__ import annotations

import streamlit as st

from handoff.bootstrap.logging import configure_logging
from handoff.db import DatabaseInitializationError, init_db

from .pages.about import render_about_page as _render_about_page_impl
from .pages.dashboard import render_dashboard_page as _render_dashboard_page_impl
from .pages.projects import render_projects_page as _render_projects_page_impl
from .pages.system_settings import render_system_settings_page as _render_system_settings_page_impl


def setup(app_version: str) -> None:
    """Initialise global layout and database.

    This function should be called once per Streamlit page before rendering any
    concrete content. It configures logging, sets the page layout, and initialises
    the database. If database initialisation fails, the app stops with an error.

    Args:
        app_version: Application version string. Accepted for API consistency;
            currently unused but reserved for future display or logging.
    """
    configure_logging()
    st.set_page_config(page_title="Handoff", page_icon="📥", layout="centered")
    try:
        init_db()
    except DatabaseInitializationError:
        st.error(
            "The database could not be initialised.\n\n"
            "Check that the app has write access to its data directory or to the path "
            "configured in HANDOFF_DB_PATH.\n\n"
            "See the log file for technical details.",
        )
        st.stop()


def render_projects_page() -> None:
    """Render the projects management page."""
    _render_projects_page_impl()


def render_dashboard_page() -> None:
    """Render the main dashboard page."""
    _render_dashboard_page_impl()


def render_about_page() -> None:
    """Render the combined About page (README + release notes)."""
    _render_about_page_impl()


def render_system_settings_page() -> None:
    """Render the System Settings page."""
    _render_system_settings_page_impl()


__all__ = [
    "render_about_page",
    "render_dashboard_page",
    "render_projects_page",
    "render_system_settings_page",
    "setup",
]
