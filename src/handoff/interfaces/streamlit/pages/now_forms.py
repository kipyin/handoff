"""Form renderers and submission handlers for the Now page."""

from __future__ import annotations

from datetime import date

import streamlit as st

from handoff.core.models import CheckInType, Handoff, Project
from handoff.dates import add_business_days, format_date_smart
from handoff.instrumentation import time_action
from handoff.interfaces.streamlit.pages.now_helpers import (
    ACTION_MODE_LABELS,
    ACTION_MODES,
    CHECK_IN_MODE_LABELS,
    CHECK_IN_MODES,
    _clear_session_key,
    _collapse_add_form,
    _is_check_in_due,
    _project_option_label_for_id,
    _render_check_in_trail,
    _set_flash_error,
    _set_flash_success,
    _set_mode,
)
from handoff.services import (
    add_check_in,
    conclude_handoff,
    create_handoff,
    delete_handoff,
    reopen_handoff,
    update_handoff,
)


def _confirm_delete_handoff(*, handoff_id: int, action_mode_key: str) -> None:
    with time_action("now_delete"):
        if delete_handoff(handoff_id):
            _set_flash_success("Handoff deleted.")
            st.session_state.pop(action_mode_key, None)
        else:
            _set_flash_error("Could not delete handoff.")


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
    project_options: dict[str, Project],
    project_key: str,
    who_key: str,
    need_key: str,
    next_check_key: str,
    deadline_key: str,
    context_key: str,
    action_mode_key: str = "",
) -> None:
    """Persist a handoff edit form submission."""
    need_back_raw = st.session_state.get(need_key, "")
    need_back = str(need_back_raw).strip()
    if not need_back:
        _set_flash_error("Need back is required.")
        return

    project_label = st.session_state.get(project_key)
    if project_label not in project_options:
        _set_flash_error("Select a project.")
        return
    project_id = project_options[project_label].id
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
    if action_mode_key:
        st.session_state.pop(action_mode_key, None)
    _set_flash_success("Saved.")


def _save_add_submission(
    *,
    project_options: dict[str, Project],
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

    project_label = st.session_state.get(project_key)
    if project_label not in project_options:
        _set_flash_error("Select a project.")
        return
    project_id = project_options[project_label].id
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
    action_mode_key = f"{key_prefix}_action_mode_{handoff_id}"
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
            st.segmented_control(
                "Actions",
                options=ACTION_MODES,
                default=None,
                format_func=lambda s: ACTION_MODE_LABELS.get(s, str(s)),
                key=action_mode_key,
                label_visibility="collapsed",
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


def _render_delete_confirmation(handoff: Handoff, *, key_prefix: str) -> None:
    handoff_id = handoff.id
    if handoff_id is None:
        return
    action_mode_key = f"{key_prefix}_action_mode_{handoff_id}"
    need_back = (handoff.need_back or "this handoff").strip()
    st.warning("This action is irreversible.")
    st.caption(f"You are about to permanently delete: **{need_back}**")
    col1, col2 = st.columns(2)
    with col1:
        st.button(
            "Confirm delete",
            key=f"{key_prefix}_confirm_delete_{handoff_id}",
            type="primary",
            on_click=_confirm_delete_handoff,
            kwargs={"handoff_id": handoff_id, "action_mode_key": action_mode_key},
        )
    with col2:
        st.button(
            "Cancel",
            key=f"{key_prefix}_cancel_delete_{handoff_id}",
            on_click=_clear_session_key,
            kwargs={"state_key": action_mode_key},
        )


def _render_edit_form(
    handoff: Handoff,
    project_options: dict[str, Project],
    key_prefix: str,
    *,
    action_mode_key: str,
) -> None:
    """Render edit form for a handoff item."""
    handoff_id = handoff.id
    if handoff_id is None:
        return
    project_names = list(project_options)
    project_key = f"{key_prefix}_project"
    if project_key in st.session_state and st.session_state[project_key] not in project_names:
        st.session_state.pop(project_key, None)
    who_key = f"{key_prefix}_who"
    need_key = f"{key_prefix}_need"
    next_key = f"{key_prefix}_next"
    deadline_key = f"{key_prefix}_deadline"
    context_key = f"{key_prefix}_context"
    with st.form(key=f"{key_prefix}_form"):
        current_project_label = _project_option_label_for_id(
            project_options,
            handoff.project.id if handoff.project else None,
        )
        proj_idx = (
            project_names.index(current_project_label)
            if current_project_label in project_names
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
                    "project_options": project_options,
                    "project_key": project_key,
                    "who_key": who_key,
                    "need_key": need_key,
                    "next_check_key": next_key,
                    "deadline_key": deadline_key,
                    "context_key": context_key,
                    "action_mode_key": action_mode_key,
                },
            )
        with col2:
            st.form_submit_button(
                "Cancel",
                on_click=_clear_session_key,
                kwargs={"state_key": action_mode_key},
            )


def _render_add_form(
    project_options: dict[str, Project],
    pitchmen: list[str],
    key_prefix: str,
) -> None:
    """Render form to add a new handoff item."""
    with st.form(key=f"{key_prefix}_add_form", clear_on_submit=False):
        project_names = list(project_options)
        project_key = f"{key_prefix}_add_project"
        if project_key in st.session_state and st.session_state[project_key] not in project_names:
            st.session_state.pop(project_key, None)
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
                    "project_options": project_options,
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


def _render_item(
    handoff: Handoff,
    key_prefix: str,
    *,
    project_options: dict[str, Project],
    is_risk: bool = False,
    show_check_in_controls: bool = False,
    allow_actions: bool = True,
    allow_reopen: bool = False,
) -> None:
    """Render one handoff item in an expander."""
    from handoff.dates import format_risk_reason

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
    action_mode_key = f"{key_prefix}_action_mode_{handoff_id}"
    reopen_mode_key = f"{key_prefix}_reopen_mode_{handoff_id}"
    has_active_check_in_mode = st.session_state.get(check_in_mode_key) in {
        "on_track",
        "delayed",
        "concluded",
    }
    has_active_reopen_mode = st.session_state.get(reopen_mode_key) == "reopen"
    action_mode = st.session_state.get(action_mode_key)
    editing = allow_actions and action_mode == "edit"
    deleting = allow_actions and action_mode == "delete"
    keep_expanded_for_mode = (
        allow_actions
        and show_check_in_controls
        and (has_active_check_in_mode or action_mode in ("edit", "delete"))
    ) or (allow_reopen and has_active_reopen_mode)
    expanded = editing or deleting or keep_expanded_for_mode
    with st.expander(header, expanded=expanded):
        if editing:
            _render_edit_form(
                handoff=handoff,
                project_options=project_options,
                key_prefix=f"{key_prefix}_edit_{handoff_id}",
                action_mode_key=action_mode_key,
            )
            return
        if deleting:
            _render_delete_confirmation(handoff, key_prefix=key_prefix)
            return
        if allow_actions and show_check_in_controls:
            _render_check_in_flow(handoff, key_prefix=key_prefix, allow_actions=allow_actions)
        elif allow_reopen:
            _render_reopen_flow(handoff, key_prefix=key_prefix)

        if context:
            st.markdown("**Context:**")
            st.markdown(context)
        else:
            st.caption("No context.")
        _render_check_in_trail(handoff)
