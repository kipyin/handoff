"""Now page: control tower for handoffs.

Shows four sections: Risk | Action | Upcoming | Concluded.
Goal: minimize risks by clearing actions on time.
"""

from __future__ import annotations

from datetime import date

import pandas as pd
import streamlit as st

from handoff.dates import add_business_days, format_date_smart, format_risk_reason
from handoff.models import Handoff, Project
from handoff.search_parse import parse_search_query
from handoff.services import (
    conclude_handoff,
    create_handoff,
    get_deadline_near_days,
    list_pitchmen_with_open_handoffs,
    list_projects,
    query_concluded_handoffs,
    query_now_items,
    query_upcoming_handoffs,
    snooze_handoff,
    update_handoff,
)
from handoff.services import (
    get_handoff_close_date as _get_close_date,
)


def _render_filters(
    *,
    project_by_name: dict[str, Project],
    pitchmen: list[str],
    key_prefix: str,
) -> tuple[list[int] | None, list[str] | None, str | None]:
    """Render Project, Who, and search filters.

    Args:
        project_by_name: Map of project name to Project for id lookup.
        pitchmen: List of pitchman names for the Who filter.
        key_prefix: Prefix for Streamlit widget keys.

    Returns:
        Tuple of (project_ids or None, pitchman_names or None, search_text or None).
    """
    project_names = list(project_by_name)
    col1, col2, col3 = st.columns([2, 1, 1])
    with col1:
        search_text = st.text_input(
            "Search",
            placeholder="Need back, @today, @due this week…",
            key=f"{key_prefix}_search",
        ).strip()
    with col2:
        project_filters = st.multiselect(
            "Project",
            options=project_names,
            default=[],
            key=f"{key_prefix}_projects",
        )
    with col3:
        pitchman_filters = st.multiselect(
            "Who",
            options=pitchmen,
            default=[],
            key=f"{key_prefix}_pitchmen",
        )
    project_ids = []
    for n in project_filters:
        if n in project_by_name:
            pid = project_by_name[n].id
            if pid is not None:
                project_ids.append(pid)
    return project_ids or None, pitchman_filters or None, search_text or None


def _render_item(
    handoff: Handoff,
    at_risk: bool,
    key_prefix: str,
    *,
    project_by_name: dict[str, Project],
) -> None:
    """Render one handoff item in an expander with Snooze, Edit, and Conclude.

    Args:
        handoff: The handoff item to render.
        at_risk: Whether to show deadline-at-risk styling.
        key_prefix: Prefix for Streamlit widget keys.
        project_by_name: Map of project name to Project for form lookup.
    """
    handoff_id = handoff.id
    if handoff_id is None:
        return
    project_name = handoff.project.name if handoff.project else "—"
    who = (handoff.pitchman or "").strip() or "—"
    need_back = handoff.need_back or "—"
    next_check_str = format_date_smart(handoff.next_check)
    deadline_str = format_date_smart(handoff.deadline) if handoff.deadline else "—"
    context = (handoff.notes or "").strip()

    risk_prefix = ""
    if at_risk and handoff.deadline:
        risk_prefix = f"⏰ {format_risk_reason(handoff.deadline)} — "
    need_trunc = f"{need_back[:40]}…" if len(need_back) > 40 else need_back
    need_bold = f"**{need_trunc}**"

    if at_risk and handoff.deadline:
        date_part = f"Check-in {next_check_str}"
    elif handoff.deadline:
        date_part = f"Check-in {next_check_str} · ⏰ {deadline_str}"
    else:
        date_part = f"Check-in {next_check_str}"

    segments = [need_bold, who, date_part, project_name]
    core = " · ".join(segments)
    header = risk_prefix + core

    editing = st.session_state.get("now_editing_handoff_id") == handoff_id

    with st.expander(header, expanded=editing):
        if editing:
            _render_edit_form(
                handoff=handoff,
                project_by_name=project_by_name,
                key_prefix=f"{key_prefix}_edit_{handoff_id}",
            )
        else:
            today = date.today()
            with st.popover("Actions"):
                r1c1, r1c2 = st.columns(2)
                with r1c1:
                    if st.button("Edit", key=f"{key_prefix}_edit_btn_{handoff_id}"):
                        st.session_state["now_editing_handoff_id"] = handoff_id
                        st.rerun()
                with r1c2:
                    if st.button("✓ Conclude", key=f"{key_prefix}_conclude_{handoff_id}"):
                        conclude_handoff(handoff_id)
                        st.rerun()
                r2c1, r2c2 = st.columns(2)
                with r2c1:
                    custom_date = st.date_input(
                        "Date",
                        value=add_business_days(today, 1),
                        key=f"{key_prefix}_custom_{handoff_id}",
                        label_visibility="collapsed",
                    )
                with r2c2:
                    if st.button("Snooze", key=f"{key_prefix}_snooze_btn_{handoff_id}"):
                        snooze_handoff(handoff_id, to_date=custom_date)
                        st.rerun()

            if context:
                st.markdown("**Context:**")
                st.markdown(context)
            else:
                st.caption("No context.")


