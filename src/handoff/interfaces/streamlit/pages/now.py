"""Now page: control tower for handoffs.

Shows four sections: Risk | Action | Upcoming | Concluded.
Goal: minimize risks by clearing actions on time.
"""

from __future__ import annotations

import streamlit as st

from handoff.core.models import Project
from handoff.core.rulebook import BuiltInSection
from handoff.instrumentation import time_action
from handoff.interfaces.streamlit.pages.now_forms import _render_add_form, _render_item
from handoff.interfaces.streamlit.pages.now_helpers import (
    _build_project_options,
    _collapse_add_form,
    _expand_add_form,
    get_now_flash_keys,
)
from handoff.services import (
    get_now_snapshot,
    list_pitchmen_with_open_handoffs,
    list_projects,
)


def _render_filters(
    *,
    project_options: dict[str, Project],
    pitchmen: list[str],
    key_prefix: str,
) -> tuple[list[int] | None, list[str] | None, str | None]:
    """Render Project, Who, and search filters.

    Args:
        project_options: Map of unique project labels to Project for id lookup.
        pitchmen: List of pitchman names for the Who filter.
        key_prefix: Prefix for Streamlit widget keys.

    Returns:
        Tuple of (project_ids or None, pitchman_names or None, search_text or None).
    """
    project_names = list(project_options)
    projects_key = f"{key_prefix}_projects"
    stored = st.session_state.get(projects_key, [])
    if stored and not set(stored).issubset(set(project_names)):
        st.session_state[projects_key] = [p for p in stored if p in project_names]

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
            key=projects_key,
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
        if n in project_options:
            pid = project_options[n].id
            if pid is not None:
                project_ids.append(pid)
    return project_ids or None, pitchman_filters or None, search_text or None


def render_now_page() -> None:
    """Render the Now page with four sections: Risk | Action | Upcoming | Concluded."""
    st.subheader("Now")
    st.caption("Minimize risks by clearing actions on time.")

    success_key, error_key, add_key = get_now_flash_keys()
    flash_message = st.session_state.pop(success_key, None)
    if flash_message:
        st.success(flash_message)
    flash_error = st.session_state.pop(error_key, None)
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
        project_options = _build_project_options(projects)
        project_ids, pitchman_names, search_text = _render_filters(
            project_options=project_options,
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

    add_expanded = st.session_state.get(add_key, False)
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
        _render_add_form(project_options, snapshot.pitchmen, "now")
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
            st.button(
                "➕ Add handoff",
                key="now_add_handoff_trigger",
                on_click=_expand_add_form,
                help="Open the add form to create a new handoff",
            )

    st.markdown("---")
    st.markdown("**Risk**")
    risk_explanation = snapshot.section_explanations.get(BuiltInSection.RISK.value)
    if risk_explanation:
        st.caption(risk_explanation)
    if not snapshot.risk:
        st.info("No at-risk handoffs.")
    else:
        for handoff in snapshot.risk:
            _render_item(
                handoff,
                "now_risk",
                project_options=project_options,
                is_risk=True,
                show_check_in_controls=True,
                allow_actions=True,
            )

    st.markdown("---")
    st.markdown("**Action required**")
    action_explanation = snapshot.section_explanations.get(BuiltInSection.ACTION_REQUIRED.value)
    if action_explanation:
        st.caption(action_explanation)
    if not snapshot.action:
        st.info("Nothing needs attention right now. Add handoffs or check back later.")
    else:
        for handoff in snapshot.action:
            _render_item(
                handoff,
                "now_action",
                project_options=project_options,
                show_check_in_controls=True,
            )

    for section_id, handoffs in snapshot.custom_sections:
        section_label = section_id.replace("_", " ").title()
        st.markdown("---")
        st.markdown(f"**{section_label}**")
        custom_explanation = snapshot.section_explanations.get(section_id)
        if custom_explanation:
            st.caption(custom_explanation)
        if not handoffs:
            st.info(f"No handoffs in {section_label}.")
        else:
            for handoff in handoffs:
                _render_item(
                    handoff,
                    f"now_custom_{section_id}",
                    project_options=project_options,
                    show_check_in_controls=True,
                )

    st.markdown("---")
    st.markdown("**Upcoming**")
    upcoming_explanation = snapshot.section_explanations.get(snapshot.upcoming_section_id)
    if upcoming_explanation:
        st.caption(upcoming_explanation)
    if not snapshot.upcoming:
        st.info("No upcoming handoffs.")
    else:
        for handoff in snapshot.upcoming:
            _render_item(
                handoff,
                key_prefix="now_upcoming",
                project_options=project_options,
                show_check_in_controls=True,
            )

    st.markdown("---")
    st.markdown("**Concluded**")
    if not snapshot.concluded:
        st.info("No concluded handoffs.")
    else:
        for handoff in snapshot.concluded:
            _render_item(
                handoff,
                key_prefix="now_concluded",
                project_options=project_options,
                allow_actions=False,
                allow_reopen=True,
            )
