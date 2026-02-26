"""Streamlit UI composition for the engagement to-do app."""

import json
from datetime import UTC, date, datetime, timedelta

import pandas as pd
import streamlit as st
from loguru import logger

from todo_app.data import (
    create_project,
    create_todo,
    delete_project,
    delete_todo,
    get_export_payload,
    get_project,
    get_todos_by_helper,
    get_todos_by_project,
    get_todos_by_timeframe,
    list_helpers,
    list_projects,
    normalize_helper_name,
    rename_project,
    update_todo,
)
from todo_app.db import init_db
from todo_app.models import TodoStatus


def _init_session_state() -> None:
    """Initialize Streamlit session defaults."""
    defaults = {
        "view": "By project",
        "selected_project_id": None,
        "helper_select": "-- Select helper --",
        "helper_search": "",
        "timeframe_preset": "Today",
        "tf_start": datetime.now(UTC).date(),
        "tf_end": datetime.now(UTC).date() + timedelta(days=6),
    }
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
            "selected": False,
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
        "selected",
        "delete",
    ]
    if include_project:
        cols.insert(1, "project")
    return pd.DataFrame(columns=cols)


def _apply_shared_filters(df: pd.DataFrame, *, key_prefix: str) -> pd.DataFrame:
    """Apply shared search/filter/sort controls and return filtered rows."""
    st.caption("Search, filter, and sort before saving.")
    col1, col2, col3 = st.columns(3)
    with col1:
        query = st.text_input(
            "Search",
            placeholder="name, notes, helper",
            key=f"{key_prefix}_search",
        ).strip()
    with col2:
        status_filters = st.multiselect(
            "Statuses",
            options=[status.value for status in TodoStatus],
            key=f"{key_prefix}_statuses",
        )
    with col3:
        sort_by = st.selectbox(
            "Sort by",
            options=["deadline", "status", "created_at"],
            key=f"{key_prefix}_sort_by",
        )

    extra_col1, extra_col2 = st.columns(2)
    with extra_col1:
        descending = st.checkbox("Descending", value=False, key=f"{key_prefix}_sort_desc")
    with extra_col2:
        project_filters: list[str] = []
        if "project" in df.columns:
            project_filters = st.multiselect(
                "Projects",
                options=sorted({p for p in df["project"].dropna().tolist() if p}),
                key=f"{key_prefix}_projects",
            )

    filtered = df.copy()
    if query:
        searchable_cols = ["name", "notes", "helper"]
        if "project" in filtered.columns:
            searchable_cols.append("project")
        mask = (
            filtered[searchable_cols]
            .fillna("")
            .agg(" ".join, axis=1)
            .str.contains(query, case=False)
        )
        filtered = filtered[mask]

    if status_filters:
        filtered = filtered[filtered["status"].isin(status_filters)]

    if project_filters and "project" in filtered.columns:
        filtered = filtered[filtered["project"].isin(project_filters)]

    if sort_by in filtered.columns:
        filtered = filtered.sort_values(by=sort_by, ascending=not descending, na_position="last")
    return filtered


def _save_rows(
    edited_df: pd.DataFrame,
    *,
    projects: list,
    default_project_id: int | None,
    orig_ids: pd.Series | None,
    bulk_status: str | None,
) -> dict[str, object]:
    """Validate and persist edited rows, returning operation summary."""
    project_by_name = {project.name: project.id for project in projects}
    id_by_index = orig_ids.reindex(edited_df.index) if orig_ids is not None else None

    summary = {"created": 0, "updated": 0, "deleted": 0, "skipped": 0, "errors": []}

    if bulk_status:
        selected_mask = edited_df.get("selected", False).fillna(False).astype(bool)
        edited_df.loc[selected_mask, "status"] = bulk_status

    for idx, row in edited_df.iterrows():
        row_no = int(idx) + 1
        todo_id = id_by_index.get(idx) if id_by_index is not None else None
        is_existing = todo_id is not None and not pd.isna(todo_id)
        is_delete = bool(row.get("delete", False))

        if is_delete:
            if not is_existing:
                summary["skipped"] += 1
                summary["errors"].append(f"Row {row_no}: cannot delete unsaved row.")
                continue
            if delete_todo(int(todo_id)):
                summary["deleted"] += 1
            else:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"Row {row_no}: todo id {int(todo_id)} not found for delete."
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
                int(todo_id),
                project_id=project_id,
                name=name_val,
                status=status_val,
                deadline=deadline_val,
                helper=helper_val,
                notes=notes_val,
            )
            if updated is None:
                summary["skipped"] += 1
                summary["errors"].append(
                    f"Row {row_no}: todo id {int(todo_id)} not found for update."
                )
            else:
                summary["updated"] += 1
        else:
            create_todo(
                project_id=project_id,
                name=name_val,
                status=status_val,
                deadline=deadline_val,
                helper=helper_val,
                notes=notes_val,
            )
            summary["created"] += 1

    return summary