def _render_edit_form(
    handoff: Handoff,
    project_by_name: dict[str, Project],
    key_prefix: str,
) -> None:
    """Render edit form for a handoff item.

    Args:
        handoff: The handoff item being edited.
        project_by_name: Map of project name to Project for form lookup.
        key_prefix: Prefix for Streamlit widget keys.
    """
    handoff_id = handoff.id
    if handoff_id is None:
        return
    project_names = list(project_by_name)
    with st.form(key=f"{key_prefix}_form"):
        proj_idx = (
            project_names.index(handoff.project.name)
            if handoff.project and handoff.project.name in project_names
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
            value=(handoff.pitchman or "").strip(),
            placeholder="Person you're waiting on",
            key=f"{key_prefix}_who",
        )
        need_back = st.text_input(
            "Need back",
            value=handoff.need_back or "",
            placeholder="Deliverable you need returned",
            key=f"{key_prefix}_need",
        )
        next_check = st.date_input(
            "Next check",
            value=handoff.next_check or date.today(),
            key=f"{key_prefix}_next",
        )
        deadline = st.date_input(
            "Deadline (optional)",
            value=handoff.deadline,
            key=f"{key_prefix}_deadline",
        )
        context = st.text_area(
            "Context (optional)",
            value=(handoff.notes or "").strip(),
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
                    update_handoff(
                        handoff_id,
                        project_id=proj_id,
                        need_back=need_back_stripped,
                        pitchman=who.strip() or None,
                        next_check=next_check,
                        deadline=deadline if deadline else None,
                        notes=context.strip() or None,
                    )
                    if "now_editing_handoff_id" in st.session_state:
                        del st.session_state["now_editing_handoff_id"]
                    st.success("Saved.")
                    st.rerun()
        if cancelled:
            if "now_editing_handoff_id" in st.session_state:
                del st.session_state["now_editing_handoff_id"]
            st.rerun()


def _render_add_form(
    project_by_name: dict[str, Project],
    pitchmen: list[str],
    key_prefix: str,
) -> None:
    """Render form to add a new handoff item.

    Args:
        project_by_name: Map of project name to Project for form lookup.
        pitchmen: List of pitchman names (unused but kept for UI symmetry).
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
                    create_handoff(
                        project_id=proj_id,
                        need_back=need_back_stripped,
                        next_check=next_check,
                        deadline=deadline if deadline else None,
                        pitchman=who.strip() or None,
                        notes=context.strip() or None,
                    )
                    st.success("Added.")
                    st.rerun()


def _concluded_to_dataframe(handoffs: list[Handoff]) -> pd.DataFrame:
    """Build a DataFrame for the Concluded section.

    Args:
        handoffs: Sorted list of concluded handoffs.

    Returns:
        DataFrame with columns: Need back, Who, Project, Next check,
        Deadline, Concluded.
    """
    rows = []
    for h in handoffs:
        project_name = h.project.name if h.project else "—"
        close = _get_close_date(h)
        close_str = format_date_smart(close) if close else "—"
        rows.append(
            {
                "Need back": h.need_back or "—",
                "Who": (h.pitchman or "").strip() or "—",
                "Project": project_name,
                "Next check": format_date_smart(h.next_check),
                "Deadline": format_date_smart(h.deadline) if h.deadline else "—",
                "Concluded": close_str,
            }
        )
    return pd.DataFrame(rows)


def render_now_page() -> None:
    """Render the Now page with four sections: Risk | Action | Upcoming | Concluded."""
    st.subheader("Now")
    st.caption(
        "Minimize risks by clearing actions on time. "
        "Use Snooze to follow up later, or Conclude when done."
    )

    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one on the Projects page.")
        return

    pitchmen = list_pitchmen_with_open_handoffs()
    project_by_name = {p.name: p for p in projects}
    project_ids, pitchman_names, search_text = _render_filters(
        project_by_name=project_by_name,
        pitchmen=pitchmen,
        key_prefix="now",
    )

    parsed = parse_search_query(search_text or "")
    deadline_near_days = get_deadline_near_days()
    items = query_now_items(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=parsed.text_query,
        deadline_near_days=deadline_near_days,
        next_check_min=parsed.next_check_min,
        next_check_max=parsed.next_check_max,
        deadline_min=parsed.deadline_min,
        deadline_max=parsed.deadline_max,
    )

    upcoming = query_upcoming_handoffs(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=parsed.text_query,
        deadline_near_days=deadline_near_days,
        next_check_min=parsed.next_check_min,
        next_check_max=parsed.next_check_max,
        deadline_min=parsed.deadline_min,
        deadline_max=parsed.deadline_max,
    )

    _render_add_form(project_by_name, pitchmen, "now")

    # --- Risk section (placeholder — real query in Phase 2) ---
    st.markdown("---")
    st.markdown("**Risk**")
    st.caption("At-risk handoffs (approaching deadline with delays). Coming soon.")

    # --- Action section ---
    st.markdown("---")
    st.markdown("**Action required**")
    if not items:
        st.info("Nothing needs attention right now. Add handoffs or check back later.")
    else:
        for handoff, at_risk in items:
            _render_item(
                handoff,
                at_risk,
                "now",
                project_by_name=project_by_name,
            )

    # --- Upcoming section ---
    st.markdown("---")
    st.markdown("**Upcoming**")
    if not upcoming:
        st.caption("No upcoming handoffs.")
    else:
        for handoff in upcoming:
            _render_item(
                handoff,
                at_risk=False,
                key_prefix="now_upcoming",
                project_by_name=project_by_name,
            )

    # --- Concluded section ---
    st.markdown("---")
    with st.expander("Concluded >"):
        concluded = query_concluded_handoffs(
            project_ids=project_ids,
            pitchman_names=pitchman_names,
            search_text=parsed.text_query,
            include_archived_projects=True,
        )
        if not concluded:
            st.caption("No concluded handoffs.")
        else:
            df = _concluded_to_dataframe(concluded)
            st.dataframe(
                df,
                key="now_concluded_df",
                use_container_width=True,
                hide_index=True,
            )
