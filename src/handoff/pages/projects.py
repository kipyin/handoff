"""Projects page implementation for the engagement to-do app."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from handoff.data import (
    archive_project,
    create_project,
    delete_project,
    get_projects_with_todo_summary,
    rename_project,
    unarchive_project,
)


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


# New pure-logic helpers for testability


def _build_projects_display_rows(
    summary_list: list[dict],
) -> list[dict]:
    """Build display row dicts for the projects table from get_projects_with_todo_summary.

    Args:
        summary_list: List of dicts with "project" and "handoff", "done", "canceled" counts.

    Returns:
        List of dicts with __project_id, name, is_archived, handoff, done, canceled,
        confirm_delete=False.

    """
    rows = []
    for item in summary_list:
        p = item["project"]
        rows.append(
            {
                "__project_id": p.id,
                "name": p.name,
                "is_archived": getattr(p, "is_archived", False),
                "handoff": item["handoff"],
                "done": item["done"],
                "canceled": item["canceled"],
                "confirm_delete": False,
            }
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
    """Compare UI-edited DataFrame to current projects and produce a list of changes.

    Returns (valid, errors, changes). Changes are dicts with a 'type' key: 'rename', 'archive',
    'unarchive', 'delete'.
    """
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


def render_projects_page() -> None:
    """Render the projects management page as a table with Save changes."""
    st.subheader("Projects")
    _render_create_project_form()

    show_archived = st.checkbox(
        "Show archived projects",
        key="projects_show_archived",
        help="Include archived projects so you can review or unarchive them.",
    )

    summary_list = get_projects_with_todo_summary(include_archived=show_archived)
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
    display_df = pd.DataFrame(_build_projects_display_rows(summary_list))

    st.caption(
        'Edit names and archive state below. Enable "Show archived projects" to review '
        'or unarchive hidden items. Check "Confirm delete" for projects to remove, then '
        "click Save changes."
    )
    edited_df = st.data_editor(
        display_df,
        num_rows="fixed",
        height="content",
        key="projects_table",
        hide_index=True,
        column_order=["name", "is_archived", "handoff", "done", "canceled", "confirm_delete"],
        column_config={
            "__project_id": None,
            "name": st.column_config.TextColumn("Project name", required=True),
            "is_archived": st.column_config.CheckboxColumn("Archived", default=False),
            "handoff": st.column_config.NumberColumn("Handoff", disabled=True),
            "done": st.column_config.NumberColumn("Done", disabled=True),
            "canceled": st.column_config.NumberColumn("Canceled", disabled=True),
            "confirm_delete": st.column_config.CheckboxColumn(
                "Delete",
                default=False,
                help="Check to mark this project for deletion. Click Save changes to apply.",
            ),
        },
    )

    # Count rows marked for deletion for confirmation.
    to_delete = _get_projects_to_delete(edited_df, projects)

    # Show confirmation UI when user previously clicked Save with deletions pending.
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
                success, errors, deleted, updated = _apply_project_changes(edited_df, projects)
                if errors:
                    for msg in errors:
                        st.error(msg)
                else:
                    if deleted and updated:
                        st.success(f"Deleted {deleted} project(s); other changes saved.")
                    elif deleted:
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

    if st.button("Save changes", key="projects_save_button", type="primary"):
        if to_delete:
            st.session_state["projects_pending_deletion"] = {
                "names": [name for _, name in to_delete],
            }
            st.rerun()
        else:
            success, errors, deleted, updated = _apply_project_changes(edited_df, projects)
            if errors:
                for msg in errors:
                    st.error(msg)
            elif deleted or updated:
                if deleted and updated:
                    st.success(f"Deleted {deleted} project(s); other changes saved.")
                elif deleted:
                    st.success(f"Deleted {deleted} project(s).")
                else:
                    st.success("Changes saved.")
                st.rerun()
            else:
                st.info("No changes to save.")
