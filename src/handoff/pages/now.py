"""Now page: control tower for handoffs.

Shows four sections: Risk | Action | Upcoming | Concluded.
Goal: minimize risks by clearing actions on time.
"""

from __future__ import annotations

from datetime import date

import streamlit as st

from handoff.dates import add_business_days, format_date_smart, format_risk_reason
from handoff.instrumentation import time_action
from handoff.models import CheckIn, CheckInType, Handoff, Project
from handoff.services import (
    add_check_in,
    conclude_handoff,
    create_handoff,
    get_now_snapshot,
    list_pitchmen_with_open_handoffs,
    list_projects,
    reopen_handoff,
    update_handoff,
)

CHECK_IN_MODES = ["on_track", "delayed", "concluded"]
CHECK_IN_MODE_LABELS = {"on_track": "On-track", "delayed": "Delayed", "concluded": "Conclude"}

_NOW_FLASH_SUCCESS_KEY = "now_flash_success"
_NOW_FLASH_ERROR_KEY = "now_flash_error"
_NOW_ADD_EXPANDED_KEY = "now_add_expanded"


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


def _set_flash_error(message: str) -> None:
    """Persist one error message for display after the next rerun."""
    st.session_state[_NOW_FLASH_ERROR_KEY] = message


def _set_mode(*, mode_key: str, mode: str) -> None:
    """Set a local interaction mode in session state."""
    st.session_state[mode_key] = mode


def _clear_session_key(*, state_key: str) -> None:
    """Remove a session-state key when it exists."""
    st.session_state.pop(state_key, None)


def _expand_add_form() -> None:
    """Expand the Add handoff form (keyboard shortcut target)."""
    st.session_state[_NOW_ADD_EXPANDED_KEY] = True


def _collapse_add_form() -> None:
    """Collapse the Add handoff form."""
    st.session_state.pop(_NOW_ADD_EXPANDED_KEY, None)


def _set_editing_handoff(*, handoff_id: int) -> None:
    """Mark one handoff as currently being edited."""
    st.session_state["now_editing_handoff_id"] = handoff_id


def _save_check_in_submission(
    *,
    handoff_id: int,
    selected_mode: str,
    mode_key: str,
    note_key: str,
    next_check_key: str | None = None,
) -> None:
    """Persist a check-in form submission and clear form mode on success."""
    note_raw = st.session_state.get(note_key, "")
    note_value = str(note_raw).strip() or None

    if selected_mode == "concluded":
        with time_action("now_conclude"):
            conclude_handoff(handoff_id, note=note_value)
        _set_flash_success("Checked in today as concluded.")
        st.session_state.pop(mode_key, None)
        return

    if next_check_key is None:
        _set_flash_error("Select a valid next check-in date.")
        return
    next_check_value = st.session_state.get(next_check_key)
    if not isinstance(next_check_value, date):
        _set_flash_error("Select a valid next check-in date.")
        return

    check_in_type = CheckInType.ON_TRACK if selected_mode == "on_track" else CheckInType.DELAYED
    with time_action("now_check_in"):
        add_check_in(
            handoff_id,
            check_in_type=check_in_type,
            note=note_value,
            next_check_date=next_check_value,
        )
    _set_flash_success(
        f"Checked in today; next check set to {format_date_smart(next_check_value)}."
    )
    st.session_state.pop(mode_key, None)


def _save_reopen_submission(
    *,
    handoff_id: int,
    mode_key: str,
    note_key: str,
    next_check_key: str,
) -> None:
    """Persist a reopen submission and clear form mode on success."""
    note_raw = st.session_state.get(note_key, "")
    note_value = str(note_raw).strip() or None
    next_check_value = st.session_state.get(next_check_key)
    if not isinstance(next_check_value, date):
        _set_flash_error("Select a valid next check-in date.")
        return
    try:
        with time_action("now_reopen"):
            reopen_handoff(
                handoff_id,
                note=note_value,
                next_check_date=next_check_value,
            )
    except ValueError as exc:
        _set_flash_error(str(exc))
        return
    _set_flash_success(
        f"Checked in today; next check set to {format_date_smart(next_check_value)}."
    )
    st.session_state.pop(mode_key, None)


