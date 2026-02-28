"""Analytics page for throughput and workload in the Chaos Queue app."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from handoff.data import query_todos
from handoff.models import TodoStatus


def _build_done_dataframe(start: date | None, end: date | None) -> pd.DataFrame:
    """Return a DataFrame of completed todos within the optional date range."""
    start_dt: datetime | None = None
    end_dt: datetime | None = None
    if start is not None:
        start_dt = datetime.combine(start, time.min)
    if end is not None:
        # Include the full end day.
        end_dt = datetime.combine(end, time.max)

    todos = query_todos(
        statuses=[TodoStatus.DONE],
        start=start_dt,
        end=end_dt,
        include_archived=False,
    )
    if not todos:
        return pd.DataFrame(
            columns=[
                "id",
                "name",
                "helper",
                "project",
                "created_at",
                "completed_at",
            ],
        )

    rows = []
    for todo in todos:
        rows.append(
            {
                "id": todo.id,
                "name": todo.name,
                "helper": todo.helper or "",
                "project": todo.project.name if todo.project else "",
                "created_at": todo.created_at,
                "completed_at": todo.completed_at,
            }
        )
    return pd.DataFrame(rows)


def render_analytics_page() -> None:
    """Render throughput and workload analytics."""
    st.subheader("Analytics")

    # Filters
    today = date.today()
    default_start = today - timedelta(days=28)
    range_value = st.date_input(
        "Completed between",
        value=(default_start, today),
        key="analytics_completed_range",
    )
    start_date: date | None
    end_date: date | None
    if isinstance(range_value, (list, tuple)) and len(range_value) == 2:
        start_date, end_date = range_value[0], range_value[1]
    else:
        start_date = end_date = None

    df_done = _build_done_dataframe(start_date, end_date)
    if df_done.empty:
        st.info("No completed todos in the selected range.")
        return

    df_done = df_done.copy()
    df_done["completed_date"] = pd.to_datetime(df_done["completed_at"]).dt.date

    # Section 1: Completed per week
    st.markdown("### Completed per week")
    iso = pd.to_datetime(df_done["completed_at"]).dt.isocalendar()
    df_done["week_label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weekly_counts = df_done.groupby("week_label")["id"].count().reset_index(name="completed")
    weekly_counts = weekly_counts.sort_values("week_label")
    st.bar_chart(weekly_counts.set_index("week_label"))

    # Section 2: Cycle time
    st.markdown("### Cycle time (created → completed)")
    df_done["cycle_days"] = (
        pd.to_datetime(df_done["completed_at"]) - pd.to_datetime(df_done["created_at"])
    ).dt.days
    avg_cycle = df_done["cycle_days"].mean()
    p50 = df_done["cycle_days"].quantile(0.5)
    p90 = df_done["cycle_days"].quantile(0.9)
    st.write(
        f"Average: {avg_cycle:.1f} days, median: {p50:.1f} days, 90th percentile: {p90:.1f} days."
    )
    st.bar_chart(df_done.set_index("completed_date")["cycle_days"])

    # Section 3: Helper load (current delegated)
    st.markdown("### Current helper load")
    delegated = query_todos(statuses=[TodoStatus.DELEGATED], include_archived=False)
    if not delegated:
        st.caption("No delegated todos at the moment.")
        return
    rows = []
    for todo in delegated:
        rows.append(
            {
                "helper": todo.helper or "(unassigned)",
                "id": todo.id,
            }
        )
    df_delegated = pd.DataFrame(rows)
    helper_counts = df_delegated.groupby("helper")["id"].count().reset_index(name="delegated")
    helper_counts = helper_counts.sort_values("delegated", ascending=False)
    st.bar_chart(helper_counts.set_index("helper"))
