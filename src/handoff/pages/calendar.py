"""Calendar/weekly view for todos."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, time, timedelta

import streamlit as st

from handoff.data import query_todos, update_todo
from handoff.dates import week_bounds
from handoff.models import Todo, TodoStatus


def _urgency_for_display(deadline_date: date | None, status_value: str) -> str:
    """Return urgency bucket for calendar display only (overdue, today, soon, none).

    Args:
        deadline_date: Todo deadline date, or None.
        status_value: Todo status value (e.g. handoff, done).

    Returns:
        One of "overdue", "today", "soon", or "none".

    """
    if status_value != TodoStatus.DELEGATED.value:
        return "none"
    if deadline_date is None:
        return "none"
    today = date.today()
    if deadline_date < today:
        return "overdue"
    if deadline_date == today:
        return "today"
    _, sunday = week_bounds(today)
    if today < deadline_date <= sunday:
        return "soon"
    return "none"


def _get_week_bounds(reference: date) -> tuple[datetime, datetime]:
    """Return start and end datetimes for the week containing reference date.

    Args:
        reference: Any date in the target week.

    Returns:
        Tuple of (monday 00:00, sunday 23:59:59) for that week.

    """
    monday, sunday = week_bounds(reference)
    start_dt = datetime.combine(monday, datetime.min.time())
    end_dt = datetime.combine(sunday, datetime.max.time())
    return start_dt, end_dt


def _group_todos_by_day(todos: list[Todo]) -> dict[date, list[Todo]]:
    """Group todos by their deadline date.

    Args:
        todos: List of todos (with deadline set).

    Returns:
        Dict mapping each deadline date to list of todos for that day.

    """
    grouped: dict[date, list[Todo]] = defaultdict(list)
    for todo in todos:
        if not todo.deadline:
            continue
        day = todo.deadline.date()
        grouped[day].append(todo)
    return grouped


def render_calendar_page() -> None:
    """Render a week-at-a-glance view of todos."""
    today = date.today()
    offset_key = "calendar_week_offset"

    week_offset = int(st.session_state.get(offset_key, 0))
    reference_date = today + timedelta(weeks=week_offset)

    start_dt, end_dt = _get_week_bounds(reference_date)
    days = [start_dt.date() + timedelta(days=i) for i in range(7)]

    # Navigation row: Prev/Next week only (date picker removed to avoid session_state conflict).
    nav_cols = st.columns(7)
    with nav_cols[0]:
        if st.button("← Previous week", key="calendar_prev"):
            st.session_state[offset_key] = week_offset - 1
            st.rerun()
    with nav_cols[6]:
        if st.button("Next week →", key="calendar_next"):
            st.session_state[offset_key] = week_offset + 1
            st.rerun()
    # Date picker commented out: updating session_state[calendar_selected_date] in button
    # callbacks after the date_input widget owns that key causes StreamlitAPIException.
    # with nav_cols[3]:
    #     selected_date = st.date_input("View week of", key="calendar_selected_date")
    #     if selected_date != reference_date:
    #         delta_days = (selected_date - today).days
    #         st.session_state[offset_key] = delta_days // 7
    #         st.rerun()

    st.subheader(f"Week of {start_dt.date().isoformat()} – {end_dt.date().isoformat()}")

    todos = query_todos(start=start_dt, end=end_dt)
    grouped = _group_todos_by_day(todos)

    if not todos:
        st.info("No todos with deadlines in this week.")
        return

    cols = st.columns(7)
    for idx, day in enumerate(days):
        with cols[idx]:
            header = f"**{day.strftime('%a %d %b')}**"
            if day == today:
                header += " — *Today*"
            st.markdown(header)
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

                urgency = _urgency_for_display(
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

                # Inline deadline adjustments for handoff todos (compact: one row).
                if status_value == TodoStatus.DELEGATED.value:
                    current_deadline_date = todo.deadline.date() if todo.deadline else day
                    todo_id = int(todo.id)
                    date_key = f"calendar_deadline_{todo_id}"
                    update_key = f"calendar_update_{todo_id}"
                    adj_c1, adj_c2 = st.columns([2, 1])
                    with adj_c1:
                        new_date = st.date_input(
                            "Deadline",
                            value=current_deadline_date,
                            key=date_key,
                            label_visibility="collapsed",
                        )
                    with adj_c2:
                        if st.button("U", key=update_key):
                            new_deadline_dt = datetime.combine(
                                new_date,
                                time(hour=18, minute=0),
                            )
                            update_todo(todo_id, deadline=new_deadline_dt)
                            st.success("Deadline updated.")
                            st.rerun()
