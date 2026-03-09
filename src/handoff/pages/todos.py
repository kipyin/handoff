"""Todos page: filterable editable table and deadline presets.

This module contains the main todos table UI, filters, save logic, and deadline
preset helpers. Previously in ui_components; consolidated here so the page owns
its UI and data flow.
"""

from __future__ import annotations

from collections.abc import Callable
from datetime import date, datetime, timedelta

import pandas as pd
import streamlit as st
from loguru import logger

from handoff.autosave import autosave_editor
from handoff.dates import week_bounds
from handoff.models import TodoStatus
from handoff.page_models import (
    TodoCreateInput,
    TodoMutationDefaults,
    TodoQuery,
    TodoRow,
    TodoUpdateInput,
)
from handoff.services.project_service import list_projects
from handoff.services.todo_service import (
    create_todo,
    delete_todo,
    list_helpers,
    query_todos,
    update_todo,
)

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


def _build_todo_dataframe(rows: list[TodoRow]) -> pd.DataFrame:
    """Convert typed todo rows to an editable dataframe."""
    if rows:
        return pd.DataFrame(
            [
                {
                    "id": row.todo_id,
                    "project": row.project_name,
                    "name": row.name,
                    "status": row.status.value,
                    "next_check": row.next_check,
                    "helper": row.helper,
                    "deadline": row.deadline,
                    "notes": row.notes,
                    "created_at": row.created_at,
                }
                for row in rows
            ]
        )

    return pd.DataFrame(
        columns=pd.Index(
            [
                "id",
                "project",
                "name",
                "status",
                "next_check",
                "helper",
                "deadline",
                "notes",
                "created_at",
            ]
        )
    )


def _apply_native_filters(
    *,
    key_prefix: str,
    project_by_name: dict[str, object],
    helper_options: list[str],
) -> tuple[TodoQuery, dict]:
    """Read Streamlit filters and return a typed todo query plus filter state."""
    cols = st.columns([2.2, 1.5, 1.5, 1.5, 1.1])
    with cols[0]:
        search_text = st.text_input(
            "Search",
            placeholder="name, notes, helper, project",
            key=f"{key_prefix}_search",
        ).strip()
    with cols[1]:
        status_filters = st.multiselect(
            "Statuses",
            options=[status.value for status in TodoStatus],
            default=[TodoStatus.HANDOFF.value],
            key=f"{key_prefix}_statuses",
        )
    with cols[2]:
        project_filters = st.multiselect(
            "Projects",
            options=list(project_by_name),
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
        "search_text": search_text,
        "start_date": start_date,
        "end_date": end_date,
    }
    todo_query = TodoQuery(
        search_text=search_text,
        statuses=tuple(TodoStatus(value) for value in status_filters),
        project_ids=tuple(
            project_by_name[name].id for name in project_filters if name in project_by_name
        ),
        helper_names=tuple(helper_filters),
        deadline_start=start_date,
        deadline_end=end_date,
    )
    return todo_query, filter_state


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
) -> TodoMutationDefaults:
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
    default_status = (
        TodoStatus(status_filters[0]) if len(status_filters) == 1 else TodoStatus.HANDOFF
    )
    default_helper = helper_filters[0] if len(helper_filters) == 1 else ""
    return TodoMutationDefaults(
        project_id=default_project_id,
        project_name=default_project_name,
        status=default_status,
        helper=default_helper,
    )


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
    display_df = working_df.drop(columns=["id", "created_at"], errors="ignore")
    display_df = display_df.reset_index(drop=True)
    return working_df, display_df


def _normalize_deadline(value: object) -> date | None:
    """Coerce an editor deadline value to a ``date``."""
    if value in (None, "", pd.NaT):
        return None
    if isinstance(value, datetime):
        return value.date()
    if isinstance(value, date):
        return value
    if isinstance(value, str):
        stripped = value.strip()
        return date.fromisoformat(stripped) if stripped else None
    return None