def _save_edit_submission(
    *,
    handoff_id: int,
    project_by_name: dict[str, Project],
    project_key: str,
    who_key: str,
    need_key: str,
    next_check_key: str,
    deadline_key: str,
    context_key: str,
) -> None:
    """Persist a handoff edit form submission."""
    need_back_raw = st.session_state.get(need_key, "")
    need_back = str(need_back_raw).strip()
    if not need_back:
        _set_flash_error("Need back is required.")
        return

    project_name = st.session_state.get(project_key)
    if project_name not in project_by_name:
        _set_flash_error("Select a project.")
        return
    project_id = project_by_name[project_name].id
    if project_id is None:
        _set_flash_error("Select a valid project.")
        return

    next_check_value = st.session_state.get(next_check_key)
    if not isinstance(next_check_value, date):
        _set_flash_error("Select a valid next check date.")
        return

    deadline_value = st.session_state.get(deadline_key)
    context_raw = st.session_state.get(context_key, "")
    who_raw = st.session_state.get(who_key, "")
    with time_action("now_edit"):
        update_handoff(
            handoff_id,
            project_id=project_id,
            need_back=need_back,
            pitchman=str(who_raw).strip() or None,
            next_check=next_check_value,
            deadline=deadline_value if isinstance(deadline_value, date) else None,
            notes=str(context_raw).strip() or None,
        )
    st.session_state.pop("now_editing_handoff_id", None)
    _set_flash_success("Saved.")


def _save_add_submission(
    *,
    project_by_name: dict[str, Project],
    project_key: str,
    who_key: str,
    need_key: str,
    next_check_key: str,
    deadline_key: str,
    context_key: str,
) -> None:
    """Persist a new handoff submission from the add form."""
    need_back_raw = st.session_state.get(need_key, "")
    need_back = str(need_back_raw).strip()
    if not need_back:
        _set_flash_error("Need back is required.")
        return

    project_name = st.session_state.get(project_key)
    if project_name not in project_by_name:
        _set_flash_error("Select a project.")
        return
    project_id = project_by_name[project_name].id
    if project_id is None:
        _set_flash_error("Select a valid project.")
        return

    next_check_value = st.session_state.get(next_check_key)
    if not isinstance(next_check_value, date):
        _set_flash_error("Select a valid next check date.")
        return

    deadline_value = st.session_state.get(deadline_key)
    who_raw = st.session_state.get(who_key, "")
    context_raw = st.session_state.get(context_key, "")
    with time_action("now_add"):
        create_handoff(
            project_id=project_id,
            need_back=need_back,
            next_check=next_check_value,
            deadline=deadline_value if isinstance(deadline_value, date) else None,
            pitchman=str(who_raw).strip() or None,
            notes=str(context_raw).strip() or None,
        )
    _collapse_add_form()
    _set_flash_success("Added.")


