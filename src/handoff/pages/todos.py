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
    normalize_helper_name,
    query_todos,
    update_todo,
)
from handoff.models import TodoStatus

# Deadline filter presets (used by table filters and tests).
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
        weekday = today.weekday()
        monday = today - timedelta(days=weekday)
        sunday = monday + timedelta(days=6)
        return monday, sunday
    return None, None


def _coerce_deadline(raw_value: object) -> tuple[datetime | None, str | None]:
    """Coerce UI values into a deadline datetime; return (datetime, error_message)."""
    if raw_value is None or raw_value == "":
        return None, None
    if isinstance(raw_value, datetime):
        return raw_value.astimezone().replace(tzinfo=None), None
    if isinstance(raw_value, date):
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
            "helper": normalize_helper_name(todo.helper) or "",
            "deadline": deadline_date,
            "notes": todo.notes or "",
            "created_at": todo.created_at,
        }
        if include_project:
            row["project"] = (
                todo.project.name if todo.project else ""
            )
        rows.append(row)
    if rows:
        return pd.DataFrame(rows)

    cols = [
        "id",
        "name",
        "status",
        "helper",
        "deadline",
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
            "notes",
            "created_at",
        ]
    return pd.DataFrame(columns=pd.Index(cols))


def _apply_native_filters(
    source_df: pd.DataFrame,
    *,
    key_prefix: str,
    project_names: list[str],
) -> tuple[pd.DataFrame, dict]:
    """Apply filters; return (filtered_df, filter_state)."""
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

    return filtered_df, filter_state


def _row_equals(current: dict, prev: dict) -> bool:
    """Return True if current row has same persistable fields as prev."""
    if current.get("project", "").strip() != (prev.get("project") or "").strip():
        return False
    if (current.get("name") or "").strip() != (prev.get("name") or "").strip():
        return False
    if (current.get("status") or "").strip() != (prev.get("status") or "").strip():
        return False
    c_notes = (current.get("notes") or "").strip() or None
    p_notes = (prev.get("notes") or "").strip() or None
    if c_notes != p_notes:
        return False
    curr_helper = (current.get("helper") or "").strip() or None
    prev_helper = (prev.get("helper") or "").strip() or None
    if curr_helper != prev_helper:
        return False
    curr_deadline = current.get("deadline")
    prev_deadline = prev.get("deadline")
    if curr_deadline is None and prev_deadline is None:
        pass
    elif (curr_deadline is None) != (prev_deadline is None):
        return False
    else:
        curr_d = (
            curr_deadline.date()
            if hasattr(curr_deadline, "date") and callable(curr_deadline.date)
            else curr_deadline
        )
        if isinstance(prev_deadline, str):
            prev_d = datetime.fromisoformat(prev_deadline[:10]).date()
        elif hasattr(prev_deadline, "date") and callable(prev_deadline.date):
            prev_d = prev_deadline.date()
        else:
            prev_d = prev_deadline
        if curr_d != prev_d:
            return False
    return True


