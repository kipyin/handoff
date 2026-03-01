"""Projects page implementation for the engagement to-do app."""

from __future__ import annotations

import pandas as pd
import streamlit as st

from handoff.data import (
    archive_project,
    create_project,
    delete_project,
    list_projects,
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


def _apply_project_changes(
    edited_df: pd.DataFrame,
    projects: list,
) -> tuple[bool, list[str], int, int]:
    """Apply table edits: renames, archive toggles, and deletions.

    Args:
        edited_df: The edited dataframe from the data_editor.
        projects: Current list of projects (same order/scope as when table was built).

    Returns:
        Tuple of (success, errors, deleted_count, updated_count).
    """
    project_by_id = {p.id: p for p in projects}
    errors: list[str] = []
    deleted = 0
    updated = 0
    for _, row in edited_df.iterrows():
        pid = row.get("__project_id")
        if pid is None or pd.isna(pid):
            continue
        pid = int(pid)
        project = project_by_id.get(pid)
        if not project:
            continue
        if row.get("confirm_delete"):
            if delete_project(pid):
                deleted += 1
            else:
                errors.append(f"Could not delete project \"{project.name}\".")
            continue
        new_name = (row.get("name") or "").strip()
        if not new_name:
            errors.append(f"Project name cannot be empty (id {pid}).")
            continue
        if new_name != project.name:
            rename_project(pid, new_name)
            updated += 1
        new_archived = bool(row.get("is_archived"))
        if new_archived != getattr(project, "is_archived", False):
            if new_archived:
                archive_project(pid)
            else:
                unarchive_project(pid)
            updated += 1
    return (len(errors) == 0, errors, deleted, updated)


def render_projects_page() -> None:
    """Render the projects management page as a table with Save changes."""
    st.subheader("Projects")
    _render_create_project_form()

    show_archived = st.checkbox(
        "Show archived projects",
        key="projects_show_archived",
    )

    projects = list_projects(include_archived=show_archived)
    if not projects:
        st.info("No projects yet. Use the form above to create the first project.")
        return

    rows = []
    for p in projects:
        rows.append(
            {
                "__project_id": p.id,
                "name": p.name,
                "is_archived": getattr(p, "is_archived", False),
                "confirm_delete": False,
            }
        )
    display_df = pd.DataFrame(rows)

    st.caption(
        "Edit names and archive state below. Check \"Confirm delete\" for projects to "
        "remove, then click Save changes."
    )
    edited_df = st.data_editor(
        display_df,
        num_rows="fixed",
        height="content",
        key="projects_table",
        hide_index=True,
        column_order=["name", "is_archived", "confirm_delete"],
        column_config={
            "__project_id": None,
            "name": st.column_config.TextColumn("Project name", required=True),
            "is_archived": st.column_config.CheckboxColumn("Archived", default=False),
            "confirm_delete": st.column_config.CheckboxColumn(
                "Delete",
                default=False,
                help="Check to mark this project for deletion. Click Save changes to apply.",
            ),
        },
    )

    # Count rows marked for deletion for confirmation.
    to_delete = []
    for _, row in edited_df.iterrows():
        pid = row.get("__project_id")
        if pid is None or pd.isna(pid):
            continue
        if row.get("confirm_delete"):
            project = next((p for p in projects if p.id == int(pid)), None)
            if project:
                to_delete.append((int(pid), project.name))

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