def _render_check_in_flow(handoff: Handoff, *, key_prefix: str, allow_actions: bool = True) -> None:
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
    row_col1, row_col2 = st.columns([3, 1])
    with row_col1:
        st.segmented_control(
            "Check-in",
            options=CHECK_IN_MODES,
            default=None,
            format_func=lambda s: CHECK_IN_MODE_LABELS.get(s, str(s)),
            key=mode_key,
            label_visibility="collapsed",
        )
    with row_col2:
        if allow_actions:
            st.button(
                "Edit",
                key=f"{key_prefix}_edit_btn_{handoff_id}",
                on_click=_set_editing_handoff,
                kwargs={"handoff_id": handoff_id},
            )
    selected_mode = st.session_state.get(mode_key)

    if selected_mode not in {"on_track", "delayed", "concluded"}:
        return

    form_key = f"{key_prefix}_check_in_form_{handoff_id}_{selected_mode}"
    note_key = f"{form_key}_note"
    next_check_key: str | None = None
    with st.form(key=form_key):
        if selected_mode == "concluded":
            st.text_area(
                "Conclusion (optional)",
                key=note_key,
            )
            st.form_submit_button(
                "Save conclude check-in",
                on_click=_save_check_in_submission,
                kwargs={
                    "handoff_id": handoff_id,
                    "selected_mode": selected_mode,
                    "mode_key": mode_key,
                    "note_key": note_key,
                },
            )
        else:
            note_label = (
                "Current progress (optional)" if selected_mode == "on_track" else "Why? (optional)"
            )
            st.text_area(note_label, key=note_key)
            default_next_check = (
                handoff.next_check
                if handoff.next_check is not None and handoff.next_check > today
                else add_business_days(today, 1)
            )
            next_check_key = f"{form_key}_next_check"
            st.date_input(
                "Next check-in",
                value=default_next_check,
                key=next_check_key,
            )
            st.form_submit_button(
                "Save check-in",
                on_click=_save_check_in_submission,
                kwargs={
                    "handoff_id": handoff_id,
                    "selected_mode": selected_mode,
                    "mode_key": mode_key,
                    "note_key": note_key,
                    "next_check_key": next_check_key,
                },
            )
        st.form_submit_button(
            "Cancel",
            on_click=_clear_session_key,
            kwargs={"state_key": mode_key},
        )


def _render_reopen_flow(handoff: Handoff, *, key_prefix: str) -> None:
    """Render append-only reopen controls for concluded handoffs."""
    handoff_id = handoff.id
    if handoff_id is None:
        return

    mode_key = f"{key_prefix}_reopen_mode_{handoff_id}"
    st.button(
        "Reopen",
        key=f"{key_prefix}_reopen_btn_{handoff_id}",
        on_click=_set_mode,
        kwargs={"mode_key": mode_key, "mode": "reopen"},
    )
    if st.session_state.get(mode_key) != "reopen":
        return

    today = date.today()
    default_next_check = add_business_days(today, 1)
    form_key = f"{key_prefix}_reopen_form_{handoff_id}"
    note_key = f"{form_key}_note"
    next_check_key = f"{form_key}_next_check"
    with st.form(key=form_key):
        st.text_area(
            "Reason (optional)",
            placeholder="reopen: waiting on revised doc",
            key=note_key,
        )
        st.date_input(
            "Next check-in",
            value=default_next_check,
            key=next_check_key,
        )
        st.form_submit_button(
            "Save reopen",
            on_click=_save_reopen_submission,
            kwargs={
                "handoff_id": handoff_id,
                "mode_key": mode_key,
                "note_key": note_key,
                "next_check_key": next_check_key,
            },
        )
        st.form_submit_button(
            "Cancel",
            on_click=_clear_session_key,
            kwargs={"state_key": mode_key},
        )


