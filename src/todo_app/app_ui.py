"""Streamlit UI composition for the engagement to-do app."""

import json
from datetime import date, datetime

import pandas as pd
import streamlit as st
from loguru import logger

from todo_app.data import (
    create_project,
    create_todo,
    delete_project,
    delete_todo,
    get_export_payload,
    list_helpers,
    list_projects,
    normalize_helper_name,
    query_todos,
    rename_project,
    update_todo,
)
from todo_app.db import init_db
from todo_app.models import TodoStatus


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
        return raw_value.replace(tzinfo=None), None
    if isinstance(raw_value, date):
        return datetime.combine(raw_value, datetime.min.time()), None
    if isinstance(raw_value, str):
        candidate = raw_value.strip()
        if not candidate:
            return None, None
        try:
            parsed = datetime.fromisoformat(candidate.replace("Z", "+00:00"))
            return parsed.replace(tzinfo=None), None
        except ValueError:
            return None, f"invalid deadline '{candidate}'"
    return None, "unsupported deadline format"


def _build_todo_dataframe(todos: list, *, include_project: bool) -> pd.DataFrame:
    """Convert todo records to an editable dataframe."""
    rows = []
    for todo in todos:
        row = {
            "id": todo.id,
            "name": todo.name,
            "status": todo.status.value,
            "helper": todo.helper or "",
            "deadline": todo.deadline.date() if todo.deadline else None,
            "notes": todo.notes or "",
            "created_at": todo.created_at,
            "delete": False,
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
        "notes",
        "created_at",
        "delete",
    ]
    if include_project:
        cols.insert(1, "project")
    return pd.DataFrame(columns=cols)


def _apply_native_filters(
    source_df: pd.DataFrame,
    *,
    key_prefix: str,
    project_names: list[str],
) -> pd.DataFrame:
    """Apply compact native Streamlit filters for unified table view."""
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
        helper_options = ["-- All helpers --"] + list_helpers()
        selected_helper = st.selectbox(
            "Helper",
            options=helper_options,
            key=f"{key_prefix}_helper",
        )
        helper_filter = None if selected_helper == "-- All helpers --" else selected_helper
    with cols[4], st.popover("Deadline"):
        use_deadline_range = st.checkbox("Enable range", key=f"{key_prefix}_deadline_on")
        start_date = st.date_input("From", key=f"{key_prefix}_deadline_from")
        end_date = st.date_input("To", key=f"{key_prefix}_deadline_to")

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
    if helper_filter:
        filtered_df = filtered_df[filtered_df["helper"].fillna("") == helper_filter]
    if use_deadline_range:
        if start_date > end_date:
            st.error("Deadline range is invalid: From must be before or equal to To.")
            filtered_df = filtered_df.head(0)
        else:
            deadline_series = pd.to_datetime(filtered_df["deadline"], errors="coerce").dt.date
            mask = (
                deadline_series.notna()
                & (deadline_series >= start_date)
                & (deadline_series <= end_date)
            )
            filtered_df = filtered_df[mask]
    return filtered_df


