"""Now page: control tower for handoffs.

Shows four sections: Risk | Action | Upcoming | Concluded.
Goal: minimize risks by clearing actions on time.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from handoff.dates import add_business_days, format_date_smart, format_risk_reason
from handoff.models import CheckIn, CheckInType, Handoff, Project
from handoff.services import (
    add_check_in,
    conclude_handoff,
    create_handoff,
    get_now_snapshot,
    list_pitchmen_with_open_handoffs,
    list_projects,
    reopen_handoff,
    snooze_handoff,
    update_handoff,
)

_NOW_FLASH_SUCCESS_KEY = "now_flash_success"


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


def _check_in_header(check_in: CheckIn) -> str:
    """Return a compact check-in header line for trail expanders."""
    check_label = check_in.check_in_type.value.replace("_", " ")
    check_label = check_label.title()
    base = f"[{check_label}] {format_date_smart(check_in.check_in_date)}"
    note = (check_in.note or "").strip()
    if not note:
        return base
    preview = note.replace("\n", " ").strip()
    if len(preview) > 40:
        preview = f"{preview[:40]}…"
    return f"{base} — {preview}"


def _render_check_in_trail(handoff: Handoff) -> None:
    """Render the check-in trail using collapsed expanders."""
    if not handoff.check_ins:
        st.caption("No check-ins yet.")
        return
    st.markdown("**Check-in trail**")
    for check_in in handoff.check_ins:
        with st.expander(_check_in_header(check_in), expanded=False):
            note = (check_in.note or "").strip()
            if note:
                st.markdown(note)
            else:
                st.caption("No note.")


def _is_check_in_due(handoff: Handoff) -> bool:
    """Return True when this handoff needs a check-in decision now."""
    return handoff.next_check is not None and handoff.next_check <= date.today()


def _set_flash_success(message: str) -> None:
    """Persist one success message for display after the next rerun."""
    st.session_state[_NOW_FLASH_SUCCESS_KEY] = message


def _render_check_in_flow(handoff: Handoff, *, key_prefix: str) -> None:
    """Render on-track/delayed/conclude check-in forms for open handoffs."""
    handoff_id = handoff.id
    if handoff_id is None:
        return

    today = date.today()
    if _is_check_in_due(handoff):
        st.caption("Check-in due now. Record today's status.")
    else:
        planned_label = format_date_smart(handoff.next_check)
        st.caption(f"Optional early check-in. Planned next check: {planned_label}.")

    mode_key = f"{key_prefix}_check_in_mode_{handoff_id}"
    selected_mode = st.session_state.get(mode_key)
    c1, c2, c3 = st.columns(3)
    with c1:
        if st.button("On-track", key=f"{key_prefix}_on_track_btn_{handoff_id}"):
            st.session_state[mode_key] = "on_track"
            st.rerun()
    with c2:
        if st.button("Delayed", key=f"{key_prefix}_delayed_btn_{handoff_id}"):
            st.session_state[mode_key] = "delayed"
            st.rerun()
    with c3:
        if st.button("Conclude", key=f"{key_prefix}_conclude_btn_{handoff_id}"):
            st.session_state[mode_key] = "concluded"
            st.rerun()

    if selected_mode not in {"on_track", "delayed", "concluded"}:
        return

    form_key = f"{key_prefix}_check_in_form_{handoff_id}_{selected_mode}"
    with st.form(key=form_key):
        if selected_mode == "concluded":
            note = st.text_area(
                "Conclusion note (optional)",
                key=f"{form_key}_note",
            )
            save = st.form_submit_button("Save conclude check-in")
        else:
            note_label = "Note (optional)" if selected_mode == "on_track" else "Reason (optional)"
            note = st.text_area(note_label, key=f"{form_key}_note")
            default_next_check = (
                handoff.next_check
                if handoff.next_check is not None and handoff.next_check > today
                else add_business_days(today, 1)
            )
            next_check = st.date_input(
                "Next check-in",
                value=default_next_check,
                key=f"{form_key}_next_check",
            )
            save = st.form_submit_button("Save check-in")
        cancel = st.form_submit_button("Cancel")

        if save:
            note_value = note.strip() or None
            if selected_mode == "concluded":
                conclude_handoff(handoff_id, note=note_value)
                _set_flash_success("Checked in today as concluded.")
            else:
                check_in_type = (
                    CheckInType.ON_TRACK if selected_mode == "on_track" else CheckInType.DELAYED
                )
                add_check_in(
                    handoff_id,
                    check_in_type=check_in_type,
                    note=note_value,
                    next_check_date=next_check,
                )
                _set_flash_success(
                    f"Checked in today; next check set to {format_date_smart(next_check)}."
                )
            st.session_state.pop(mode_key, None)
            st.rerun()
        if cancel:
            st.session_state.pop(mode_key, None)
            st.rerun()


def _render_reopen_flow(handoff: Handoff, *, key_prefix: str) -> None:
    """Render append-only reopen controls for concluded handoffs."""
    handoff_id = handoff.id
    if handoff_id is None:
        return

    mode_key = f"{key_prefix}_reopen_mode_{handoff_id}"
    if st.button("Reopen", key=f"{key_prefix}_reopen_btn_{handoff_id}"):
        st.session_state[mode_key] = "reopen"
        st.rerun()
    if st.session_state.get(mode_key) != "reopen":
        return

    today = date.today()
    default_next_check = add_business_days(today, 1)
    form_key = f"{key_prefix}_reopen_form_{handoff_id}"
    with st.form(key=form_key):
        note = st.text_area(
            "Reason (optional)",
            placeholder="reopen: waiting on revised doc",
            key=f"{form_key}_note",
        )
        next_check = st.date_input(
            "Next check-in",
            value=default_next_check,
            key=f"{form_key}_next_check",
        )
        save = st.form_submit_button("Save reopen")
        cancel = st.form_submit_button("Cancel")

        if save:
            note_value = note.strip() or None
            try:
                reopen_handoff(
                    handoff_id,
                    note=note_value,
                    next_check_date=next_check,
                )
            except ValueError as exc:
                st.error(str(exc))
            else:
                _set_flash_success(
                    f"Checked in today; next check set to {format_date_smart(next_check)}."
                )
                st.session_state.pop(mode_key, None)
                st.rerun()
        if cancel:
            st.session_state.pop(mode_key, None)
            st.rerun()


def _render_item(
    handoff: Handoff,
    key_prefix: str,
    *,
    project_by_name: dict[str, Project],
    is_risk: bool = False,
    show_check_in_controls: bool = False,
    allow_actions: bool = True,
    allow_reopen: bool = False,
) -> None:
    """Render one handoff item in an expander."""
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
    if is_risk and handoff.deadline:
        risk_prefix = f"⏰ {format_risk_reason(handoff.deadline)} — "
    need_trunc = f"{need_back[:40]}…" if len(need_back) > 40 else need_back
    need_bold = f"**{need_trunc}**"

    if is_risk and handoff.deadline:
        date_part = f"Check-in {next_check_str}"
    elif handoff.deadline:
        date_part = f"Check-in {next_check_str} · ⏰ {deadline_str}"
    else:
        date_part = f"Check-in {next_check_str}"

    segments = [need_bold, who, date_part, project_name]
    core = " · ".join(segments)
    header = risk_prefix + core

    editing = allow_actions and st.session_state.get("now_editing_handoff_id") == handoff_id
    with st.expander(header, expanded=editing):
        if editing:
            _render_edit_form(
                handoff=handoff,
                project_by_name=project_by_name,
                key_prefix=f"{key_prefix}_edit_{handoff_id}",
            )
        else:
            if allow_actions and show_check_in_controls:
                _render_check_in_flow(handoff, key_prefix=key_prefix)

            if allow_actions:
                today = date.today()
                with st.popover("Actions"):
                    r1c1, r1c2 = st.columns(2)
                    with r1c1:
                        if st.button("Edit", key=f"{key_prefix}_edit_btn_{handoff_id}"):
                            st.session_state["now_editing_handoff_id"] = handoff_id
                            st.rerun()
                    with r1c2:
                        custom_date = st.date_input(
                            "Date",
                            value=add_business_days(today, 1),
                            key=f"{key_prefix}_custom_{handoff_id}",
                            label_visibility="collapsed",
                        )
                    with r1c2:
                        if st.button("Snooze", key=f"{key_prefix}_snooze_btn_{handoff_id}"):
                            snooze_handoff(handoff_id, to_date=custom_date)
                            st.rerun()
            elif allow_reopen:
                _render_reopen_flow(handoff, key_prefix=key_prefix)

            if context:
                st.markdown("**Context:**")
                st.markdown(context)
            else:
                st.caption("No context.")
            _render_check_in_trail(handoff)


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


def render_now_page() -> None:
    """Render the Now page with four sections: Risk | Action | Upcoming | Concluded."""
    st.subheader("Now")
    st.caption(
        "Minimize risks by clearing actions on time. "
        "Use Snooze to follow up later, or Conclude when done."
    )
    flash_message = st.session_state.pop(_NOW_FLASH_SUCCESS_KEY, None)
    if flash_message:
        st.success(flash_message)

    include_archived_projects = st.checkbox(
        "Include archived projects",
        value=False,
        key="now_include_archived_projects",
    )
    projects = list_projects(include_archived=include_archived_projects)
    if not projects:
        if include_archived_projects:
            st.info("No projects yet. Create one on the Projects page.")
        else:
            all_projects = list_projects(include_archived=True)
            if all_projects:
                st.info(
                    "No active projects. Turn on 'Include archived projects' to view archived work."
                )
            else:
                st.info("No projects yet. Create one on the Projects page.")
        return

    pitchmen = list_pitchmen_with_open_handoffs(include_archived_projects=include_archived_projects)
    project_by_name = {p.name: p for p in projects}
    project_ids, pitchman_names, search_text = _render_filters(
        project_by_name=project_by_name,
        pitchmen=pitchmen,
        key_prefix="now",
    )

    snapshot = get_now_snapshot(
        include_archived_projects=include_archived_projects,
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=search_text,
        projects=projects,
        pitchmen=pitchmen,
    )

    _render_add_form(project_by_name, snapshot.pitchmen, "now")

    # --- Risk section ---
    st.markdown("---")
    st.markdown("**Risk**")
    if not snapshot.risk:
        st.caption("No at-risk handoffs.")
    else:
        for handoff in snapshot.risk:
            _render_item(
                handoff,
                "now_risk",
                project_by_name=project_by_name,
                is_risk=True,
                show_check_in_controls=True,
                allow_actions=True,
            )

    # --- Action section ---
    st.markdown("---")
    st.markdown("**Action required**")
    if not snapshot.action:
        st.info("Nothing needs attention right now. Add handoffs or check back later.")
    else:
        for handoff in snapshot.action:
            _render_item(
                handoff,
                "now_action",
                project_by_name=project_by_name,
                show_check_in_controls=True,
            )

    # --- Upcoming section ---
    st.markdown("---")
    st.markdown("**Upcoming**")
    if not snapshot.upcoming:
        st.caption("No upcoming handoffs.")
    else:
        for handoff in snapshot.upcoming:
            _render_item(
                handoff,
                key_prefix="now_upcoming",
                project_by_name=project_by_name,
                show_check_in_controls=True,
            )

    # --- Concluded section ---
    st.markdown("---")
    st.markdown("**Concluded**")
    if not snapshot.concluded:
        st.caption("No concluded handoffs.")
    else:
        for handoff in snapshot.concluded:
            _render_item(
                handoff,
                key_prefix="now_concluded",
                project_by_name=project_by_name,
                allow_actions=False,
                allow_reopen=True,
            )
