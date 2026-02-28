"""Streamlit UI components for the Handoff app.

This module wires together the Streamlit layout and the data layer:

- ``view()`` renders a unified, filterable todos table and saves edits back
  through helpers in :mod:`handoff.data`.
- ``sidebar()`` hosts project creation, rename/delete, and backup download
  actions in the Streamlit sidebar.

Most pages should import from this module instead of reaching into lower-level
helpers directly.
"""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st
from loguru import logger

from handoff.data import (
    create_project,
    create_todo,
    delete_project,
    delete_todo,
    list_helpers,
    list_projects,
    normalize_helper_name,
    query_todos,
    rename_project,
    update_todo,
)
from handoff.db import init_db
from handoff.models import TodoStatus


def _init_session_state() -> None:
    """Initialize Streamlit session defaults."""
    defaults: dict[str, object] = {}
    for key, value in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = value


def _coerce_deadline(raw_value: object) -> tuple[datetime | None, str | None]:
    """Coerce supported UI values into a deadline datetime."""
    if raw_value is None or raw_value == "":
        return None, None
    if isinstance(raw_value, datetime):
        # Treat all deadlines as naive local datetimes.
        return raw_value.astimezone().replace(tzinfo=None), None
    if isinstance(raw_value, date):
        # Store date-only deadlines at the end of the day (18:00 local time).
        return datetime.combine(raw_value, time(hour=18, minute=0)), None
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return None, None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return parsed.astimezone().replace(tzinfo=None), None
        except ValueError:
            return None, f"invalid deadline '{candidate}'"
    return None, "unsupported deadline format"


def get_urgency_bucket(deadline: date | None, status: str) -> str:
    """Return a simple urgency bucket for a todo.

    Args:
        deadline: Date portion of the todo deadline, or None.
        status: String status value (for example, ``delegated``, ``done``).

    Returns:
        One of ``overdue``, ``today``, ``soon``, or ``none``.
    """
    if status != TodoStatus.DELEGATED.value:
        return "none"
    if deadline is None:
        return "none"

    today = date.today()
    if deadline < today:
        return "overdue"
    if deadline == today:
        return "today"

    # Treat the rest of the current ISO week after today as "soon".
    weekday = today.weekday()
    monday = today - timedelta(days=weekday)
    sunday = monday + timedelta(days=6)
    if today < deadline <= sunday:
        return "soon"
    return "none"


def _format_deadline_display(d: date | None) -> str:
    """Format a date as 'Tue, Mar 4th' (moment-style ddd, MMM Do)."""
    if d is None:
        return ""
    day = d.day
    if 10 <= day % 100 <= 20:
        suffix = "th"
    else:
        suffix = {1: "st", 2: "nd", 3: "rd"}.get(day % 10, "th")
    return f"{d.strftime('%a, %b ')}{day}{suffix}"


def _build_todo_dataframe(todos: list, *, include_project: bool) -> pd.DataFrame:
    """Convert todo records to an editable dataframe."""
    rows = []
    for todo in todos:
        status_value = todo.status.value
        deadline_date = todo.deadline.date() if todo.deadline else None
        row = {
            "id": todo.id,
            "name": todo.name,
            "status": status_value,
            "helper": todo.helper or "",
            "deadline": deadline_date,
            "deadline_display": _format_deadline_display(deadline_date),
            "notes": todo.notes or "",
            "created_at": todo.created_at,
            "urgency": get_urgency_bucket(deadline_date, status_value),
        }
        if include_project:
            row["project"] = todo.project.name if todo.project else ""
        rows.append(row)
    if rows:
        return pd.DataFrame(rows)

    cols = [
        "id",
        "name",
        "status",
        "helper",
        "deadline",
        "deadline_display",
        "urgency",
        "notes",
        "created_at",
    ]
    if include_project:
        cols = [
            "id",
            "project",
            "name",
            "status",
            "helper",
            "deadline",
            "deadline_display",
            "urgency",
            "notes",
            "created_at",
        ]
    return pd.DataFrame(columns=pd.Index(cols))