def _render_editable_table(
    *,
    source_df: pd.DataFrame,
    projects: list,
    default_project_id: int | None,
    key_prefix: str,
) -> None:
    """Render table controls/editor and persist on save."""
    filtered_df = _apply_shared_filters(source_df, key_prefix=key_prefix)
    if filtered_df.empty:
        st.info("No rows match the current filters. You can still add rows and save.")
        filtered_df = source_df.head(0).copy()

    orig_ids = (
        filtered_df["id"].copy() if "id" in filtered_df.columns else pd.Series(dtype="float64")
    )
    display_df = filtered_df.drop(columns=["id", "created_at"], errors="ignore")

    project_names = [project.name for project in projects]
    column_config = {
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
        "selected": st.column_config.CheckboxColumn("Selected"),
        "delete": st.column_config.CheckboxColumn("Delete"),
    }
    if "project" in display_df.columns:
        column_config["project"] = st.column_config.SelectboxColumn(
            "Project", options=project_names, required=True
        )

    bulk_status = st.selectbox(
        "Bulk status for selected rows (applies on save)",
        options=["No bulk status"] + [status.value for status in TodoStatus],
        key=f"{key_prefix}_bulk_status",
    )

    edited_df = st.data_editor(
        display_df,
        num_rows="dynamic",
        key=f"{key_prefix}_table",
        hide_index=True,
        column_config=column_config,
    )

    if st.button("Save changes", type="primary", key=f"{key_prefix}_save"):
        selected_bulk_status = bulk_status if bulk_status != "No bulk status" else None
        summary = _save_rows(
            edited_df,
            projects=projects,
            default_project_id=default_project_id,
            orig_ids=orig_ids,
            bulk_status=selected_bulk_status,
        )
        success_msg = (
            f"Saved. Created: {summary['created']}, updated: {summary['updated']}, "
            f"deleted: {summary['deleted']}, skipped: {summary['skipped']}."
        )
        st.success(success_msg)
        if summary["errors"]:
            st.warning("\n".join(summary["errors"]))
        st.rerun()


def view_by_project() -> None:
    """View and edit todos in a selected project."""
    st.subheader("View by project")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one in the sidebar.")
        return

    options = ["-- Select a project --"] + [project.name for project in projects]
    selected_index = 0
    if st.session_state.selected_project_id is not None:
        for idx, project in enumerate(projects):
            if project.id == st.session_state.selected_project_id:
                selected_index = idx + 1
                break
    selected_name = st.selectbox("Project", options=options, index=selected_index, key="proj_sel")
    if selected_name == "-- Select a project --":
        st.session_state.selected_project_id = None
        st.info("Select a project to edit todos.")
        return

    project_id = next(project.id for project in projects if project.name == selected_name)
    st.session_state.selected_project_id = project_id
    project = get_project(project_id)
    if not project:
        st.error("Selected project was not found.")
        return

    todos = get_todos_by_project(project_id)
    st.markdown(f"**{project.name}** - {len(todos)} todo(s)")
    df = _build_todo_dataframe(todos, include_project=False)
    _render_editable_table(
        source_df=df,
        projects=projects,
        default_project_id=project_id,
        key_prefix=f"project_{project_id}",
    )


def view_by_helper() -> None:
    """View and edit todos assigned to a helper."""
    st.subheader("View by helper")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one in the sidebar.")
        return

    helpers = list_helpers()
    col1, col2 = st.columns(2)
    with col1:
        selected_helper = st.selectbox(
            "Helper (dropdown)",
            options=["-- Select helper --"] + helpers,
            key="helper_select",
        )
    with col2:
        typed_helper = st.text_input(
            "Or type helper name",
            key="helper_search",
            placeholder="Type helper name to search",
        )

    query_name = (typed_helper or "").strip()
    if not query_name and selected_helper != "-- Select helper --":
        query_name = selected_helper.strip()
    query_name = normalize_helper_name(query_name) or ""

    if not query_name:
        st.info("Choose a helper or type a name to see tasks across projects.")
        return

    todos = get_todos_by_helper(query_name)
    st.caption(f"Tasks for helper '{query_name}'.")
    df = _build_todo_dataframe(todos, include_project=True)
    _render_editable_table(
        source_df=df,
        projects=projects,
        default_project_id=projects[0].id if projects else None,
        key_prefix=f"helper_{query_name.lower()}",
    )


def view_by_timeframe() -> None:
    """View and edit todos in a selected timeframe."""
    st.subheader("View by timeframe")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one in the sidebar.")
        return

    today = datetime.now(UTC).date()
    preset = st.radio(
        "Period",
        ["Today", "This week", "Custom"],
        horizontal=True,
        key="timeframe_preset",
    )
    if preset == "Today":
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
    elif preset == "This week":
        start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
        end = datetime.combine(today + timedelta(days=6 - today.weekday()), datetime.max.time())
    else:
        start_d = st.date_input("From", value=st.session_state.tf_start, key="tf_start")
        end_d = st.date_input("To", value=st.session_state.tf_end, key="tf_end")
        if start_d > end_d:
            st.error("From date must be before or equal to To date.")
            return
        start = datetime.combine(start_d, datetime.min.time())
        end = datetime.combine(end_d, datetime.max.time())

    todos = get_todos_by_timeframe(start, end)
    st.caption(f"Tasks between {start.date().isoformat()} and {end.date().isoformat()}.")
    df = _build_todo_dataframe(todos, include_project=True)
    _render_editable_table(
        source_df=df,
        projects=projects,
        default_project_id=projects[0].id if projects else None,
        key_prefix=f"timeframe_{preset.lower()}",
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
            if st.session_state.selected_project_id == selected_project_id:
                st.session_state.selected_project_id = None
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
    st.session_state.view = st.sidebar.radio(
        "View",
        ["By project", "By helper", "By timeframe"],
        key="view_radio",
    )
    st.sidebar.divider()

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
    logger.info("Switched main view to {view}", view=st.session_state.view)
    if st.session_state.view == "By project":
        view_by_project()
    elif st.session_state.view == "By helper":
        view_by_helper()
    else:
        view_by_timeframe()
