"""Shared helpers for the Now page: session state, project options, check-in trail."""

from __future__ import annotations

from collections import Counter
from datetime import date

import streamlit as st

from handoff.core.models import CheckIn, Handoff, Project
from handoff.dates import format_date_smart

CHECK_IN_MODES = ["on_track", "delayed", "concluded"]
CHECK_IN_MODE_LABELS = {"on_track": "On-track", "delayed": "Delayed", "concluded": "Conclude"}
ACTION_MODES = ["edit", "delete"]
ACTION_MODE_LABELS = {"edit": "Edit", "delete": "Delete"}

_NOW_FLASH_SUCCESS_KEY = "now_flash_success"
_NOW_FLASH_ERROR_KEY = "now_flash_error"
_NOW_ADD_EXPANDED_KEY = "now_add_expanded"


def _set_flash_success(message: str) -> None:
    st.session_state[_NOW_FLASH_SUCCESS_KEY] = message


def _set_flash_error(message: str) -> None:
    st.session_state[_NOW_FLASH_ERROR_KEY] = message


def _set_mode(*, mode_key: str, mode: str) -> None:
    st.session_state[mode_key] = mode


def _clear_session_key(*, state_key: str) -> None:
    st.session_state.pop(state_key, None)


def _expand_add_form() -> None:
    st.session_state[_NOW_ADD_EXPANDED_KEY] = True


def _collapse_add_form() -> None:
    st.session_state.pop(_NOW_ADD_EXPANDED_KEY, None)


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


def _build_project_options(projects: list[Project]) -> dict[str, Project]:
    """Build unique labels for project widgets keyed to the original project."""
    name_counts = Counter(project.name for project in projects)
    seen_name_counts: dict[str, int] = {}
    options: dict[str, Project] = {}

    for project in projects:
        occurrence = seen_name_counts.get(project.name, 0) + 1
        seen_name_counts[project.name] = occurrence

        if name_counts[project.name] > 1:
            suffix = f"#{project.id}" if project.id is not None else f"duplicate {occurrence}"
            label = f"{project.name} ({suffix})"
        else:
            label = project.name
        while label in options:
            label = (
                f"{label} #{project.id}" if project.id is not None else f"{label} ({occurrence})"
            )
        options[label] = project
    return options


def _project_option_label_for_id(
    project_options: dict[str, Project], project_id: int | None
) -> str | None:
    """Return the widget label that maps back to the given project id."""
    if project_id is None:
        return None
    for label, project in project_options.items():
        if project.id == project_id:
            return label
    return None


def get_now_flash_keys() -> tuple[str, str, str]:
    """Return (success_key, error_key, add_expanded_key) for the Now page."""
    return _NOW_FLASH_SUCCESS_KEY, _NOW_FLASH_ERROR_KEY, _NOW_ADD_EXPANDED_KEY
