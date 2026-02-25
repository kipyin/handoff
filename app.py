"""Streamlit entrypoint for the to-do app. Run with: uv run streamlit run app.py."""

from datetime import date, datetime, timedelta, timezone

import pandas as pd
import streamlit as st

from todo_app.data import (
    create_project,
    create_todo,
    get_project,
    get_todos_by_helper,
    get_todos_by_timeframe,
    get_todos_by_project,
    list_helpers,
    list_projects,
    update_todo,
)
from todo_app.db import init_db
from todo_app.models import TodoStatus

# Page config
st.set_page_config(page_title="Engagement To-Do", layout="wide")
init_db()

# Session state for view and selected project
if "view" not in st.session_state:
    st.session_state.view = "By project"
if "selected_project_id" not in st.session_state:
    st.session_state.selected_project_id = None


def render_todo_row(todo, project_name: str | None = None, show_project: bool = False) -> None:
    """Render a single todo row with status-based styling and optional project label."""
    is_done = todo.status == TodoStatus.DONE
    is_canceled = todo.status == TodoStatus.CANCELED
    deadline = todo.deadline
    today = datetime.now(timezone.utc).date()
    is_overdue = deadline and deadline.date() < today
    is_due_today = deadline and deadline.date() == today

    # Container style
    bg = "rgba(255,200,200,0.4)" if (is_overdue or is_due_today) else None
    if is_done or is_canceled:
        bg = "rgba(200,200,200,0.3)"  # gray out

    with st.container():
        if bg:
            st.markdown(f'<div style="background: {bg}; padding: 0.5rem 0.75rem; border-radius: 6px; margin-bottom: 4px;">', unsafe_allow_html=True)
        cols = st.columns([3, 1, 1, 1, 1])
        with cols[0]:
            name_style = "opacity: 0.6; text-decoration: line-through;" if (is_done or is_canceled) else ""
            label = todo.name
            if show_project and project_name:
                label = f"[{project_name}] {todo.name}"
            st.markdown(f'<span style="{name_style}">{label}</span>', unsafe_allow_html=True)
        with cols[1]:
            st.text(todo.status.value)
        with cols[2]:
            st.text(todo.helper or "-")
        with cols[3]:
            st.text(todo.deadline.strftime("%Y-%m-%d %H:%M") if todo.deadline else "-")
        with cols[4]:
            if todo.notes:
                with st.popover("Notes"):
                    st.text(todo.notes)
            else:
                st.text("-")
        if bg:
            st.markdown("</div>", unsafe_allow_html=True)


def view_by_project() -> None:
    """View todos per project: gray out done, highlight due today/overdue."""
    st.subheader("View by project")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one below.")
        return

    # Project selector
    options = ["-- Select a project --"] + [p.name for p in projects]
    idx = 0
    if st.session_state.selected_project_id:
        for i, p in enumerate(projects):
            if p.id == st.session_state.selected_project_id:
                idx = i + 1
                break
    sel = st.selectbox("Project", options, index=idx, key="proj_sel")
    if sel == "-- Select a project --":
        st.session_state.selected_project_id = None
        return
    project_id = next(p.id for p in projects if p.name == sel)
    st.session_state.selected_project_id = project_id
    project = get_project(project_id)
    if not project:
        return
    todos = get_todos_by_project(project_id)
    st.markdown(f"**{project.name}** — {len(todos)} todo(s)")

    # Build editable table data
    if todos:
        rows = []
        for t in todos:
            rows.append(
                {
                    "id": t.id,
                    "name": t.name,
                    "status": t.status.value,
                    "helper": t.helper or "",
                    "deadline": t.deadline.date() if t.deadline else None,
                    "notes": t.notes or "",
                }
            )
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(columns=["id", "name", "status", "helper", "deadline", "notes"])

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        key=f"todos_project_{project_id}",
        hide_index=True,
        column_config={
            "id": st.column_config.NumberColumn("ID", disabled=True),
            "name": st.column_config.TextColumn("Name"),
            "status": st.column_config.SelectboxColumn(
                "Status",
                options=[s.value for s in TodoStatus],
                default=TodoStatus.DELEGATED.value,
            ),
            "helper": st.column_config.TextColumn("Helper"),
            "deadline": st.column_config.DateColumn("Deadline"),
            "notes": st.column_config.TextColumn("Notes"),
        },
    )

    if st.button("Save changes", type="primary"):
        for _, row in edited_df.iterrows():
            name_val = (row.get("name") or "").strip()
            if not name_val:
                # Ignore completely empty rows
                continue

            deadline_val = row.get("deadline")
            if isinstance(deadline_val, datetime):
                dl_dt = deadline_val
            elif isinstance(deadline_val, str) and deadline_val.strip():
                try:
                    parsed = datetime.fromisoformat(deadline_val.replace("Z", "+00:00"))
                    dl_dt = parsed if parsed.tzinfo else parsed.replace(tzinfo=None)
                except ValueError:
                    dl_dt = None
            elif isinstance(deadline_val, date) and not isinstance(deadline_val, datetime):
                dl_dt = datetime.combine(deadline_val, datetime.min.time())
            elif deadline_val and hasattr(deadline_val, "date"):
                try:
                    dl_dt = datetime.combine(deadline_val.date(), datetime.min.time())
                except (AttributeError, TypeError):
                    dl_dt = None
            else:
                dl_dt = None

            helper_val = (row.get("helper") or "").strip() or None
            notes_val = (row.get("notes") or "").strip() or None
            status_str = (row.get("status") or TodoStatus.DELEGATED.value).strip()
            status_val = TodoStatus(status_str)

            todo_id = row.get("id")
            if pd.isna(todo_id) or todo_id is None:
                # New todo
                create_todo(
                    project_id=project_id,
                    name=name_val,
                    status=status_val,
                    deadline=dl_dt,
                    helper=helper_val,
                    notes=notes_val,
                )
            else:
                # Existing todo update
                update_todo(
                    int(todo_id),
                    name=name_val,
                    status=status_val,
                    deadline=dl_dt,
                    helper=helper_val,
                    notes=notes_val,
                )

        st.success("Todos saved.")
        st.rerun()


