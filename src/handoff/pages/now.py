"""Now page: control tower for action-required handoffs.

Shows items that need attention (next_check due or deadline at risk).
Each item is in an expander with Snooze, Edit, and Close actions.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from handoff.dates import add_business_days, format_date_smart, format_risk_reason
from handoff.models import Project, Todo, TodoStatus
from handoff.services import (
    complete_todo,
    create_todo,
    get_deadline_near_days,
    list_helpers,
    list_projects,
    query_now_items,
    query_upcoming_handoffs,
    snooze_todo,
    update_todo,
)


def _render_filters(
    *,
    project_by_name: dict[str, Project],
    helpers: list[str],
    key_prefix: str,
) -> tuple[list[int] | None, list[str] | None, str | None]:
    """Render Project, Who, and search filters.

    Args:
        project_by_name: Map of project name to Project for id lookup.
        helpers: List of helper names for the Who filter.
        key_prefix: Prefix for Streamlit widget keys.

    Returns:
        Tuple of (project_ids or None, helper_names or None, search_text or None).
    """
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
    project_ids = []
    for n in project_filters:
        if n in project_by_name:
            pid = project_by_name[n].id
            if pid is not None:
                project_ids.append(pid)
    return project_ids or None, helper_filters or None, search_text or None


def _render_item(
    todo: Todo,
    at_risk: bool,
    key_prefix: str,
    *,
    project_by_name: dict[str, Project],
) -> None:
    """Render one handoff item in an expander with Snooze, Edit, and Close.

    Args:
        todo: The handoff item to render.
        at_risk: Whether to show deadline-at-risk styling.
        key_prefix: Prefix for Streamlit widget keys.
        project_by_name: Map of project name to Project for form lookup.
    """
    todo_id = todo.id
    if todo_id is None:
        return
    project_name = todo.project.name if todo.project else "—"
    who = (todo.helper or "").strip() or "—"
    need_back = todo.name or "—"
    next_check_str = format_date_smart(todo.next_check)
    deadline_str = format_date_smart(todo.deadline) if todo.deadline else "—"
    context = (todo.notes or "").strip()

    # Header: risk (if at_risk) → **Need back** → Who → dates → Project (last, no bold)
    risk_prefix = ""
    if at_risk and todo.deadline:
        risk_prefix = f"🔴 {format_risk_reason(todo.deadline)} — "
    need_trunc = f"{need_back[:40]}…" if len(need_back) > 40 else need_back
    need_bold = f"**{need_trunc}**"

    # Date segment: when at_risk, omit ⏰ (risk already encodes deadline); else show both
    if at_risk and todo.deadline:
        date_part = f"👀 {next_check_str}"
    elif todo.deadline:
        date_part = f"👀 {next_check_str} · ⏰ {deadline_str}"
    else:
        date_part = f"👀 {next_check_str}"

    segments = [need_bold, who, date_part, project_name]
    core = " · ".join(segments)
    header = risk_prefix + core

    editing = st.session_state.get("now_editing_todo_id") == todo_id

    with st.expander(header, expanded=editing):
        if editing:
            _render_edit_form(
                todo=todo,
                project_by_name=project_by_name,
                key_prefix=f"{key_prefix}_edit_{todo_id}",
            )
        else:
            # Actions at top, then Context
            today = date.today()
            with st.popover("Actions"):
                r1c1, r1c2 = st.columns(2)
                with r1c1:
                    if st.button("Edit", key=f"{key_prefix}_edit_btn_{todo_id}"):
                        st.session_state["now_editing_todo_id"] = todo_id
                        st.rerun()
                with r1c2:
                    if st.button("✓ Close", key=f"{key_prefix}_close_{todo_id}"):
                        complete_todo(todo_id)
                        st.rerun()
                r2c1, r2c2 = st.columns(2)
                with r2c1:
                    custom_date = st.date_input(
                        "Date",
                        value=add_business_days(today, 1),
                        key=f"{key_prefix}_custom_{todo_id}",
                        label_visibility="collapsed",
                    )
                with r2c2:
                    if st.button("Snooze", key=f"{key_prefix}_snooze_btn_{todo_id}"):
                        snooze_todo(todo_id, to_date=custom_date)
                        st.rerun()

            if context:
                st.markdown("**Context:**")
                st.markdown(context)
            else:
                st.caption("No context.")


def _render_edit_form(
    todo: Todo,
    project_by_name: dict[str, Project],
    key_prefix: str,
) -> None:
    """Render edit form for a handoff item.

    Args:
        todo: The handoff item being edited.
        project_by_name: Map of project name to Project for form lookup.
        key_prefix: Prefix for Streamlit widget keys.
    """
    todo_id = todo.id
    if todo_id is None:
        return
    project_names = list(project_by_name)
    with st.form(key=f"{key_prefix}_form"):
        proj_idx = (
            project_names.index(todo.project.name)
            if todo.project and todo.project.name in project_names
            else 0
        )
        project_name = st.selectbox(
            "Project",
            options=project_names,
            index=proj_idx,
            key=f"{key_prefix}_project",
        )
        who = st.text_input(
            "Who",
            value=(todo.helper or "").strip(),
            placeholder="Person you're waiting on",
            key=f"{key_prefix}_who",
        )
        need_back = st.text_input(
            "Need back",
            value=todo.name or "",
            placeholder="Deliverable you need returned",
            key=f"{key_prefix}_need",
        )
        next_check = st.date_input(
            "Next check",
            value=todo.next_check or date.today(),
            key=f"{key_prefix}_next",
        )
        deadline = st.date_input(
            "Deadline (optional)",
            value=todo.deadline,
            key=f"{key_prefix}_deadline",
        )
        context = st.text_area(
            "Context (optional)",
            value=(todo.notes or "").strip(),
            placeholder="Notes, links, markdown…",
            key=f"{key_prefix}_context",
        )
        col1, col2 = st.columns(2)
        with col1:
            submitted = st.form_submit_button("Save")
        with col2:
            cancelled = st.form_submit_button("Cancel")
        if submitted:
            need_back_stripped = (need_back or "").strip()
            if not need_back_stripped:
                st.error("Need back is required.")
            elif project_name not in project_by_name:
                st.error("Select a project.")
            else:
                proj_id = project_by_name[project_name].id
                if proj_id is None:
                    st.error("Select a valid project.")
                else:
                    update_todo(
                        todo_id,
                        project_id=proj_id,
                        name=need_back_stripped,
                        helper=who.strip() or None,
                        next_check=next_check,
                        deadline=deadline if deadline else None,
                        notes=context.strip() or None,
                    )
                    if "now_editing_todo_id" in st.session_state:
                        del st.session_state["now_editing_todo_id"]
                    st.success("Saved.")
                    st.rerun()
        if cancelled:
            if "now_editing_todo_id" in st.session_state:
                del st.session_state["now_editing_todo_id"]
            st.rerun()


def _render_add_form(
    project_by_name: dict[str, Project],
    helpers: list[str],
    key_prefix: str,
) -> None:
    """Render form to add a new handoff item.

    Args:
        project_by_name: Map of project name to Project for form lookup.
        helpers: List of helper names (unused but kept for UI symmetry).
        key_prefix: Prefix for Streamlit widget keys.
    """
    with (
        st.expander("➕ Add handoff", expanded=False),
        st.form(key=f"{key_prefix}_add_form", clear_on_submit=True),
    ):
        project_names = list(project_by_name)
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
                proj_id = project_by_name[project_name].id
                if proj_id is None:
                    st.error("Select a valid project.")
                else:
                    create_todo(
                        project_id=proj_id,
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
    project_by_name = {p.name: p for p in projects}
    project_ids, helper_names, search_text = _render_filters(
        project_by_name=project_by_name,
        helpers=helpers,
        key_prefix="now",
    )

    deadline_near_days = get_deadline_near_days()
    items = query_now_items(
        project_ids=project_ids,
        helper_names=helper_names,
        search_text=search_text or None,
        deadline_near_days=deadline_near_days,
    )

    upcoming = query_upcoming_handoffs(
        project_ids=project_ids,
        helper_names=helper_names,
        search_text=search_text or None,
        deadline_near_days=deadline_near_days,
    )

    _render_add_form(project_by_name, helpers, "now")

    st.markdown("---")
    st.markdown("**Action required**")
    if not items:
        st.info("Nothing needs attention right now. Add handoffs or check back later.")
    else:
        for todo, at_risk in items:
            _render_item(
                todo,
                at_risk,
                "now",
                project_by_name=project_by_name,
            )

    st.markdown("---")
    st.markdown("**Upcoming**")
    if not upcoming:
        st.caption("No upcoming handoffs.")
    else:
        for todo in upcoming:
            _render_item(
                todo,
                at_risk=False,
                key_prefix="now_upcoming",
                project_by_name=project_by_name,
            )
