"""Todos page: filterable editable table and deadline presets.

This module contains the main todos table UI, filters, save logic, and deadline
preset helpers. Previously in ui_components; consolidated here so the page owns
its UI and data flow.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st
from loguru import logger

from handoff.data import (
    create_todo,
    delete_todo,
    list_helpers,
    list_projects,
    query_todos,
    update_todo,
)
from handoff.dates import week_bounds
from handoff.models import TodoStatus

# Deadline filter presets (used by table filters and tests).
DEADLINE_ANY = "Any"
DEADLINE_OVERDUE = "Overdue"
DEADLINE_TODAY = "Today"
DEADLINE_TOMORROW = "Tomorrow"
DEADLINE_THIS_WEEK = "This week"
DEADLINE_CUSTOM = "Custom range"

DEADLINE_PRESETS = [
    DEADLINE_ANY,
    DEADLINE_OVERDUE,
    DEADLINE_TODAY,
    DEADLINE_TOMORROW,
    DEADLINE_THIS_WEEK,
    DEADLINE_CUSTOM,
]


def _deadline_preset_bounds(preset: str) -> tuple[date | None, date | None]:
    """Return (start_date, end_date) for a deadline preset, or (None, None) for Any.

    Args:
        preset: One of DEADLINE_ANY, DEADLINE_OVERDUE, DEADLINE_TODAY, DEADLINE_TOMORROW,
            DEADLINE_THIS_WEEK, or DEADLINE_CUSTOM.

    Returns:
        Tuple of (start_date, end_date); (None, None) for Any or Custom.

    """
    today = date.today()
    if preset == DEADLINE_ANY:
        return None, None
    if preset == DEADLINE_OVERDUE:
        return date.min, today - timedelta(days=1)
    if preset == DEADLINE_TODAY:
        return today, today
    if preset == DEADLINE_TOMORROW:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    if preset == DEADLINE_THIS_WEEK:
        monday, sunday = week_bounds(today)
        return monday, sunday
    return None, None


def _build_todo_dataframe(todos: list) -> pd.DataFrame:
    """Convert todo records to an editable dataframe (always includes project column).

    Args:
        todos: List of todo records with project relationship loaded.

    Returns:
        DataFrame with columns id, project, name, status, helper, deadline, notes, created_at.

    """
    rows = []
    for todo in todos:
        status_value = todo.status.value
        deadline_date = todo.deadline if todo.deadline else None
        row = {
            "id": todo.id,
            "project": todo.project.name if todo.project else "",
            "name": todo.name,
            "status": status_value,
            "helper": (todo.helper or "").strip(),
            "deadline": deadline_date,
            "notes": todo.notes or "",
            "created_at": todo.created_at,
        }
        rows.append(row)
    if rows:
        return pd.DataFrame(rows)

    cols = [
        "id",
        "project",
        "name",
        "status",
        "helper",
        "deadline",
        "notes",
        "created_at",
    ]
    return pd.DataFrame(columns=pd.Index(cols))


def _apply_native_filters(
    source_df: pd.DataFrame,
    *,
    key_prefix: str,
    project_names: list[str],
    helper_options: list[str],
) -> tuple[pd.DataFrame, dict]:
    """Apply filters; return (filtered_df, filter_state).

    Args:
        source_df: Full todos DataFrame.
        key_prefix: Streamlit key prefix for filter widgets.
        project_names: List of project names for the project filter.
        helper_options: List of helper names for the helper filter (avoids repeated DB calls).

    Returns:
        Tuple of (filtered DataFrame, filter_state dict with project_filters, etc.).

    """
    cols = st.columns([2.2, 1.5, 1.5, 1.5, 1.1])
    with cols[0]:
        query = st.text_input(
            "Search",
            placeholder="name, notes, helper, project",
            key=f"{key_prefix}_search",
        ).strip()
    with cols[1]:
        status_filters = st.multiselect(
            "Statuses",
            options=[status.value for status in TodoStatus],
            default=[TodoStatus.DELEGATED.value],
            key=f"{key_prefix}_statuses",
        )
    with cols[2]:
        project_filters = st.multiselect(
            "Projects",
            options=project_names,
            key=f"{key_prefix}_projects",
        )
    with cols[3]:
        helper_filters = st.multiselect(
            "Helper",
            options=helper_options,
            key=f"{key_prefix}_helper",
        )
    with cols[4]:
        deadline_preset = st.selectbox(
            "Deadline",
            options=DEADLINE_PRESETS,
            key=f"{key_prefix}_deadline_preset",
        )
        start_date: date | None = None
        end_date: date | None = None
        if deadline_preset == DEADLINE_CUSTOM:
            range_value = st.date_input(
                "Range",
                value=(date.today(), date.today() + timedelta(days=7)),
                key=f"{key_prefix}_deadline_range",
            )
            if isinstance(range_value, (list, tuple)) and len(range_value) == 2:
                start_date, end_date = range_value[0], range_value[1]
                if start_date > end_date:
                    st.error("From must be before or equal to To.")
                    start_date = end_date = None
            else:
                start_date = end_date = None
        else:
            start_date, end_date = _deadline_preset_bounds(deadline_preset)

    filter_state = {
        "project_filters": project_filters,
        "status_filters": status_filters,
        "helper_filters": helper_filters,
    }
    filtered_df = _apply_dataframe_filters(
        source_df, query, status_filters, project_filters, helper_filters, start_date, end_date
    )
    return filtered_df, filter_state


def _apply_dataframe_filters(
    source_df: pd.DataFrame,
    query: str,
    status_filters: list[str],
    project_filters: list[str],
    helper_filters: list[str],
    start_date: date | None,
    end_date: date | None,
) -> pd.DataFrame:
    """Apply filter criteria to a todos DataFrame; returns filtered copy."""
    filtered_df = source_df.copy()
    if query:
        searchable_cols = ["name", "notes", "helper", "project"]
        search_df = filtered_df[searchable_cols].copy()
        search_df["helper"] = search_df["helper"].fillna("").astype(str)
        mask = (
            search_df.fillna("").agg(" ".join, axis=1).str.contains(query, case=False, regex=False)
        )
        filtered_df = filtered_df[mask]
    if status_filters:
        filtered_df = filtered_df[filtered_df["status"].isin(status_filters)]
    if project_filters:
        filtered_df = filtered_df[filtered_df["project"].isin(project_filters)]
    if helper_filters:
        helper_set = set(helper_filters)

        def _row_has_helper(helper_val: object) -> bool:
            if helper_val and str(helper_val).strip():
                return str(helper_val).strip() in helper_set
            return False

        filtered_df = filtered_df[filtered_df["helper"].apply(_row_has_helper)]
    if start_date is not None and end_date is not None:
        deadline_series = pd.to_datetime(filtered_df["deadline"], errors="coerce").dt.date
        mask = (
            deadline_series.notna()
            & (deadline_series >= start_date)
            & (deadline_series <= end_date)
        )
        filtered_df = filtered_df[mask]
    return filtered_df


def _compute_defaults_from_filters(
    filter_state: dict,
    project_by_name: dict,
    projects: list,
) -> tuple[int | None, str | None, str, str]:
    """Compute default project, status, and helper from filter state and project list.

    Returns:
        (default_project_id, default_project_name, default_status, default_helper).

    """
    project_filters = filter_state.get("project_filters", [])
    status_filters = filter_state.get("status_filters", [])
    helper_filters = filter_state.get("helper_filters", [])
    default_project_id: int | None = None
    default_project_name: str | None = None
    if len(project_filters) == 1 and project_filters[0] in project_by_name:
        default_project_name = project_filters[0]
        default_project_id = project_by_name[default_project_name].id
    if default_project_id is None and projects:
        default_project_id = projects[0].id
        default_project_name = projects[0].name
    default_status = status_filters[0] if len(status_filters) == 1 else TodoStatus.DELEGATED.value
    default_helper = helper_filters[0] if len(helper_filters) == 1 else ""
    return default_project_id, default_project_name, default_status, default_helper


def _sort_and_build_display_df(filtered_df: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Sort todos by created_at and build working_df and display_df.

    Returns:
        (working_df with __todo_id and __created_at, display_df without id/created_at).

    """
    if not filtered_df.empty and "created_at" in filtered_df.columns:
        filtered_df = filtered_df.sort_values(
            by="created_at",
            ascending=True,
            na_position="last",
        ).reset_index(drop=True)
    working_df = filtered_df.reset_index(drop=True).copy()
    working_df["__todo_id"] = working_df.get("id")
    working_df["__created_at"] = working_df.get("created_at")
    display_df = working_df.drop(columns=["id", "created_at"], errors="ignore").reset_index(
        drop=True
    )
    return working_df, display_df


