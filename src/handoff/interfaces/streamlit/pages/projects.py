"""Projects page implementation for the Handoff app."""

from __future__ import annotations

from dataclasses import asdict

import pandas as pd
import streamlit as st
from loguru import logger

from handoff.core.page_models import ProjectSummaryRow
from handoff.services.project_service import (
    archive_project,
    create_project,
    delete_project,
    get_projects_with_handoff_summary,
    rename_project,
    unarchive_project,
)

from ..autosave import autosave_editor


def _render_create_project_form() -> None:
    """Render the top-of-page project creation form."""
    st.subheader("Create project")
    with st.form("projects_create_project"):
        name = st.text_input("Project name", key="projects_new_project_name") or ""
        submitted = st.form_submit_button("Create")
        if submitted:
            cleaned = name.strip()
            if not cleaned:
                st.error("Project name cannot be empty.")
                return
            create_project(cleaned)
            st.success("Project created.")
            st.rerun()


def _build_projects_display_rows(
    summary_list: list[dict],
) -> list[ProjectSummaryRow]:
    """Build typed summary rows for the projects table."""
    rows: list[ProjectSummaryRow] = []
    for item in summary_list:
        p = item["project"]
        rows.append(
            ProjectSummaryRow(
                project_id=p.id,
                name=p.name,
                is_archived=getattr(p, "is_archived", False),
                open=item["open"],
                concluded=item["concluded"],
            )
        )
    return rows


def _get_projects_to_delete(edited_df: pd.DataFrame, projects: list) -> list[tuple[int, str]]:
    """Helper to identify projects marked for deletion in the UI."""
    project_by_id = {p.id: p for p in projects}
    to_delete: list[tuple[int, str]] = []
    for _, row in edited_df.iterrows():
        pid = row.get("__project_id")
        if pid is None or pd.isna(pid):
            continue
        pid = int(pid)
        project = project_by_id.get(pid)
        if project and row.get("confirm_delete"):
            to_delete.append((pid, getattr(project, "name", "")))
    return to_delete


def _get_pending_changes(
    edited_df: pd.DataFrame, projects: list
) -> tuple[bool, list[str], list[dict]]:
    """Compare UI-edited DataFrame to current projects and produce a list of changes."""
    project_by_id = {p.id: p for p in projects}
    errors: list[str] = []
    changes: list[dict] = []

    for _, row in edited_df.iterrows():
        pid = row.get("__project_id")
        if pid is None or pd.isna(pid):
            continue
        pid = int(pid)
        project = project_by_id.get(pid)
        if not project:
            continue
        if row.get("confirm_delete"):
            changes.append({"type": "delete", "id": pid, "name": getattr(project, "name", "")})
            continue
        new_name = (row.get("name") or "").strip()
        if not new_name:
            errors.append(f"Project name cannot be empty (id {pid}).")
            continue
        if new_name != project.name:
            changes.append({"type": "rename", "id": pid, "new_name": new_name})
        new_archived = bool(row.get("is_archived"))
        if new_archived != getattr(project, "is_archived", False):
            changes.append({"type": "archive", "id": pid, "archive": new_archived})

    valid = len(errors) == 0
    return valid, errors, changes


def _execute_changes(changes: list[dict]) -> tuple[int, int, list[str]]:
    """Execute a list of UI-derived changes. Returns (deleted, updated, errors)."""
    deleted = 0
    updated = 0
    errors: list[str] = []
    for ch in changes:
        t = ch.get("type")
        if t == "rename":
            pid = int(ch["id"])
            new_name = ch["new_name"]
            try:
                rename_project(pid, new_name)
                updated += 1
            except Exception as e:
                errors.append(f"Could not rename project {pid}: {e}")
        elif t == "archive":
            pid = int(ch["id"])
            try:
                if ch["archive"]:
                    archive_project(pid)
                else:
                    unarchive_project(pid)
                updated += 1
            except Exception as e:
                errors.append(f"Could not update archive for project {pid}: {e}")
        elif t == "delete":
            pid = int(ch["id"])
            try:
                if delete_project(pid):
                    deleted += 1
                else:
                    errors.append(f'Could not delete project "{ch.get("name")}".')
            except Exception as e:
                errors.append(f"Could not delete project {pid}: {e}")
    return deleted, updated, errors


def _apply_project_changes(
    edited_df: pd.DataFrame,
    projects: list,
) -> tuple[bool, list[str], int, int]:
    """Apply table edits: renames, archive toggles, and deletions using pure logic helpers."""
    valid, errors, changes = _get_pending_changes(edited_df, projects)
    if not valid:
        return (False, errors, 0, 0)
    if not changes:
        return (True, [], 0, 0)
    deleted, updated, exec_errors = _execute_changes(changes)
    success = len(exec_errors) == 0
    if not success:
        return (False, exec_errors, deleted, updated)
    return (True, [], deleted, updated)


_AUTOSAVE_ERRORS_KEY = "__projects_autosave_errors"