def _save_rows(
    edited_df: pd.DataFrame,
    *,
    projects: list,
    default_project_id: int | None,
    context_label: str,
    last_snapshot_json: str | None = None,
) -> dict[str, object]:
    """Validate and persist edited rows; return operation summary."""
    import json as _json

    project_by_name = {project.name: project.id for project in projects}
    prev_by_id: dict[int, dict] = {}
    if last_snapshot_json:
        try:
            prev_records = _json.loads(last_snapshot_json)
            for rec in prev_records if isinstance(prev_records, list) else []:
                tid = rec.get("__todo_id")
                if tid is not None and not (isinstance(tid, float) and pd.isna(tid)):
                    prev_by_id[int(tid)] = rec
        except (TypeError, ValueError):
            pass

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

        helper_val = row.get("helper")
        notes_val = (row.get("notes") or "").strip() or None

        if is_existing:
            prev_row = prev_by_id.get(todo_id) if todo_id is not None else None
            if prev_row is not None and _row_equals(row, prev_row):
                continue
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
                    "Save action update context={context} row={row_no} todo_id={todo_id} name={name!r}",
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
    """Render editable table with filters and persist via data_editor on_change."""
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

    MAX_TODO_ROWS = 30
    total_filtered = len(filtered_df)
    if total_filtered > MAX_TODO_ROWS:
        filtered_df = filtered_df.head(MAX_TODO_ROWS).reset_index(drop=True)
    table_caption = (
        f"Showing first {min(total_filtered, MAX_TODO_ROWS)} of {total_filtered} todos. "
        "Use filters to narrow."
        if total_filtered > MAX_TODO_ROWS
        else ""
    )

    working_df = filtered_df.reset_index(drop=True).copy()
    working_df["__todo_id"] = working_df.get("id")
    working_df["__created_at"] = working_df.get("created_at")
    display_df = working_df.drop(columns=["id", "created_at"], errors="ignore").reset_index(
        drop=True
    )

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
        "deadline",
        "notes",
    ]
    base_caption = "Filter using the controls above. Use row deletion in the table to remove todos."
    st.caption(f"{base_caption} {table_caption}" if table_caption else base_caption)

    snapshot_key = f"{key_prefix}_last_saved_snapshot"
    status_key = f"{key_prefix}_saving_status"
    error_key = f"{key_prefix}_saving_error"
    editor_state_key = f"{key_prefix}_table"

    _SAVE_CTX_KEY = "_todos_save_ctx"
    if _SAVE_CTX_KEY not in st.session_state:
        st.session_state[_SAVE_CTX_KEY] = {}
    st.session_state[_SAVE_CTX_KEY][key_prefix] = {
        "projects": projects,
        "default_project_id": default_project_id,
        "context_label": context_label,
        "display_df": display_df,
        "remember_project_key": remember_project_key,
        "remember_helper_key": remember_helper_key,
        "snapshot_key": snapshot_key,
        "status_key": status_key,
        "error_key": error_key,
    }

    def _on_table_change() -> None:
        ctx = st.session_state.get(_SAVE_CTX_KEY, {}).get(key_prefix)
        edited_df = st.session_state.get(editor_state_key)
        if ctx is None or edited_df is None or not isinstance(edited_df, pd.DataFrame):
            return
        last_snapshot = st.session_state.get(ctx["snapshot_key"])
        st.session_state[ctx["status_key"]] = "saving"
        st.session_state[ctx["error_key"]] = ""
        logger.info(
            "Autosave (on_change) for {context} with rows={rows}",
            context=ctx["context_label"],
            rows=len(edited_df),
        )
        deleted = 0
        skipped_for_delete = 0
        delete_errors: list[str] = []
        display_df_ctx = ctx["display_df"]
        editor_state = st.session_state.get(editor_state_key)
        deleted_rows_indices: list[int] = []
        if hasattr(editor_state, "get"):
            deleted_rows_indices = editor_state.get("deleted_rows") or []
        for raw_idx in deleted_rows_indices:
            try:
                idx = int(raw_idx)
            except (TypeError, ValueError):
                continue
            if not 0 <= idx < len(display_df_ctx):
                continue
            raw_id = display_df_ctx.iloc[idx].get("__todo_id")
            if raw_id is None or pd.isna(raw_id):
                continue
            todo_id = int(raw_id)
            if delete_todo(todo_id):
                deleted += 1
            else:
                skipped_for_delete += 1
                delete_errors.append(
                    f"Row {idx + 1}: todo id {todo_id} not found for delete."
                )
        try:
            summary = _save_rows(
                edited_df,
                projects=ctx["projects"],
                default_project_id=ctx["default_project_id"],
                context_label=ctx["context_label"],
                last_snapshot_json=last_snapshot,
            )
        except Exception as exc:  # noqa: BLE001
            logger.exception(
                "Autosave failed for {context}: {}",
                ctx["context_label"],
                exc,
            )
            st.session_state[ctx["status_key"]] = "error"
            st.session_state[ctx["error_key"]] = "Autosave failed. See logs for details."
            return
        summary["deleted"] = summary.get("deleted", 0) + deleted
        summary["skipped"] = summary.get("skipped", 0) + skipped_for_delete
        if delete_errors:
            summary.setdefault("errors", []).extend(delete_errors)
        logger.info(
            "Autosave result context={context}: created={created}, updated={updated}, "
            "deleted={deleted}, skipped={skipped}",
            context=ctx["context_label"],
            created=summary["created"],
            updated=summary["updated"],
            deleted=summary["deleted"],
            skipped=summary["skipped"],
        )
        last_created_project_id = summary.get("last_created_project_id")
        last_created_helper = summary.get("last_created_helper")
        if last_created_project_id is not None:
            st.session_state[ctx["remember_project_key"]] = last_created_project_id
        if last_created_helper is not None:
            st.session_state[ctx["remember_helper_key"]] = (
                last_created_helper
                if isinstance(last_created_helper, str)
                else (last_created_helper[0] if last_created_helper else "")
            )
        current_snapshot = edited_df.to_json(date_format="iso", orient="records")
        st.session_state[ctx["snapshot_key"]] = current_snapshot
        st.session_state[ctx["status_key"]] = "saved"
        st.rerun()

    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        height="content",
        key=editor_state_key,
        hide_index=True,
        column_order=column_order,
        on_change=_on_table_change,
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
            "helper": st.column_config.SelectboxColumn(
                "Helper",
                options=[""] + list_helpers(),
                default=default_helper,
            ),
            "deadline": st.column_config.DateColumn("Deadline"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

    current_snapshot = edited_df.to_json(date_format="iso", orient="records")
    if st.session_state.get(snapshot_key) is None:
        st.session_state[snapshot_key] = current_snapshot
        st.session_state[status_key] = "saved"
        st.session_state[error_key] = ""

    status_value = st.session_state.get(status_key, "saved")
    error_message = st.session_state.get(error_key, "")
    if status_value == "saving":
        st.caption("Saving changes\u2026")
    elif status_value == "error":
        st.error(error_message or "Last save failed. See logs for details.")
    else:
        st.caption("All changes saved.")


def render_todos_page() -> None:
    """Render the main todos page with a unified editable table."""
    st.subheader("Todos")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one on the Projects page.")
        return

    todos = query_todos()
    df = _build_todo_dataframe(todos, include_project=True)
    _render_editable_table(
        source_df=df,
        projects=projects,
        key_prefix="main",
        context_label="view=todos_page",
    )
