"""Projects page implementation for the engagement to-do app."""

from __future__ import annotations

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


def _render_project_row(*, project, summary: dict) -> None:
    """Render a single project's summary, rename, and delete controls."""
    total = summary.get("total", 0)
    delegated = summary.get("delegated", 0)
    done = summary.get("done", 0)
    canceled = summary.get("canceled", 0)

    is_archived = getattr(project, "is_archived", False)
    title = project.name
    if is_archived:
        title = f"{title} (archived)"

    st.markdown(f"### {title}")
    st.caption(f"{total} todos (delegated: {delegated}, done: {done}, canceled: {canceled})")

    rename_col, archive_col, delete_col = st.columns([3, 2, 2])
    with rename_col:
        new_name = (
            st.text_input(
                "Rename project",
                value=project.name,
                key=f"projects_rename_name_{project.id}",
            )
            or project.name
        )
        if st.button("Rename", key=f"projects_rename_button_{project.id}"):
            cleaned = new_name.strip()
            if not cleaned:
                st.error("Project name cannot be empty.")
            elif cleaned == project.name:
                st.info("Name unchanged.")
            else:
                rename_project(project.id, cleaned)
                st.success("Project renamed.")
                st.rerun()

    with archive_col:
        if is_archived:
            if st.button("Unarchive", key=f"projects_unarchive_button_{project.id}"):
                ok = unarchive_project(project.id)
                if ok:
                    st.success("Project unarchived.")
                    st.rerun()
                else:
                    st.error("Project could not be unarchived.")
        else:
            if st.button(
                "Archive project",
                key=f"projects_archive_button_{project.id}",
                type="secondary",
            ):
                ok = archive_project(project.id)
                if ok:
                    st.success("Project archived.")
                    st.rerun()
                else:
                    st.error("Project could not be archived.")

    with delete_col:
        confirm = st.checkbox(
            "Confirm delete",
            key=f"projects_confirm_delete_{project.id}",
        )
        if st.button(
            "Delete project",
            key=f"projects_delete_button_{project.id}",
            disabled=not confirm,
            type="secondary",
        ):
            deleted = delete_project(project.id)
            if deleted:
                st.success("Project deleted.")
                st.rerun()
            else:
                st.error("Project could not be deleted.")


def render_projects_page() -> None:
    """Render the projects management page."""
    st.subheader("Projects")
    _render_create_project_form()

    show_archived = st.checkbox(
        "Show archived projects",
        key="projects_show_archived",
    )

    project_items = get_projects_with_todo_summary(include_archived=show_archived)
    if not project_items:
        st.info("No projects yet. Use the form above to create the first project.")
        return

    st.divider()
    for item in project_items:
        project = item["project"]
        _render_project_row(project=project, summary=item)
        st.divider()