def _save_editable_table_with_project(
    edited_df: pd.DataFrame,
    projects: list,
    default_project_id: int | None,
) -> None:
    """Save edited table rows that have a project column. Creates or updates todos."""
    project_by_name = {p.name: p.id for p in projects}
    for _, row in edited_df.iterrows():
        name_val = (row.get("name") or "").strip()
        if not name_val:
            continue

        project_name = (row.get("project") or "").strip()
        project_id = project_by_name.get(project_name) if project_name else default_project_id
        if project_id is None:
            continue

        deadline_val = row.get("deadline")
        if isinstance(deadline_val, datetime):
            dl_dt = deadline_val
        elif deadline_val:
            dl_dt = datetime.combine(deadline_val, datetime.min.time())
        else:
            dl_dt = None

        helper_val = (row.get("helper") or "").strip() or None
        notes_val = (row.get("notes") or "").strip() or None
        status_str = (row.get("status") or TodoStatus.DELEGATED.value).strip()
        status_val = TodoStatus(status_str)

        todo_id = row.get("id")
        if pd.isna(todo_id) or todo_id is None:
            create_todo(
                project_id=project_id,
                name=name_val,
                status=status_val,
                deadline=dl_dt,
                helper=helper_val,
                notes=notes_val,
            )
        else:
            update_todo(
                int(todo_id),
                project_id=project_id,
                name=name_val,
                status=status_val,
                deadline=dl_dt,
                helper=helper_val,
                notes=notes_val,
            )


def view_by_helper() -> None:
    """View all todos assigned to a helper across projects (editable table + add todos)."""
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
            ["-- Select helper --"] + helpers,
            index=0,
            key="helper_select",
        )
    with col2:
        typed_helper = st.text_input(
            "Or type helper name",
            placeholder="Type helper name to search",
            key="helper_search",
        )

    query_name = (typed_helper or "").strip()
    if not query_name and selected_helper != "-- Select helper --":
        query_name = selected_helper.strip()

    if not query_name:
        st.info("Choose a helper or type a name to see all their tasks across projects.")
        return

    todos = get_todos_by_helper(query_name)
    project_names = [p.name for p in projects]

    if todos:
        rows = []
        for t in todos:
            pname = t.project.name if t.project else ""
            rows.append(
                {
                    "id": t.id,
                    "project": pname,
                    "name": t.name,
                    "status": t.status.value,
                    "helper": t.helper or "",
                    "deadline": t.deadline.date() if t.deadline else None,
                    "notes": t.notes or "",
                }
            )
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(
            columns=["id", "project", "name", "status", "helper", "deadline", "notes"]
        )

    column_config = {
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "project": st.column_config.SelectboxColumn(
            "Project",
            options=project_names,
            required=True,
        ),
        "name": st.column_config.TextColumn("Name"),
        "status": st.column_config.SelectboxColumn(
            "Status",
            options=[s.value for s in TodoStatus],
            default=TodoStatus.DELEGATED.value,
        ),
        "helper": st.column_config.TextColumn("Helper"),
        "deadline": st.column_config.DateColumn("Deadline"),
        "notes": st.column_config.TextColumn("Notes"),
    }

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        key="todos_helper",
        hide_index=True,
        column_config=column_config,
    )

    if st.button("Save changes", type="primary", key="save_helper"):
        _save_editable_table_with_project(
            edited_df, projects, default_project_id=projects[0].id if projects else None
        )
        st.success("Todos saved.")
        st.rerun()

    st.caption(f"**Tasks for “{query_name}”** — add rows below to create todos in the chosen project.")