def _save_rows(
    edited_df: pd.DataFrame,
    *,
    projects: list,
    default_project_id: int | None,
    context_label: str,
) -> dict[str, object]:
    """Validate and persist edited rows, returning operation summary."""
    project_by_name = {project.name: project.id for project in projects}

    summary = {"created": 0, "updated": 0, "deleted": 0, "skipped": 0, "errors": []}

    for row_no, row in enumerate(edited_df.to_dict("records"), start=1):
        todo_id_raw = row.get("__todo_id")
        is_existing = todo_id_raw is not None and not pd.isna(todo_id_raw)
        todo_id = int(todo_id_raw) if is_existing else None
        is_delete = bool(row.get("delete", False))

        if is_delete:
            if not is_existing:
                summary["skipped"] += 1
                summary["errors"].append(f"Row {row_no}: cannot delete unsaved row.")
                continue
            delete_ok = delete_todo(int(todo_id))
            if delete_ok:
                summary["deleted"] += 1
            else:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"Row {row_no}: todo id {int(todo_id)} not found for delete."
                )
            logger.info(
                "Save action delete context={context} "
                "row={row_no} todo_id={todo_id} success={success}",
                context=context_label,
                row_no=row_no,
                todo_id=int(todo_id) if is_existing else None,
                success=delete_ok,
            )
            continue

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
                logger.info(
                    "Save action update context={context} row={row_no} todo_id={todo_id}",
                    context=context_label,
                    row_no=row_no,
                    todo_id=todo_id,
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
            logger.info(
                "Save action create context={context} row={row_no} todo_id={todo_id}",
                context=context_label,
                row_no=row_no,
                todo_id=created.id,
            )

    return summary


def _render_editable_table(
    *,
    source_df: pd.DataFrame,
    projects: list,
    default_project_id: int | None,
    key_prefix: str,
    context_label: str,
) -> None:
    """Render native editable table and persist on save."""
    project_names = [project.name for project in projects]
    filtered_df = _apply_native_filters(
        source_df,
        key_prefix=key_prefix,
        project_names=project_names,
    )
    if filtered_df.empty:
        st.info("No rows match filters. You can still add rows and save.")
        filtered_df = source_df.head(0).copy()

    working_df = filtered_df.reset_index(drop=True).copy()
    working_df["__todo_id"] = working_df.get("id")
    working_df["__created_at"] = working_df.get("created_at")
    display_df = working_df.drop(columns=["id", "created_at"], errors="ignore").reset_index(
        drop=True
    )

    st.caption("Sort by clicking column headers. Filter using the controls above.")
    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        key=f"{key_prefix}_table",
        hide_index=True,
        column_config={
            "__todo_id": None,
            "__created_at": None,
            "project": st.column_config.SelectboxColumn(
                "Project",
                options=project_names,
                required=True,
            ),
            "name": st.column_config.TextColumn("Name", required=True),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=[status.value for status in TodoStatus],
                default=TodoStatus.DELEGATED.value,
                required=True,
            ),
            "helper": st.column_config.TextColumn("Helper"),
            "deadline": st.column_config.DateColumn("Deadline"),
            "notes": st.column_config.TextColumn("Notes"),
            "delete": st.column_config.CheckboxColumn("Delete"),
        },
    )

    if st.button("Save changes", type="primary", key=f"{key_prefix}_save"):
        logger.info(
            "Save requested for {context} with rows={rows}",
            context=context_label,
            rows=len(edited_df),
        )
        summary = _save_rows(
            edited_df,
            projects=projects,
            default_project_id=default_project_id,
            context_label=context_label,
        )
        logger.info(
            "Save summary context={context} created={created} updated={updated} "
            "deleted={deleted} skipped={skipped}",
            context=context_label,
            created=summary["created"],
            updated=summary["updated"],
            deleted=summary["deleted"],
            skipped=summary["skipped"],
        )
        success_msg = (
            f"Saved. Created: {summary['created']}, updated: {summary['updated']}, "
            f"deleted: {summary['deleted']}, skipped: {summary['skipped']}."
        )
        st.success(success_msg)
        if summary["errors"]:
            st.warning("\n".join(summary["errors"]))
        st.rerun()


def view_unified() -> None:
    """View and edit todos in one unified table."""
    st.subheader("Todos")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one in the sidebar.")
        return

    todos = query_todos()
    st.caption("Use each column's header menu for filtering and sorting.")
    df = _build_todo_dataframe(todos, include_project=True)
    _render_editable_table(
        source_df=df,
        projects=projects,
        default_project_id=projects[0].id if projects else None,
        key_prefix="unified",
        context_label="view=unified",
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


def _render_sidebar_backup() -> None:
    """Render backup/download controls."""
    st.sidebar.subheader("Backup")
    payload = get_export_payload()
    json_text = json.dumps(payload, indent=2)
    st.sidebar.download_button(
        "Download JSON backup",
        data=json_text,
        file_name="todo_backup.json",
        mime="application/json",
        key="download_json_backup",
    )

    todos = payload.get("todos", [])
    csv_text = (
        pd.DataFrame(todos).to_csv(index=False)
        if todos
        else "id,project_id,name,status,deadline,helper,notes,created_at\n"
    )
    st.sidebar.download_button(
        "Download CSV (todos)",
        data=csv_text,
        file_name="todo_todos.csv",
        mime="text/csv",
        key="download_csv_backup",
    )


def sidebar(*, app_version: str) -> None:
    """Render sidebar controls and project lifecycle actions."""
    st.sidebar.title("Engagement To-Do")
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
    st.sidebar.divider()
    _render_sidebar_backup()


def main(*, app_version: str) -> None:
    """Run the Streamlit app UI."""
    st.set_page_config(page_title="Engagement To-Do", layout="wide")
    init_db()
    _init_session_state()
    sidebar(app_version=app_version)
    logger.info("Rendering unified todo table view")
    view_unified()
