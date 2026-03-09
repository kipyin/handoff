"""Settings page implementation for Handoff.

This page centralises app updates, code backup restore, data export, log
download, and a compact About section so that operational controls live in
one place.
"""

from __future__ import annotations

import io
import json
import platform
import zipfile
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from loguru import logger

from handoff.backup_schema import BackupPayload
from handoff.docs import get_readme_intro
from handoff.logging import _get_logs_dir
from handoff.services.settings_service import (
    DEADLINE_NEAR_DAYS_MAX,
    DEADLINE_NEAR_DAYS_MIN,
    get_deadline_near_days,
    get_export_payload,
    import_payload,
    set_deadline_near_days,
)
from handoff.update_ui import render_update_panel
from handoff.version import __version__ as APP_VERSION


def _render_now_settings_section() -> None:
    """Render Now page / risk-window setting (deadline at risk days)."""
    st.markdown("### Now page")
    st.caption(
        "Control how many days before a deadline an item is shown as at risk on the Now page. "
        "Default is 1 (only overdue or due today)."
    )
    current = get_deadline_near_days()
    new_value = st.number_input(
        "Deadline at risk (days)",
        min_value=DEADLINE_NEAR_DAYS_MIN,
        max_value=DEADLINE_NEAR_DAYS_MAX,
        value=current,
        step=1,
        key="settings_deadline_near_days",
    )
    if new_value != current:
        set_deadline_near_days(new_value)
        st.success("Saved. The Now page will use this from the next refresh.")


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


def _render_send_log_section() -> None:
    """Render a download button that zips all log files for easy sharing."""
    st.markdown("### Send log")
    st.caption(
        "Download a zip of all log files. Attach this when reporting an issue — "
        "you don't need to find the log folder yourself."
    )

    logs_dir = _get_logs_dir()
    log_files = sorted(logs_dir.iterdir()) if logs_dir.exists() else []
    log_files = [f for f in log_files if f.is_file()]

    if not log_files:
        st.caption("No log files found.")
        return

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for log_file in log_files:
            zf.write(log_file, arcname=log_file.name)
    buf.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    st.download_button(
        "Download log zip",
        data=buf.getvalue(),
        file_name=f"handoff-logs-{timestamp}.zip",
        mime="application/zip",
        key="settings_download_logs",
    )


def _render_data_import_section() -> None:
    """Render JSON import controls for restoring data from a backup."""
    st.markdown("### Data import")
    st.caption(
        "Restore from a JSON backup. **This will overwrite all existing data** "
        "(projects and todos)."
    )

    uploaded = st.file_uploader(
        "Upload a .json backup file",
        type=["json"],
        key="settings_import_file",
    )
    if uploaded is None:
        return

    try:
        raw_text = uploaded.getvalue().decode("utf-8")
        payload = BackupPayload.from_dict(json.loads(raw_text))
    except UnicodeDecodeError:
        st.error("Could not read the file as UTF-8 text. Please upload a JSON backup.")
        return
    except json.JSONDecodeError:
        st.error("Invalid JSON file. Please upload a Handoff JSON backup.")
        return
    except (KeyError, ValueError) as exc:
        logger.warning("Invalid backup upload: {}", exc)
        st.error(
            "Invalid backup file. Expected a Handoff backup with 'projects' and 'todos' lists."
        )
        return

    st.info(
        f"File contains **{len(payload.projects)}** projects and **{len(payload.todos)}** todos."
    )

    confirm = st.checkbox(
        "I understand this will replace all existing projects and todos.",
        key="settings_import_confirm",
    )
    if confirm and st.button("Import and overwrite", key="settings_import_apply"):
        try:
            import_payload(payload.to_dict())
            st.success("Import complete — all data has been replaced.")
        except Exception as exc:
            st.error(f"Import failed: {exc}")


def _render_about_section() -> None:
    """Render a compact About section at the end of the Settings page."""
    st.markdown("### About Handoff")
    st.caption(f"Version: {APP_VERSION}")

    st.write(get_readme_intro())

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
        "Use this page to apply code updates, restore backups created by updates, export "
        "or import your data, and download logs. An About section at the end summarises "
        "the app and environment."
    )

    # App updates and code backups (panel from handoff.updater).
    render_update_panel(APP_VERSION)

    st.divider()
    _render_now_settings_section()

    st.divider()
    _render_data_export_section()

    st.divider()
    _render_data_import_section()

    st.divider()
    _render_send_log_section()

    st.divider()
    _render_about_section()