def view_by_timeframe() -> None:
    """View todos in a selected time period (editable table + add todos)."""
    st.subheader("View by timeframe")
    projects = list_projects()
    if not projects:
        st.info("No projects yet. Create one in the sidebar.")
        return

    today = datetime.now(timezone.utc).date()
    preset = st.radio("Period", ["Today", "This week", "Custom"], horizontal=True, key="timeframe_preset")
    if preset == "Today":
        start = datetime.combine(today, datetime.min.time())
        end = datetime.combine(today, datetime.max.time())
    elif preset == "This week":
        start = datetime.combine(today - timedelta(days=today.weekday()), datetime.min.time())
        end = datetime.combine(today + timedelta(days=6 - today.weekday()), datetime.max.time())
    else:
        start_d = st.date_input("From", value=today, key="tf_start")
        end_d = st.date_input("To", value=today + timedelta(days=6), key="tf_end")
        start = datetime.combine(start_d, datetime.min.time())
        end = datetime.combine(end_d, datetime.max.time())

    todos = get_todos_by_timeframe(start, end)
    project_names = [p.name for p in projects]

    if todos:
        rows = []
        for t in todos:
            pname = t.project.name if t.project else ""
            rows.append(
                {
                    "id": t.id,
                    "project": pname,
                    "name": t.name,
                    "status": t.status.value,
                    "helper": t.helper or "",
                    "deadline": t.deadline.date() if t.deadline else None,
                    "notes": t.notes or "",
                }
            )
        df = pd.DataFrame(rows)
    else:
        df = pd.DataFrame(
            columns=["id", "project", "name", "status", "helper", "deadline", "notes"]
        )

    column_config = {
        "id": st.column_config.NumberColumn("ID", disabled=True),
        "project": st.column_config.SelectboxColumn(
            "Project",
            options=project_names,
            required=True,
        ),
        "name": st.column_config.TextColumn("Name"),
        "status": st.column_config.SelectboxColumn(
            "Status",
            options=[s.value for s in TodoStatus],
            default=TodoStatus.DELEGATED.value,
        ),
        "helper": st.column_config.TextColumn("Helper"),
        "deadline": st.column_config.DateColumn("Deadline"),
        "notes": st.column_config.TextColumn("Notes"),
    }

    edited_df = st.data_editor(
        df,
        num_rows="dynamic",
        key="todos_timeframe",
        hide_index=True,
        column_config=column_config,
    )

    if st.button("Save changes", type="primary", key="save_timeframe"):
        _save_editable_table_with_project(
            edited_df, projects, default_project_id=projects[0].id if projects else None
        )
        st.success("Todos saved.")
        st.rerun()

    st.caption("Tasks in selected period. Add rows to create todos; set Project for new rows.")


def sidebar() -> None:
    """Sidebar: view switcher and create project."""
    st.sidebar.title("Engagement To-Do")
    st.session_state.view = st.sidebar.radio(
        "View",
        ["By project", "By helper", "By timeframe"],
        key="view_radio",
    )
    st.sidebar.divider()
    st.sidebar.subheader("Create project")
    with st.sidebar.form("new_project"):
        new_name = st.text_input("Project name", key="new_proj_name")
        if st.form_submit_button("Create"):
            if new_name and new_name.strip():
                create_project(new_name.strip())
                st.sidebar.success("Project created.")
                st.rerun()


def main() -> None:
    sidebar()
    if st.session_state.view == "By project":
        view_by_project()
    elif st.session_state.view == "By helper":
        view_by_helper()
    else:
        view_by_timeframe()


if __name__ == "__main__":
    main()