def _build_update_input(
    todo_id: int,
    row_changes: dict,
    current_row: dict,
    project_by_name: dict[str, int],
) -> TodoUpdateInput:
    """Translate one edited row into a typed update contract."""
    project_name = row_changes.get("project", current_row.get("project"))
    status_value = row_changes.get("status", current_row.get("status"))
    return TodoUpdateInput(
        todo_id=todo_id,
        project_id=project_by_name.get(project_name),
        name=row_changes.get("name", current_row.get("name")),
        status=TodoStatus(status_value) if status_value else None,
        next_check=_normalize_deadline(
            row_changes.get("next_check", current_row.get("next_check"))
        ),
        deadline=_normalize_deadline(row_changes.get("deadline", current_row.get("deadline"))),
        helper=row_changes.get("helper", current_row.get("helper")),
        notes=row_changes.get("notes", current_row.get("notes")),
    )


def _build_create_input(
    row: dict,
    *,
    project_by_name: dict[str, int],
    defaults: TodoMutationDefaults,
) -> TodoCreateInput | None:
    """Translate one inserted row into a typed create contract."""
    name = (row.get("name") or "").strip()
    if not name:
        return None

    project_name = row.get("project")
    project_id = project_by_name.get(project_name) if project_name else defaults.project_id
    if project_id is None:
        return None

    status_value = row.get("status") or defaults.status.value
    return TodoCreateInput(
        project_id=project_id,
        name=name,
        status=TodoStatus(status_value),
        next_check=_normalize_deadline(row.get("next_check")),
        deadline=_normalize_deadline(row.get("deadline")),
        helper=row.get("helper"),
        notes=row.get("notes"),
    )