def _render_item(
    handoff: Handoff,
    key_prefix: str,
    *,
    project_by_name: dict[str, Project],
    is_risk: bool = False,
    show_check_in_controls: bool = False,
    allow_actions: bool = True,
    allow_reopen: bool = False,
    match_explanation: str | None = None,
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

    check_in_mode_key = f"{key_prefix}_check_in_mode_{handoff_id}"
    reopen_mode_key = f"{key_prefix}_reopen_mode_{handoff_id}"
    has_active_check_in_mode = st.session_state.get(check_in_mode_key) in {
        "on_track",
        "delayed",
        "concluded",
    }
    has_active_reopen_mode = st.session_state.get(reopen_mode_key) == "reopen"
    editing = allow_actions and st.session_state.get("now_editing_handoff_id") == handoff_id
    keep_expanded_for_mode = (
        allow_actions and show_check_in_controls and has_active_check_in_mode
    ) or (allow_reopen and has_active_reopen_mode)
    # Auto-expand for due action items so check-in controls are visible without clicking
    is_due_action = show_check_in_controls and _is_check_in_due(handoff)
    with st.expander(header, expanded=editing or keep_expanded_for_mode or is_due_action):
        if match_explanation:
            st.caption(match_explanation)
        if not editing and allow_actions and show_check_in_controls:
            _render_check_in_flow(handoff, key_prefix=key_prefix, allow_actions=allow_actions)
        elif not editing and allow_reopen:
            _render_reopen_flow(handoff, key_prefix=key_prefix)

        if editing:
            _render_edit_form(
                handoff=handoff,
                project_by_name=project_by_name,
                key_prefix=f"{key_prefix}_edit_{handoff_id}",
            )
            return

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
    project_key = f"{key_prefix}_project"
    who_key = f"{key_prefix}_who"
    need_key = f"{key_prefix}_need"
    next_key = f"{key_prefix}_next"
    deadline_key = f"{key_prefix}_deadline"
    context_key = f"{key_prefix}_context"
    with st.form(key=f"{key_prefix}_form"):
        proj_idx = (
            project_names.index(handoff.project.name)
            if handoff.project and handoff.project.name in project_names
            else 0
        )
        st.selectbox(
            "Project",
            options=project_names,
            index=proj_idx,
            key=project_key,
        )
        st.text_input(
            "Who",
            value=(handoff.pitchman or "").strip(),
            placeholder="Person you're waiting on",
            key=who_key,
        )
        st.text_input(
            "Need back",
            value=handoff.need_back or "",
            placeholder="Deliverable you need returned",
            key=need_key,
        )
        st.date_input(
            "Next check",
            value=handoff.next_check or date.today(),
            key=next_key,
        )
        st.date_input(
            "Deadline (optional)",
            value=handoff.deadline,
            key=deadline_key,
        )
        st.text_area(
            "Context (optional)",
            value=(handoff.notes or "").strip(),
            placeholder="Notes, links, markdown…",
            key=context_key,
        )
        col1, col2 = st.columns(2)
        with col1:
            st.form_submit_button(
                "Save",
                on_click=_save_edit_submission,
                kwargs={
                    "handoff_id": handoff_id,
                    "project_by_name": project_by_name,
                    "project_key": project_key,
                    "who_key": who_key,
                    "need_key": need_key,
                    "next_check_key": next_key,
                    "deadline_key": deadline_key,
                    "context_key": context_key,
                },
            )
        with col2:
            st.form_submit_button(
                "Cancel",
                on_click=_clear_session_key,
                kwargs={"state_key": "now_editing_handoff_id"},
            )


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
    with st.form(key=f"{key_prefix}_add_form", clear_on_submit=False):
        project_names = list(project_by_name)
        project_key = f"{key_prefix}_add_project"
        who_key = f"{key_prefix}_add_who"
        need_key = f"{key_prefix}_add_need"
        next_key = f"{key_prefix}_add_next"
        deadline_key = f"{key_prefix}_add_deadline"
        context_key = f"{key_prefix}_add_context"
        st.selectbox("Project *", options=project_names, key=project_key)
        st.text_input("Who", placeholder="Person you're waiting on", key=who_key)
        st.text_input(
            "Need back *",
            placeholder="Deliverable you need returned",
            key=need_key,
        )
        st.date_input(
            "Next check *",
            value=date.today(),
            key=next_key,
        )
        st.date_input(
            "Deadline (optional)",
            value=None,
            key=deadline_key,
        )
        st.text_area(
            "Context (optional)",
            placeholder="Notes, links, markdown…",
            key=context_key,
        )
        col_submit, col_close = st.columns(2)
        with col_submit:
            st.form_submit_button(
                "Add",
                on_click=_save_add_submission,
                kwargs={
                    "project_by_name": project_by_name,
                    "project_key": project_key,
                    "who_key": who_key,
                    "need_key": need_key,
                    "next_check_key": next_key,
                    "deadline_key": deadline_key,
                    "context_key": context_key,
                },
            )
        with col_close:
            st.form_submit_button(
                "Close",
                on_click=_collapse_add_form,
            )


def render_now_page() -> None:
    """Render the Now page with four sections: Risk | Action | Upcoming | Concluded."""
    st.subheader("Now")
    st.caption("Minimize risks by clearing actions on time.")
    flash_message = st.session_state.pop(_NOW_FLASH_SUCCESS_KEY, None)
    if flash_message:
        st.success(flash_message)
    flash_error = st.session_state.pop(_NOW_FLASH_ERROR_KEY, None)
    if flash_error:
        st.error(flash_error)

    toggle_widget = getattr(st, "toggle", None) or st.checkbox
    include_archived_projects = bool(
        toggle_widget(
            "Include archived projects",
            value=False,
            key="now_include_archived_projects",
        )
    )
    with time_action("now_render"):
        projects = list_projects(include_archived=include_archived_projects)
        if not projects:
            if include_archived_projects:
                st.info("No projects yet. Create one on the Projects page.")
            else:
                all_projects = list_projects(include_archived=True)
                if all_projects:
                    st.info(
                        "No active projects. Turn on 'Include archived projects' "
                        "to view archived work."
                    )
                else:
                    st.info("No projects yet. Create one on the Projects page.")
            return

        pitchmen = list_pitchmen_with_open_handoffs(
            include_archived_projects=include_archived_projects
        )
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

    add_expanded = st.session_state.get(_NOW_ADD_EXPANDED_KEY, False)
    if add_expanded:
        try:
            st.button(
                "➕ Add handoff",
                shortcut="a",
                key="now_add_handoff_collapse",
                on_click=_collapse_add_form,
                help="Collapse the add form",
            )
        except TypeError:
            st.button(
                "➕ Add handoff",
                key="now_add_handoff_collapse",
                on_click=_collapse_add_form,
                help="Collapse the add form",
            )
        _render_add_form(project_by_name, snapshot.pitchmen, "now")
    else:
        try:
            st.button(
                "➕ Add handoff",
                shortcut="a",
                key="now_add_handoff_trigger",
                on_click=_expand_add_form,
                help="Open the add form to create a new handoff",
            )
        except TypeError:
            # Fallback for in-app updater: old embedded Streamlit lacks shortcut param
            st.button(
                "➕ Add handoff",
                key="now_add_handoff_trigger",
                on_click=_expand_add_form,
                help="Open the add form to create a new handoff",
            )

    # --- Risk section ---
    st.markdown("---")
    st.markdown("**Risk**")
    if not snapshot.risk:
        st.info("No at-risk handoffs.")
    else:
        for handoff in snapshot.risk:
            _render_item(
                handoff,
                "now_risk",
                project_by_name=project_by_name,
                is_risk=True,
                show_check_in_controls=True,
                allow_actions=True,
                match_explanation=(
                    snapshot.section_explanations.get(handoff.id, "") or None
                    if handoff.id is not None
                    else None
                ),
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
                match_explanation=(
                    snapshot.section_explanations.get(handoff.id, "") or None
                    if handoff.id is not None
                    else None
                ),
            )

    # --- Custom sections ---
    for section_id, handoffs in snapshot.custom_sections:
        section_label = section_id.replace("_", " ").title()
        st.markdown("---")
        st.markdown(f"**{section_label}**")
        if not handoffs:
            st.info(f"No handoffs in {section_label}.")
        else:
            for handoff in handoffs:
                _render_item(
                    handoff,
                    f"now_custom_{section_id}",
                    project_by_name=project_by_name,
                    show_check_in_controls=True,
                    match_explanation=(
                        snapshot.section_explanations.get(handoff.id, "") or None
                        if handoff.id is not None
                        else None
                    ),
                )

    # --- Upcoming section ---
    st.markdown("---")
    st.markdown("**Upcoming**")
    if not snapshot.upcoming:
        st.info("No upcoming handoffs.")
    else:
        for handoff in snapshot.upcoming:
            _render_item(
                handoff,
                key_prefix="now_upcoming",
                project_by_name=project_by_name,
                show_check_in_controls=True,
                match_explanation=(
                    snapshot.section_explanations.get(handoff.id, "") or None
                    if handoff.id is not None
                    else None
                ),
            )

    # --- Concluded section ---
    st.markdown("---")
    st.markdown("**Concluded**")
    if not snapshot.concluded:
        st.info("No concluded handoffs.")
    else:
        for handoff in snapshot.concluded:
            _render_item(
                handoff,
                key_prefix="now_concluded",
                project_by_name=project_by_name,
                allow_actions=False,
                allow_reopen=True,
            )
