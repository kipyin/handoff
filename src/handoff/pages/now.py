"""Now page: control tower for action-required handoffs.

Shows items that need attention (next_check due or deadline at risk).
Each item is in an expander with Snooze and Close actions.
"""

from __future__ import annotations

from datetime import date, timedelta

import streamlit as st

from handoff.data import (
    close_todo,
    create_todo,
    list_helpers,
    list_projects,
    query_now_items,
    snooze_todo,
)
from handoff.dates import format_next_check
from handoff.models import Todo, TodoStatus


def _render_filters(
    *,
    projects: list,
    helpers: list[str],
    key_prefix: str,
) -> tuple[list[int] | None, list[str] | None, str | None]:
    """Render Project, Who, and search filters. Return (project_ids, helper_names, search_text)."""
    project_by_name = {p.name: p for p in projects}
    project_names = list(project_by_name)
    col1, col2, col3 = st.columns(3)
    with col1:
        project_filters = st.multiselect(
            "Project",
            options=project_names,
            default=[],
            key=f"{key_prefix}_projects",
        )
    with col2:
        helper_filters = st.multiselect(
            "Who",
            options=helpers,
            default=[],
            key=f"{key_prefix}_helpers",
        )
    with col3:
        search_text = st.text_input(
            "Search",
            placeholder="Need back, context…",
            key=f"{key_prefix}_search",
        ).strip()
    project_ids = [
        pid
        for n in project_filters
        if n in project_by_name and (pid := project_by_name[n].id) is not None
    ]
    return project_ids or None, helper_filters or None, search_text or None


def _render_item(todo: Todo, at_risk: bool, key_prefix: str) -> None:
    """Render one handoff item in an expander with Snooze and Close."""
    todo_id = todo.id
    if todo_id is None:
        return
    project_name = todo.project.name if todo.project else "—"
    who = (todo.helper or "").strip() or "—"
    need_back = todo.name or "—"
    next_check_str = format_next_check(todo.next_check)
    deadline_str = str(todo.deadline) if todo.deadline else "—"
    context = (todo.notes or "").strip()

    # Header: project · who · need_back (truncated) + risk badge
    header = f"**{project_name}** · {who} · {need_back[:50]}{'…' if len(need_back) > 50 else ''}"
    header = f"🔴 RISK — {header}" if at_risk else f"📋 {header}"

    with st.expander(header, expanded=at_risk):
        st.markdown(f"**Need back:** {need_back}")
        st.markdown(f"**From:** {who}")
        st.markdown(f"**Project:** {project_name}")
        st.markdown(f"**Next check:** {next_check_str}")
        st.markdown(f"**Deadline:** {deadline_str}")
        if context:
            st.markdown("---")
            st.markdown("**Context:**")
            st.markdown(context)

        st.markdown("---")
        st.markdown("**Actions**")
        today = date.today()
        c1, c2, c3, c4 = st.columns(4)
        with c1:
            if st.button("+1d", key=f"{key_prefix}_snooze_1d_{todo_id}"):
                snooze_todo(todo_id, to_date=today + timedelta(days=1))
                st.rerun()
        with c2:
            if st.button("+3d", key=f"{key_prefix}_snooze_3d_{todo_id}"):
                snooze_todo(todo_id, to_date=today + timedelta(days=3))
                st.rerun()
        with c3:
            if st.button("+1w", key=f"{key_prefix}_snooze_1w_{todo_id}"):
                snooze_todo(todo_id, to_date=today + timedelta(days=7))
                st.rerun()
        with c4:
            custom_date = st.date_input(
                "Custom",
                value=today + timedelta(days=3),
                key=f"{key_prefix}_custom_{todo_id}",
            )
            if st.button("Snooze", key=f"{key_prefix}_snooze_btn_{todo_id}"):
                snooze_todo(todo_id, to_date=custom_date)
                st.rerun()
        if st.button("✓ Close", key=f"{key_prefix}_close_{todo_id}"):
            close_todo(todo_id)
            st.rerun()


def _render_add_form(projects: list, helpers: list[str], key_prefix: str) -> None:
    """Render form to add a new handoff item."""
    with (
        st.expander("➕ Add handoff", expanded=False),
        st.form(key=f"{key_prefix}_add_form", clear_on_submit=True),
    ):
        project_names = [p.name for p in projects]
        project_by_name = {p.name: p for p in projects}
        project_name = st.selectbox(
            "Project", options=project_names, key=f"{key_prefix}_add_project"
        )
        who = st.text_input(
            "Who", placeholder="Person you're waiting on", key=f"{key_prefix}_add_who"
        )
        need_back = st.text_input(
            "Need back",
            placeholder="Deliverable you need returned",
            key=f"{key_prefix}_add_need",
        )
        next_check = st.date_input(
            "Next check",
            value=date.today(),
            key=f"{key_prefix}_add_next",
        )
        deadline = st.date_input(
            "Deadline (optional)",
            value=None,
            key=f"{key_prefix}_add_deadline",
        )
        context = st.text_area(
            "Context (optional)",
            placeholder="Notes, links, markdown…",
            key=f"{key_prefix}_add_context",
        )
        submitted = st.form_submit_button("Add")
        if submitted:
            need_back_stripped = (need_back or "").strip()
            if not need_back_stripped:
                st.error("Need back is required.")
            elif project_name not in project_by_name:
                st.error("Select a project.")
            else:
                create_todo(
                    project_id=project_by_name[project_name].id,
                    name=need_back_stripped,
                    status=TodoStatus.HANDOFF,
                    next_check=next_check,
                    deadline=deadline if deadline else None,
                    helper=who.strip() or None,
                    notes=context.strip() or None,
                )
                st.success("Added.")
                st.rerun()


def render_now_page() -> None:
    """Render the Now page (control tower for action-required handoffs)."""
    st.subheader("Now")
    st.caption(
        "Items that need attention: next check due today or earlier, or deadline at risk. "
        "Use Snooze to follow up later, or Close when done."
    )

    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one on the Projects page.")
        return

    helpers = list_helpers()
    project_ids, helper_names, search_text = _render_filters(
        projects=projects,
        helpers=helpers,
        key_prefix="now",
    )

    items = query_now_items(
        project_ids=project_ids,
        helper_names=helper_names,
        search_text=search_text or None,
    )

    _render_add_form(projects, helpers, "now")

    st.markdown("---")
    st.markdown("**Action required**")
    if not items:
        st.info("Nothing needs attention right now. Add handoffs or check back later.")
        return

    for todo, at_risk in items:
        _render_item(todo, at_risk, "now")
