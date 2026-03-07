"""Settings page implementation for Handoff.

This page centralises app updates, code backup restore, data export, log
download, and a compact About section so that operational controls live in
one place.
"""

from __future__ import annotations

import csv
import io
import json
import platform
import zipfile
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st

from handoff.data import get_export_payload, import_payload
from handoff.docs import get_readme_intro
from handoff.logging import _get_logs_dir
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


def _parse_csv_to_payload(text: str) -> dict[str, Any]:
    """Build an import payload from a CSV string (todos-only, projects auto-created)."""
    reader = csv.DictReader(io.StringIO(text))
    todos_raw: list[dict[str, Any]] = []
    project_ids: dict[int, bool] = {}
    for row in reader:
        pid = int(row["project_id"])
        project_ids[pid] = row.get("is_archived", "False").lower() in ("true", "1")
        todos_raw.append(
            {
                "id": int(row["id"]),
                "project_id": pid,
                "name": row["name"],
                "status": row.get("status", "handoff"),
                "deadline": row.get("deadline") or None,
                "helper": row.get("helper") or None,
                "notes": row.get("notes") or None,
                "created_at": row.get("created_at", datetime.now().isoformat()),
                "completed_at": row.get("completed_at") or None,
                "is_archived": row.get("is_archived", "False").lower() in ("true", "1"),
            }
        )
    projects_raw = [
        {
            "id": pid,
            "name": f"Project {pid}",
            "created_at": datetime.now().isoformat(),
            "is_archived": archived,
        }
        for pid, archived in project_ids.items()
    ]
    return {"projects": projects_raw, "todos": todos_raw}


def _render_data_import_section() -> None:
    """Render JSON and CSV import controls for restoring data from a backup."""
    st.markdown("### Data import")
    st.caption(
        "Restore from a JSON or CSV backup. **This will overwrite all existing data** "
        "(projects and todos)."
    )

    uploaded = st.file_uploader(
        "Upload a .json or .csv backup file",
        type=["json", "csv"],
        key="settings_import_file",
    )
    if uploaded is None:
        return

    try:
        raw_text = uploaded.getvalue().decode("utf-8")
        if uploaded.name.endswith(".csv"):
            payload = _parse_csv_to_payload(raw_text)
        else:
            payload = json.loads(raw_text)

        if "projects" not in payload or "todos" not in payload:
            st.error("Invalid file: expected top-level 'projects' and 'todos' keys.")
            return

        st.info(
            f"File contains **{len(payload['projects'])}** projects "
            f"and **{len(payload['todos'])}** todos."
        )
    except Exception as exc:
        st.error(f"Could not parse file: {exc}")
        return

    confirm = st.checkbox(
        "I understand this will replace all existing projects and todos.",
        key="settings_import_confirm",
    )
    if confirm and st.button("Import and overwrite", key="settings_import_apply"):
        try:
            import_payload(payload)
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
    _render_data_export_section()

    st.divider()
    _render_data_import_section()

    st.divider()
    _render_send_log_section()

    st.divider()
    _render_about_section()
