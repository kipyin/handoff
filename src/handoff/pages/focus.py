"""Focus / daily planning page for Handoff."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from handoff.data import query_todos, update_todo
from handoff.models import TodoStatus
from handoff.ui_components import _deadline_preset_bounds


def _build_focus_dataframe() -> pd.DataFrame:
    """Return a DataFrame of delegated todos split into logical buckets."""
    today = date.today()
    start_of_week, end_of_week = _deadline_preset_bounds("This week")
    assert start_of_week is not None and end_of_week is not None

    # Overdue + today
    end_today = datetime.combine(today, time.max)
    overdue_and_today = query_todos(
        statuses=[TodoStatus.DELEGATED],
        end=end_today,
    )

    # Later this week (after today).
    start_tomorrow = today + timedelta(days=1)
    start_tomorrow_dt = datetime.combine(start_tomorrow, time.min)
    end_week_dt = datetime.combine(end_of_week, time.max)
    later_this_week = query_todos(
        statuses=[TodoStatus.DELEGATED],
        start=start_tomorrow_dt,
        end=end_week_dt,
    )

    rows = []
    for todo in overdue_and_today:
        bucket = "overdue_or_today"
        deadline_date = todo.deadline.date() if todo.deadline else None
        rows.append(
            {
                "id": todo.id,
                "name": todo.name,
                "project": todo.project.name if todo.project else "",
                "helper": todo.helper or "",
                "deadline": deadline_date,
                "bucket": bucket,
            }
        )
    for todo in later_this_week:
        bucket = "later_this_week"
        deadline_date = todo.deadline.date() if todo.deadline else None
        rows.append(
            {
                "id": todo.id,
                "name": todo.name,
                "project": todo.project.name if todo.project else "",
                "helper": todo.helper or "",
                "deadline": deadline_date,
                "bucket": bucket,
            }
        )

    if not rows:
        return pd.DataFrame(
            columns=["id", "name", "project", "helper", "deadline", "bucket"]
        )
    return pd.DataFrame(rows)


def render_focus_page() -> None:
    """Render a guided daily planning flow."""
    st.subheader("Today’s focus")

    df = _build_focus_dataframe()
    if df.empty:
        st.info("No delegated todos with deadlines this week.")
        return

    today = date.today()

    # Step 1 – overdue + today
    st.markdown("### 1. Review overdue and today")
    step1 = df[df["bucket"] == "overdue_or_today"].copy()
    if step1.empty:
        st.caption("No overdue or due-today items.")
    else:
        selected_step1_ids: list[int] = []
        for _, row in step1.iterrows():
            todo_id = int(row["id"])
            label = f"{row['name']} ({row['project'] or 'no project'})"
            if isinstance(row["deadline"], date) and row["deadline"] < today:
                label = f"🔥 {label}"
            checkbox_key = f"focus_step1_select_{todo_id}"
            if st.checkbox(label, key=checkbox_key):
                selected_step1_ids.append(todo_id)

    # Step 2 – later this week
    st.markdown("### 2. Add a few from later this week")
    step2 = df[df["bucket"] == "later_this_week"].copy()
    selected_step2_ids: list[int] = []
    if step2.empty:
        st.caption("No additional items later this week.")
    else:
        for _, row in step2.iterrows():
            todo_id = int(row["id"])
            label = f"{row['name']} ({row['project'] or 'no project'})"
            checkbox_key = f"focus_step2_select_{todo_id}"
            if st.checkbox(label, key=checkbox_key):
                selected_step2_ids.append(todo_id)

    selected_ids = sorted(set(selected_step1_ids + selected_step2_ids))
    st.markdown("### 3. Today’s focus list")
    if not selected_ids:
        st.caption("Select a few items above to build today’s list.")
        return

    focus_rows = df[df["id"].isin(selected_ids)].copy()
    focus_rows = focus_rows[["name", "project", "helper", "deadline"]].rename(
        columns={"deadline": "Deadline"}
    )
    st.dataframe(focus_rows, use_container_width=True, hide_index=True)

    col_done, col_defer = st.columns(2)
    with col_done:
        if st.button("Mark selected as done", key="focus_mark_done"):
            for todo_id in selected_ids:
                update_todo(todo_id, status=TodoStatus.DONE)
            st.success("Marked selected todos as done.")
            st.rerun()

    with col_defer:
        defer_days = st.selectbox(
            "Defer by",
            options=[1, 2, 3, 7],
            format_func=lambda d: f"{d} day(s)",
            key="focus_defer_days",
        )
        if st.button("Defer selected", key="focus_defer"):
            for todo_id in selected_ids:
                # Naive deferral based on existing deadline or today if missing.
                todo_deadline = df.loc[df["id"] == todo_id, "deadline"].iloc[0]
                base_date: date = todo_deadline if isinstance(todo_deadline, date) else today
                new_deadline = base_date + timedelta(days=int(defer_days))
                new_deadline_dt = datetime.combine(new_deadline, time(hour=18, minute=0))
                update_todo(todo_id, deadline=new_deadline_dt)
            st.success("Deferred selected todos.")
            st.rerun()