def _persist_changes(
    state: dict,
    display_df: pd.DataFrame,
    projects: list,
    default_project_id: int | None,
    key_prefix: str,
) -> None:
    """Apply edits, additions, and deletions from data_editor state to the database.

    Args:
        state: The 'edited_rows', 'added_rows', 'deleted_rows' dict from st.data_editor.
        display_df: The DataFrame that was passed to the editor (for ID lookup).
        projects: List of project models.
        default_project_id: Project ID to use for new rows if not specified.
        key_prefix: Prefix for session state keys.

    """
    project_by_name = {p.name: p.id for p in projects}
    edited = state.get("edited_rows", {})
    added = state.get("added_rows", [])
    deleted = state.get("deleted_rows", [])

    # 1. Handle Deletions
    for row_idx in deleted:
        if 0 <= row_idx < len(display_df):
            todo_id = display_df.iloc[row_idx].get("__todo_id")
            if todo_id is not None and not pd.isna(todo_id):
                delete_todo(int(todo_id))
                logger.info("Deleted todo_id={}", todo_id)

    # 2. Handle Edits
    for row_idx, changes in edited.items():
        row_idx = int(row_idx)
        if not (0 <= row_idx < len(display_df)):
            continue

        todo_id = display_df.iloc[row_idx].get("__todo_id")
        if todo_id is None or pd.isna(todo_id):
            continue

        # Fetch current values from the display_df to merge with changes
        current_row = display_df.iloc[row_idx].to_dict()
        
        # Resolve project_id
        project_name = changes.get("project", current_row.get("project"))
        project_id = project_by_name.get(project_name)

        # Resolve status
        status_str = changes.get("status", current_row.get("status"))
        status_val = TodoStatus(status_str) if status_str else None

        # Resolve deadline (Directly use the value from changes or current_row)
        deadline_val = changes.get("deadline", current_row.get("deadline"))
        if isinstance(deadline_val, str) and deadline_val:
            deadline_val = date.fromisoformat(deadline_val)

        update_todo(
            int(todo_id),
            project_id=project_id,
            name=changes.get("name", current_row.get("name")),
            status=status_val,
            deadline=deadline_val,
            helper=changes.get("helper", current_row.get("helper")),
            notes=changes.get("notes", current_row.get("notes")),
        )
        logger.info("Updated todo_id={}", todo_id)

    # 3. Handle Additions
    for row in added:
        name = row.get("name", "").strip()
        if not name:
            continue

        project_name = row.get("project")
        project_id = project_by_name.get(project_name) if project_name else default_project_id
        if not project_id:
            continue

        status_str = row.get("status") or TodoStatus.DELEGATED.value
        
        # Resolve deadline
        deadline_val = row.get("deadline")
        if isinstance(deadline_val, str) and deadline_val:
            deadline_val = date.fromisoformat(deadline_val)
            
        helper = row.get("helper")

        created = create_todo(
            project_id=project_id,
            name=name,
            status=TodoStatus(status_str),
            deadline=deadline_val,
            helper=helper,
            notes=row.get("notes"),
        )
        # Remember last used project/helper for the next addition
        st.session_state[f"{key_prefix}_last_new_project_id"] = project_id
        st.session_state[f"{key_prefix}_last_new_helper"] = helper
        logger.info("Created todo_id={}", created.id)