DEADLINE_ANY = "Any"
DEADLINE_TODAY = "Today"
DEADLINE_TOMORROW = "Tomorrow"
DEADLINE_THIS_WEEK = "This week"
DEADLINE_CUSTOM = "Custom range"

DEADLINE_PRESETS = [
    DEADLINE_ANY,
    DEADLINE_TODAY,
    DEADLINE_TOMORROW,
    DEADLINE_THIS_WEEK,
    DEADLINE_CUSTOM,
]


def _deadline_preset_bounds(preset: str) -> tuple[date | None, date | None]:
    """Return (start_date, end_date) for a deadline preset, or (None, None) for Any."""
    today = date.today()
    if preset == DEADLINE_ANY:
        return None, None
    if preset == DEADLINE_TODAY:
        return today, today
    if preset == DEADLINE_TOMORROW:
        tomorrow = today + timedelta(days=1)
        return tomorrow, tomorrow
    if preset == DEADLINE_THIS_WEEK:
        # ISO week: Monday = 0
        weekday = today.weekday()
        monday = today - timedelta(days=weekday)
        sunday = monday + timedelta(days=6)
        return monday, sunday
    return None, None


def _apply_native_filters(
    source_df: pd.DataFrame,
    *,
    key_prefix: str,
    project_names: list[str],
) -> tuple[pd.DataFrame, dict]:
    """Apply compact native Streamlit filters; return (filtered_df, filter_state)."""
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
            options=list_helpers(),
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

    filtered_df = source_df.copy()
    if query:
        searchable_cols = ["name", "notes", "helper", "project"]
        mask = (
            filtered_df[searchable_cols]
            .fillna("")
            .agg(" ".join, axis=1)
            .str.contains(query, case=False, regex=False)
        )
        filtered_df = filtered_df[mask]
    if status_filters:
        filtered_df = filtered_df[filtered_df["status"].isin(status_filters)]
    if project_filters:
        filtered_df = filtered_df[filtered_df["project"].isin(project_filters)]
    if helper_filters:
        filtered_df = filtered_df[filtered_df["helper"].fillna("").isin(helper_filters)]
    if start_date is not None and end_date is not None:
        deadline_series = pd.to_datetime(filtered_df["deadline"], errors="coerce").dt.date
        mask = (
            deadline_series.notna()
            & (deadline_series >= start_date)
            & (deadline_series <= end_date)
        )
        filtered_df = filtered_df[mask]

    return filtered_df, filter_state


def _save_rows(
    edited_df: pd.DataFrame,
    *,
    projects: list,
    default_project_id: int | None,
    context_label: str,
) -> dict[str, object]:
    """Validate and persist edited rows, returning operation summary."""
    project_by_name = {project.name: project.id for project in projects}

    summary: dict[str, object] = {
        "created": 0,
        "updated": 0,
        "deleted": 0,
        "skipped": 0,
        "errors": [],
        "created_ids": [],
        "updated_ids": [],
        "last_created_project_id": None,
        "last_created_helper": None,
    }

    for row_no, row in enumerate(edited_df.to_dict("records"), start=1):
        todo_id_raw = row.get("__todo_id")
        is_existing = todo_id_raw is not None and not pd.isna(todo_id_raw)
        todo_id = int(todo_id_raw) if is_existing else None

        name_val = (row.get("name") or "").strip()
        if not name_val:
            summary["skipped"] += 1
            summary["errors"].append(f"Row {row_no}: name is required.")
            continue

        if "project" in row:
            project_name = (row.get("project") or "").strip()
            project_id = project_by_name.get(project_name) if project_name else None
        else:
            project_id = default_project_id

        if project_id is None:
            summary["skipped"] += 1
            summary["errors"].append(f"Row {row_no}: valid project is required.")
            continue

        raw_status = (row.get("status") or "").strip() or TodoStatus.DELEGATED.value
        try:
            status_val = TodoStatus(raw_status)
        except ValueError:
            summary["skipped"] += 1
            summary["errors"].append(f"Row {row_no}: invalid status '{raw_status}'.")
            continue

        deadline_val, deadline_error = _coerce_deadline(row.get("deadline"))
        if deadline_error:
            summary["skipped"] += 1
            summary["errors"].append(f"Row {row_no}: {deadline_error}.")
            continue

        helper_val = normalize_helper_name(row.get("helper"))
        notes_val = (row.get("notes") or "").strip() or None

        if is_existing:
            updated = update_todo(
                todo_id,
                project_id=project_id,
                name=name_val,
                status=status_val,
                deadline=deadline_val,
                helper=helper_val,
                notes=notes_val,
            )
            if updated is None:
                summary["skipped"] += 1
                summary["errors"].append(f"Row {row_no}: todo id {todo_id} not found for update.")
            else:
                summary["updated"] += 1
                summary["updated_ids"].append(todo_id)
                logger.info(
                    "Save action update context={context} row={row_no} "
                    "todo_id={todo_id} name={name!r}",
                    context=context_label,
                    row_no=row_no,
                    todo_id=todo_id,
                    name=name_val,
                )
        else:
            created = create_todo(
                project_id=project_id,
                name=name_val,
                status=status_val,
                deadline=deadline_val,
                helper=helper_val,
                notes=notes_val,
            )
            summary["created"] += 1
            summary["created_ids"].append(created.id)
            summary["last_created_project_id"] = project_id
            summary["last_created_helper"] = helper_val
            logger.info(
                "Save action create context={context} row={row_no} todo_id={todo_id} name={name!r}",
                context=context_label,
                row_no=row_no,
                todo_id=created.id,
                name=name_val,
            )

    return summary


