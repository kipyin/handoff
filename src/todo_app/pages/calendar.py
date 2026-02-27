"""Calendar/weekly view for todos."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

import streamlit as st

from todo_app.data import get_todos_by_timeframe, update_todo
from todo_app.models import Todo, TodoStatus
from todo_app.ui_components import _deadline_preset_bounds, get_urgency_bucket


def _get_week_bounds(reference: date) -> tuple[datetime, datetime]:
    """Return start and end datetimes for the week containing reference date."""
    start_date, end_date = _deadline_preset_bounds("This week")
    assert start_date is not None and end_date is not None
    start_dt = datetime.combine(start_date, datetime.min.time())
    end_dt = datetime.combine(end_date, datetime.max.time())
    return start_dt, end_dt


def _group_todos_by_day(todos: list[Todo]) -> dict[date, list[Todo]]:
    """Group todos by their deadline date."""
    grouped: dict[date, list[Todo]] = defaultdict(list)
    for todo in todos:
        if not todo.deadline:
            continue
        day = todo.deadline.date()
        grouped[day].append(todo)
    return grouped


def render_calendar_page() -> None:
    """Render a week-at-a-glance view of todos."""
    st.subheader("This week")

    today = date.today()
    start_dt, end_dt = _get_week_bounds(today)
    todos = get_todos_by_timeframe(start_dt, end_dt)
    grouped = _group_todos_by_day(todos)

    if not todos:
        st.info("No todos with deadlines this week.")
        return

    days = [start_dt.date() + timedelta(days=i) for i in range(7)]
    cols = st.columns(7)
    for idx, day in enumerate(days):
        with cols[idx]:
            st.markdown(f"**{day.strftime('%a %d %b')}**")
            day_todos = grouped.get(day, [])
            if not day_todos:
                st.caption("No todos")
                continue
            for todo in day_todos:
                status_value = todo.status.value
                project_name = getattr(todo.project, "name", "")
                label = f"- {todo.name}"
                if project_name:
                    label += f"  _({project_name})_"

                completed_at = getattr(todo, "completed_at", None)
                if completed_at and start_dt <= completed_at <= end_dt:
                    label += f" (done {completed_at.date().isoformat()})"

                urgency = get_urgency_bucket(
                    todo.deadline.date() if todo.deadline else None,
                    status_value,
                )
                if status_value == TodoStatus.DONE.value:
                    label = f"✅ {label}"
                elif status_value == TodoStatus.CANCELED.value:
                    label = f"✖️ {label}"
                elif urgency == "overdue":
                    label = f"🔥 {label}"
                elif urgency == "today":
                    label = f"⭐ {label}"
                elif urgency == "soon":
                    label = f"◷ {label}"

                st.markdown(label)

                # Inline deadline adjustments for delegated todos.
                if status_value == TodoStatus.DELEGATED.value:
                    current_deadline_date = (
                        todo.deadline.date() if todo.deadline else day
                    )
                    todo_id = int(todo.id)
                    date_key = f"calendar_deadline_{todo_id}"
                    new_date = st.date_input(
                        "Deadline",
                        value=current_deadline_date,
                        key=date_key,
                    )
                    update_key = f"calendar_update_{todo_id}"
                    if st.button("Update", key=update_key):
                        new_deadline_dt = datetime.combine(
                            new_date,
                            time(hour=18, minute=0),
                        )
                        update_todo(todo_id, deadline=new_deadline_dt)
                        st.success("Deadline updated.")
                        st.rerun()