def _render_editable_table(
    *,
    source_df: pd.DataFrame,
    projects: list,
    helper_options: list[str],
    key_prefix: str,
    context_label: str,
) -> None:
    """Render editable table with filters and native Streamlit delta persistence."""
    project_names = [project.name for project in projects]
    project_by_name = {p.name: p for p in projects}
    
    filtered_df, filter_state = _apply_native_filters(
        source_df,
        key_prefix=key_prefix,
        project_names=project_names,
        helper_options=helper_options,
    )
    
    default_project_id, default_project_name, default_status, default_helper = (
        _compute_defaults_from_filters(filter_state, project_by_name, projects)
    )

    # Apply remembered defaults from previous additions
    remembered_project_id = st.session_state.get(f"{key_prefix}_last_new_project_id")
    if isinstance(remembered_project_id, int):
        for name, project in project_by_name.items():
            if project.id == remembered_project_id:
                default_project_id = project.id
                default_project_name = name
                break
    
    remembered_helper = st.session_state.get(f"{key_prefix}_last_new_helper")
    if isinstance(remembered_helper, str) and remembered_helper:
        default_helper = remembered_helper

    working_df, display_df = _sort_and_build_display_df(filtered_df)

    editor_key = f"{key_prefix}_table_editor"
    
    st.caption("Changes are saved automatically as you edit.")
    
    st.data_editor(
        display_df,
        num_rows="dynamic",
        height="content",
        key=editor_key,
        hide_index=True,
        column_order=["project", "name", "status", "helper", "deadline", "notes"],
        column_config={
            "__todo_id": None,
            "__created_at": None,
            "project": st.column_config.SelectboxColumn(
                "Project",
                options=project_names,
                default=default_project_name,
                required=True,
            ),
            "name": st.column_config.TextColumn("Name", required=True),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=[status.value for status in TodoStatus],
                default=default_status,
                required=True,
            ),
            "helper": st.column_config.TextColumn("Helper", default=default_helper),
            "deadline": st.column_config.DateColumn("Deadline"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

    # Check for changes in the editor state
    state = st.session_state.get(editor_key)
    if state and (state.get("edited_rows") or state.get("added_rows") or state.get("deleted_rows")):
        _persist_changes(
            state=state,
            display_df=display_df,
            projects=projects,
            default_project_id=default_project_id,
            key_prefix=key_prefix,
        )
        st.rerun()


def render_todos_page() -> None:
    """Render the main todos page with a unified editable table."""
    st.subheader("Todos")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one on the Projects page.")
        return

    todos = query_todos()
    df = _build_todo_dataframe(todos)
    helpers = list_helpers()
    _render_editable_table(
        source_df=df,
        projects=projects,
        helper_options=helpers,
        key_prefix="main",
        context_label="view=todos_page",
    )
