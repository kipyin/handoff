"""Settings page implementation for Handoff.

This page centralises app updates, code backup restore, data export, and a
compact About section so that operational controls live in one place.
"""

from __future__ import annotations

import json
import platform
from typing import Any

import pandas as pd
import streamlit as st

from handoff.data import get_export_payload
from handoff.updater import render_update_panel
from handoff.version import __version__ as APP_VERSION


def _render_data_export_section() -> None:
    """Render JSON and CSV export controls for projects and todos."""
    st.markdown("### Data export")
    st.caption(
        "Download a snapshot of your data. Exports are read-only and do not modify the "
        "underlying SQLite database."
    )

    payload: dict[str, Any] = get_export_payload()

    json_text = json.dumps(payload, indent=2)
    st.download_button(
        "Download JSON backup",
        data=json_text,
        file_name="todo_backup.json",
        mime="application/json",
        key="settings_download_json_backup",
    )

    todos = payload.get("todos", [])
    csv_text = (
        pd.DataFrame(todos).to_csv(index=False)
        if todos
        else "id,project_id,name,status,deadline,helper,notes,created_at\n"
    )
    st.download_button(
        "Download CSV (todos)",
        data=csv_text,
        file_name="todo_todos.csv",
        mime="text/csv",
        key="settings_download_csv_backup",
    )


def _render_about_section() -> None:
    """Render a compact About section at the end of the Settings page."""
    st.markdown("### About Handoff")
    st.caption(f"Version: {APP_VERSION}")

    st.write(
        "Handoff helps you see who is on the hook across all your projects. It is a local "
        "to-do app for juggling tasks across different engagements (projects). The app is "
        "designed for personal use and runs locally with SQLite."
    )

    st.write(
        "You get a local, single-user to-do app backed by SQLite, with a unified view across "
        "projects and helpers, plus a simple weekly calendar, analytics ideas, and an in-app "
        "update flow."
    )

    st.write(
        "Your data lives on this machine in a single SQLite database file; there is no server "
        "component or automatic sync. You can export JSON/CSV copies of your data from the "
        "Data export section above."
    )

    system = platform.system()
    release = platform.release()
    python_version = platform.python_version()
    st.caption(f"Environment: Python {python_version} on {system} {release}")

    st.caption(
        "For a fuller overview and a detailed changelog, open the in-app README and Release "
        "notes pages from the navigation bar."
    )


def render_settings_page() -> None:
    """Render the settings page with update, backup, and about sections."""
    st.subheader("Settings")
    st.write(
        "Use this page to apply code updates, restore backups created by updates, and export "
        "your data. An About section at the end summarises the app and environment."
    )

    # App updates and code backups (panel from handoff.updater).
    render_update_panel(APP_VERSION)

    st.divider()
    _render_data_export_section()

    st.divider()
    _render_about_section()