def _render_editable_table(
    *,
    source_df: pd.DataFrame,
    projects: list,
    key_prefix: str,
    context_label: str,
) -> None:
    """Render native editable table and persist on save."""
    project_names = [project.name for project in projects]
    project_by_name = {p.name: p for p in projects}
    filtered_df, filter_state = _apply_native_filters(
        source_df,
        key_prefix=key_prefix,
        project_names=project_names,
    )
    if filtered_df.empty:
        st.info("No rows match filters. You can still add rows and save.")
        filtered_df = source_df.head(0).copy()

    # Defaults for new rows from active filters (single selection)
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

    # Remembered defaults for new rows (per view)
    remember_project_key = f"{key_prefix}_last_new_project_id"
    remember_helper_key = f"{key_prefix}_last_new_helper"
    remembered_project_id = st.session_state.get(remember_project_key)
    if isinstance(remembered_project_id, int):
        for name, project in project_by_name.items():
            if project.id == remembered_project_id:
                default_project_id = project.id
                default_project_name = name
                break
    remembered_helper = st.session_state.get(remember_helper_key)
    if isinstance(remembered_helper, str) and remembered_helper:
        default_helper = remembered_helper

    # Sort state and apply sort
    sort_col_key = f"{key_prefix}_sort_column"
    sort_asc_key = f"{key_prefix}_sort_asc"
    if sort_col_key not in st.session_state:
        st.session_state[sort_col_key] = "deadline"
    if sort_asc_key not in st.session_state:
        st.session_state[sort_asc_key] = True
    sortable_cols = [
        c for c in ["project", "name", "status", "helper", "deadline"] if c in filtered_df.columns
    ]
    sort_col = st.session_state[sort_col_key]
    if sort_col not in sortable_cols:
        sort_col = sortable_cols[0] if sortable_cols else "name"
    sort_asc = st.session_state[sort_asc_key]
    if not filtered_df.empty and sort_col in filtered_df.columns:
        filtered_df = filtered_df.sort_values(
            by=sort_col,
            ascending=sort_asc,
            na_position="last",
        ).reset_index(drop=True)

    working_df = filtered_df.reset_index(drop=True).copy()
    working_df["__todo_id"] = working_df.get("id")
    working_df["__created_at"] = working_df.get("created_at")
    display_df = working_df.drop(columns=["id", "created_at"], errors="ignore").reset_index(
        drop=True
    )

    # Sort controls
    with st.container():
        sc1, sc2, _ = st.columns([1, 1, 4])
        with sc1:
            new_sort_col = st.selectbox(
                "Sort by",
                options=sortable_cols,
                index=sortable_cols.index(sort_col) if sort_col in sortable_cols else 0,
                key=f"{key_prefix}_sort_select",
            )
        with sc2:
            new_sort_asc = st.selectbox(
                "Order",
                options=["Ascending", "Descending"],
                index=0 if sort_asc else 1,
                key=f"{key_prefix}_order_select",
            )
        if new_sort_col != sort_col or new_sort_asc != ("Ascending" if sort_asc else "Descending"):
            st.session_state[sort_col_key] = new_sort_col
            st.session_state[sort_asc_key] = new_sort_asc == "Ascending"
            st.rerun()

    column_order = [
        "project",
        "name",
        "status",
        "helper",
        "deadline_display",
        "deadline",
        "urgency",
        "notes",
    ]
    st.caption("Filter using the controls above. Use row deletion in the table to remove todos.")
    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        key=f"{key_prefix}_table",
        hide_index=True,
        column_order=column_order,
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
            "helper": st.column_config.TextColumn(
                "Helper",
                default=default_helper or None,
            ),
            "deadline_display": st.column_config.TextColumn("Deadline", disabled=True),
            "deadline": st.column_config.DateColumn("Date"),
            "urgency": st.column_config.TextColumn("Urgency", disabled=True),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

    # Autosave: compare current table state to the last persisted snapshot and
    # persist changes automatically when they differ.
    snapshot_key = f"{key_prefix}_last_saved_snapshot"
    status_key = f"{key_prefix}_saving_status"
    error_key = f"{key_prefix}_saving_error"
    current_snapshot = edited_df.to_json(date_format="iso", orient="records")
    last_snapshot = st.session_state.get(snapshot_key)

    if last_snapshot is None:
        # First render: treat the current DB state as the baseline without
        # writing anything back, so we don't show a spurious unsaved warning.
        st.session_state[snapshot_key] = current_snapshot
        st.session_state[status_key] = "saved"
        st.session_state[error_key] = ""
    elif current_snapshot != last_snapshot:
        st.session_state[status_key] = "saving"
        st.session_state[error_key] = ""
        logger.info(
            "Autosave starting for {context} with rows={rows}",
            context=context_label,
            rows=len(edited_df),
        )
        deleted = 0
        skipped_for_delete = 0
        deleted_ids: list[int] = []
        delete_errors: list[str] = []

        editor_state_key = f"{key_prefix}_table"
        editor_state = st.session_state.get(editor_state_key)
        deleted_rows_indices: list[int] = []
        if hasattr(editor_state, "get"):
            deleted_rows_indices = editor_state.get("deleted_rows") or []

        if deleted_rows_indices:
            normalized_indices: list[int] = []
            for raw_idx in deleted_rows_indices:
                try:
                    normalized_indices.append(int(raw_idx))
                except (TypeError, ValueError):
                    continue

            seen_ids: set[int] = set()
            for row_idx in normalized_indices:
                if not 0 <= row_idx < len(display_df):
                    continue
                raw_id = display_df.iloc[row_idx].get("__todo_id")
                if raw_id is None or pd.isna(raw_id):
                    # Deleted row was never persisted; nothing to do.
                    continue
                todo_id = int(raw_id)
                if todo_id in seen_ids:
                    continue
                seen_ids.add(todo_id)
                delete_ok = delete_todo(todo_id)
                if delete_ok:
                    deleted += 1
                    deleted_ids.append(todo_id)
                else:
                    skipped_for_delete += 1
                    delete_errors.append(
                        f"Row {row_idx + 1}: todo id {todo_id} not found for delete."
                    )

        try:
            summary = _save_rows(
                edited_df,
                projects=projects,
                default_project_id=default_project_id,
                context_label=context_label,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception("Autosave failed for {context}: {}", context_label, exc)
            st.session_state[status_key] = "error"
            st.session_state[error_key] = "Autosave failed. See logs for details."
        else:
            summary["deleted"] = summary.get("deleted", 0) + deleted
            summary["skipped"] = summary.get("skipped", 0) + skipped_for_delete
            if delete_errors:
                summary.setdefault("errors", []).extend(delete_errors)

            created_ids = summary.get("created_ids", [])
            updated_ids = summary.get("updated_ids", [])
            logger.info(
                "Autosave result context={context}: created={created} ids={created_ids}, "
                "updated={updated} ids={updated_ids}, deleted={deleted} ids={deleted_ids}, "
                "skipped={skipped}",
                context=context_label,
                created=summary["created"],
                created_ids=created_ids,
                updated=summary["updated"],
                updated_ids=updated_ids,
                deleted=summary["deleted"],
                deleted_ids=deleted_ids,
                skipped=summary["skipped"],
            )
            # Update remembered defaults for new rows based on the last created todo.
            last_created_project_id = summary.get("last_created_project_id")
            last_created_helper = summary.get("last_created_helper")
            if last_created_project_id is not None:
                st.session_state[remember_project_key] = last_created_project_id
            if last_created_helper:
                st.session_state[remember_helper_key] = last_created_helper

            # Record the new snapshot so subsequent renders know there are no
            # outstanding edits, then rerun so the table reflects DB state.
            st.session_state[snapshot_key] = current_snapshot
            st.session_state[status_key] = "saved"
            st.rerun()

    # Saving status message for the bottom of the table.
    status_value = st.session_state.get(status_key, "saved")
    error_message = st.session_state.get(error_key, "")
    if status_value == "saving":
        st.caption("Saving changes\u2026")
    elif status_value == "error":
        st.error(error_message or "Last save failed. See logs for details.")
    else:
        st.caption("All changes saved.")


def view() -> None:
    """View and edit todos in a single table."""
    st.subheader("Todos")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one in the sidebar.")
        return

    todos = query_todos()
    df = _build_todo_dataframe(todos, include_project=True)
    _render_editable_table(
        source_df=df,
        projects=projects,
        key_prefix="main",
        context_label="view=main",
    )


def _render_sidebar_project_management(projects: list) -> None:
    """Render project rename/delete controls."""
    st.sidebar.subheader("Manage projects")
    if not projects:
        st.sidebar.caption("No projects to manage yet.")
        return

    project_by_id = {project.id: project for project in projects}
    selected_project_id = st.sidebar.selectbox(
        "Project",
        options=[project.id for project in projects],
        format_func=lambda pid: project_by_id[pid].name,
        key="manage_project_id",
    )
    rename_value = st.sidebar.text_input("New name", key="rename_project_name")
    if st.sidebar.button("Rename project", key="rename_project_button"):
        if not rename_value.strip():
            st.sidebar.error("Project name cannot be empty.")
        else:
            rename_project(selected_project_id, rename_value.strip())
            st.sidebar.success("Project renamed.")
            st.rerun()

    confirm_delete = st.sidebar.checkbox(
        "I understand this deletes the project and all todos.",
        key="confirm_delete_project",
    )
    if st.sidebar.button(
        "Delete project",
        key="delete_project_button",
        disabled=not confirm_delete,
        type="secondary",
    ):
        deleted = delete_project(selected_project_id)
        if deleted:
            st.sidebar.success("Project deleted.")
            st.rerun()
        else:
            st.sidebar.error("Project could not be deleted.")


def sidebar(*, app_version: str) -> None:
    """Render sidebar controls and project lifecycle actions."""
    st.sidebar.title("Handoff")
    st.sidebar.caption("See who's on the hook across all your projects.")
    st.sidebar.caption(f"Version: {app_version}")

    st.sidebar.subheader("Create project")
    with st.sidebar.form("new_project"):
        new_name = st.text_input("Project name", key="new_proj_name")
        submit = st.form_submit_button("Create")
        if submit:
            if not new_name.strip():
                st.sidebar.error("Project name cannot be empty.")
            else:
                create_project(new_name.strip())
                st.sidebar.success("Project created.")
                st.rerun()

    projects = list_projects()
    st.sidebar.divider()
    _render_sidebar_project_management(projects)


def main(*, app_version: str) -> None:
    """Run the Streamlit app UI."""
    st.set_page_config(page_title="Handoff", layout="wide")
    init_db()
    _init_session_state()
    sidebar(app_version=app_version)
    logger.info("Rendering main todo table view")
    view()