def _persist_project_edits(state: dict, display_df: pd.DataFrame) -> bool:
    """Autosave callback for project renames and archive toggles."""
    edited = state.get("edited_rows", {})
    if not edited:
        return False

    errors: list[str] = []

    for row_idx_str, changes in edited.items():
        try:
            row_idx = int(row_idx_str)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid edited row index: {}", row_idx_str)
            continue

        if not (0 <= row_idx < len(display_df)):
            continue
        pid = display_df.iloc[row_idx].get("__project_id")
        if pid is None or pd.isna(pid):
            continue
        pid = int(pid)

        new_name = changes.get("name")
        if new_name is not None:
            cleaned = new_name.strip()
            if cleaned:
                try:
                    rename_project(pid, cleaned)
                    logger.info("Auto-saved rename for project_id={}", pid)
                except Exception:
                    logger.exception("Failed to auto-save rename for project_id={}", pid)
                    errors.append(f"Could not rename project {pid}.")

        new_archived = changes.get("is_archived")
        if new_archived is not None:
            try:
                if new_archived:
                    archive_project(pid)
                else:
                    unarchive_project(pid)
                logger.info("Auto-saved archive={} for project_id={}", new_archived, pid)
            except Exception:
                logger.exception("Failed to auto-save archive for project_id={}", pid)
                errors.append(f"Could not update archive state for project {pid}.")

    if errors:
        st.session_state[_AUTOSAVE_ERRORS_KEY] = errors

    return False


def _reset_projects_table_state() -> None:
    """Clear editor, autosave context, and deletion-confirmation state."""
    for key in ("projects_table_active", "projects_table_all", "projects_pending_deletion"):
        st.session_state.pop(key, None)
    for key in list(st.session_state):
        if isinstance(key, str) and key.startswith("__projects_table_"):
            st.session_state.pop(key, None)


def render_projects_page() -> None:
    """Render the projects management page with autosave for edits."""
    st.subheader("Projects")
    _render_create_project_form()

    show_archived = st.checkbox(
        "Show archived projects",
        key="projects_show_archived",
        help="Include archived projects so you can review or unarchive them.",
        on_change=_reset_projects_table_state,
    )

    summary_list = get_projects_with_handoff_summary(include_archived=show_archived)
    if not summary_list:
        if show_archived:
            st.info("No projects yet. Use the form above to create the first project.")
        else:
            st.info(
                "No active projects yet. Create one above or enable "
                '"Show archived projects" to manage archived ones.'
            )
        return

    projects = [item["project"] for item in summary_list]
    display_df = pd.DataFrame(
        [
            {
                "__project_id": row.project_id,
                **asdict(row),
                "confirm_delete": False,
            }
            for row in _build_projects_display_rows(summary_list)
        ]
    ).drop(columns=["project_id"])
    editor_key = "projects_table_all" if show_archived else "projects_table_active"

    if show_archived:
        st.caption(
            "Edit names and archive state below — changes save automatically. "
            "Archived projects are visible here and can be unarchived. "
            'Check "Delete" to mark projects for removal.'
        )
    else:
        st.caption(
            "Edit names and archive state below — changes save automatically. "
            'Check "Delete" to mark projects for removal.'
        )
    edited_df = autosave_editor(
        display_df,
        key=editor_key,
        persist_fn=_persist_project_edits,
        num_rows="fixed",
        height="content",
        hide_index=True,
        column_order=["name", "is_archived", "open", "concluded", "confirm_delete"],
        column_config={
            "__project_id": None,
            "name": st.column_config.TextColumn("Project name", required=True),
            "is_archived": st.column_config.CheckboxColumn("Archived", default=False),
            "open": st.column_config.NumberColumn("Open", disabled=True),
            "concluded": st.column_config.NumberColumn("Concluded", disabled=True),
            "confirm_delete": st.column_config.CheckboxColumn(
                "Delete",
                default=False,
                help="Check to mark this project for deletion.",
            ),
        },
    )

    for err in st.session_state.pop(_AUTOSAVE_ERRORS_KEY, []):
        st.error(err)

    to_delete = _get_projects_to_delete(edited_df, projects)

    pending = st.session_state.get("projects_pending_deletion")
    if pending is not None:
        names = pending["names"]
        n = len(names)
        st.warning(
            f"You are about to permanently delete {n} project(s): **{', '.join(names)}**. "
            "This cannot be undone."
        )
        col1, col2, _ = st.columns([1, 1, 4])
        with col1:
            if st.button("Confirm and delete", key="projects_confirm_delete_btn", type="primary"):
                _success, errors, deleted, _updated = _apply_project_changes(edited_df, projects)
                if errors:
                    for msg in errors:
                        st.error(msg)
                else:
                    if deleted:
                        st.success(f"Deleted {deleted} project(s).")
                    else:
                        st.success("Changes saved.")
                del st.session_state["projects_pending_deletion"]
                st.rerun()
        with col2:
            if st.button("Cancel", key="projects_cancel_delete_btn"):
                del st.session_state["projects_pending_deletion"]
                st.rerun()
        return

    if to_delete and st.button("Delete selected", key="projects_delete_button", type="primary"):
        st.session_state["projects_pending_deletion"] = {
            "names": [name for _, name in to_delete],
        }
        st.rerun()
