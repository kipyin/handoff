"""Streamlit UI for the Handoff app."""

from handoff.interfaces.streamlit.ui import (
    render_about_page,
    render_dashboard_page,
    render_projects_page,
    render_system_settings_page,
    setup,
)

__all__ = [
    "render_about_page",
    "render_dashboard_page",
    "render_projects_page",
    "render_system_settings_page",
    "setup",
]