def _persist_changes(
    state: dict,
    display_df: pd.DataFrame,
    projects: list,
    defaults: TodoMutationDefaults,
    key_prefix: str,
) -> None:
    """Apply edits, additions, and deletions from data_editor state to the database.

    Args:
        state: The 'edited_rows', 'added_rows', 'deleted_rows' dict from st.data_editor.
        display_df: The DataFrame that was passed to the editor (for ID lookup).
        projects: List of project models.
        defaults: Default values to use when adding a new row.
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
    for row_idx_key, changes in edited.items():
        try:
            row_idx = int(row_idx_key)
        except (TypeError, ValueError):
            logger.warning("Ignoring invalid edited row index: {}", row_idx_key)
            continue
        if not (0 <= row_idx < len(display_df)):
            continue

        todo_id = display_df.iloc[row_idx].get("__todo_id")
        if todo_id is None or pd.isna(todo_id):
            continue

        current_row = display_df.iloc[row_idx].to_dict()
        update_input = _build_update_input(int(todo_id), changes, current_row, project_by_name)

        update_todo(
            update_input.todo_id,
            project_id=update_input.project_id,
            name=update_input.name,
            status=update_input.status,
            next_check=update_input.next_check,
            deadline=update_input.deadline,
            helper=update_input.helper,
            notes=update_input.notes,
        )
        logger.info("Updated todo_id={}", todo_id)

    # 3. Handle Additions
    for row in added:
        create_input = _build_create_input(row, project_by_name=project_by_name, defaults=defaults)
        if create_input is None:
            continue

        created = create_todo(
            project_id=create_input.project_id,
            name=create_input.name,
            status=create_input.status,
            next_check=create_input.next_check,
            deadline=create_input.deadline,
            helper=create_input.helper,
            notes=create_input.notes,
        )
        # Remember last used project/helper for the next addition
        st.session_state[f"{key_prefix}_last_new_project_id"] = create_input.project_id
        st.session_state[f"{key_prefix}_last_new_helper"] = create_input.helper
        logger.info("Created todo_id={}", created.id)


def _make_todos_persist_fn(
    projects: list,
    defaults: TodoMutationDefaults,
    key_prefix: str,
) -> Callable[[dict, pd.DataFrame], bool]:
    """Build a persist callback for :func:`autosave_editor`.

    Returns a callable ``(state, prev_display_df) -> needs_rerun`` that
    delegates to :func:`_persist_changes` and requests a full rerun only
    when the editor's row count changes (additions or deletions).
    """

    def _persist(state: dict, display_df: pd.DataFrame) -> bool:
        _persist_changes(
            state=state,
            display_df=display_df,
            projects=projects,
            defaults=defaults,
            key_prefix=key_prefix,
        )
        return bool(state.get("added_rows") or state.get("deleted_rows"))

    return _persist


def _render_editable_table(
    *,
    projects: list,
    helper_options: list[str],
    key_prefix: str,
    context_label: str,
) -> None:
    """Render editable table with filters and autosave persistence."""
    project_names = [project.name for project in projects]
    project_by_name = {p.name: p for p in projects}

    todo_query, filter_state = _apply_native_filters(
        key_prefix=key_prefix,
        project_by_name=project_by_name,
        helper_options=helper_options,
    )
    rows = [TodoRow.from_todo(todo) for todo in query_todos(query=todo_query)]
    filtered_df = _build_todo_dataframe(rows)

    defaults = _compute_defaults_from_filters(filter_state, project_by_name, projects)

    remembered_project_id = st.session_state.get(f"{key_prefix}_last_new_project_id")
    if isinstance(remembered_project_id, int):
        for name, project in project_by_name.items():
            if project.id == remembered_project_id:
                defaults = TodoMutationDefaults(
                    project_id=project.id,
                    project_name=name,
                    status=defaults.status,
                    helper=defaults.helper,
                )
                break

    remembered_helper = st.session_state.get(f"{key_prefix}_last_new_helper")
    if isinstance(remembered_helper, str) and remembered_helper:
        defaults = TodoMutationDefaults(
            project_id=defaults.project_id,
            project_name=defaults.project_name,
            status=defaults.status,
            helper=remembered_helper,
        )

    working_df, display_df = _sort_and_build_display_df(filtered_df)

    editor_key = f"{key_prefix}_table_editor"

    # Keep the caption based on the full active todo list, even though filters are now
    # applied through TodoQuery instead of client-side dataframe filtering.
    total_count = len(query_todos(query=TodoQuery(include_archived=todo_query.include_archived)))
    filtered_count = len(filtered_df.index)
    st.caption(
        f"Showing {filtered_count} of {total_count} todo{'s' if total_count != 1 else ''}. "
        "Changes are saved automatically as you edit."
    )
    if total_count > 0 and filtered_count == 0:
        st.info("No todos match the current filters. Clear or adjust them to see results.")

    persist_fn = _make_todos_persist_fn(projects, defaults, key_prefix)

    autosave_editor(
        display_df,
        key=editor_key,
        persist_fn=persist_fn,
        num_rows="dynamic",
        height="content",
        hide_index=True,
        column_order=["project", "name", "status", "next_check", "helper", "deadline", "notes"],
        column_config={
            "__todo_id": None,
            "__created_at": None,
            "project": st.column_config.SelectboxColumn(
                "Project",
                options=project_names,
                default=defaults.project_name,
                required=True,
            ),
            "name": st.column_config.TextColumn("Name", required=True),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=[status.value for status in TodoStatus],
                default=defaults.status.value,
                required=True,
            ),
            "next_check": st.column_config.DateColumn("Next check"),
            "helper": st.column_config.TextColumn("Helper", default=defaults.helper),
            "deadline": st.column_config.DateColumn("Deadline"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )


def render_todos_page() -> None:
    """Render the main todos page with a unified editable table."""
    st.subheader("Todos")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one on the Projects page.")
        return

    helpers = list_helpers()
    _render_editable_table(
        projects=projects,
        helper_options=helpers,
        key_prefix="main",
        context_label="view=todos_page",
    )
