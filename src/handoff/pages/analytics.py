"""Analytics page for throughput and workload in the Handoff app."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from handoff.data import query_todos
from handoff.models import TodoStatus


def _parse_date_range(
    range_value: date | tuple[date, date] | list[date],
) -> tuple[date | None, date | None]:
    """Parse Streamlit date_input range value into (start_date, end_date).

    Args:
        range_value: Value from st.date_input with range; may be single date or
            (start, end) tuple/list.

    Returns:
        (start_date, end_date); both None if range_value is not a 2-element sequence.

    """
    if isinstance(range_value, (list, tuple)) and len(range_value) == 2:
        return range_value[0], range_value[1]
    return None, None


def _compute_weekly_counts(df_done: pd.DataFrame) -> pd.DataFrame:
    """Compute completed-per-week counts from a done-todos DataFrame.

    Expects df_done to have completed_at and id columns. Adds week_label and
    returns a DataFrame with week_label and completed count, sorted by week.

    Args:
        df_done: DataFrame with completed_at and id columns.

    Returns:
        DataFrame with columns week_label, completed.

    """
    iso = pd.to_datetime(df_done["completed_at"]).dt.isocalendar()
    df_done = df_done.copy()
    df_done["week_label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weekly = df_done.groupby("week_label")["id"].count().reset_index(name="completed")
    return weekly.sort_values("week_label")


def _compute_cycle_time_stats(
    df_done: pd.DataFrame,
) -> tuple[pd.DataFrame, float, float, float]:
    """Compute cycle time (created → completed) stats in days.

    Expects df_done to have created_at and completed_at columns. Adds cycle_days
    to a copy and returns it along with the stats.

    Args:
        df_done: DataFrame with created_at and completed_at.

    Returns:
        (df_with_cycle_days, mean_days, p50_days, p90_days).

    """
    df = df_done.copy()
    df["cycle_days"] = (
        pd.to_datetime(df["completed_at"]) - pd.to_datetime(df["created_at"])
    ).dt.days
    avg = float(df["cycle_days"].mean())
    p50 = float(df["cycle_days"].quantile(0.5))
    p90 = float(df["cycle_days"].quantile(0.9))
    return df, avg, p50, p90


def _compute_helper_load(todos: list) -> pd.DataFrame:
    """Build helper-load DataFrame from handoff (delegated) todos.

    Args:
        todos: List of Todo-like objects with .helper and .id.

    Returns:
        DataFrame with columns helper, id; grouped counts can be derived from it.
        Sorted by handoff count descending.

    """
    rows = []
    for todo in todos:
        helper = (getattr(todo, "helper", None) or "").strip()
        rows.append({"helper": helper or "(unassigned)", "id": todo.id})
    df = pd.DataFrame(rows)
    counts = df.groupby("helper")["id"].count().reset_index(name="handoff")
    return counts.sort_values("handoff", ascending=False)


def _build_done_dataframe(start: date | None, end: date | None) -> pd.DataFrame:
    """Return a DataFrame of completed todos within the optional date range.

    Args:
        start: Optional start date for the completed range.
        end: Optional end date for the completed range.

    Returns:
        DataFrame with columns id, name, helper, project, created_at, completed_at.

    """
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

    today = date.today()
    default_start = today - timedelta(days=28)
    range_value = st.date_input(
        "Completed between",
        value=(default_start, today),
        key="analytics_completed_range",
    )
    start_date, end_date = _parse_date_range(range_value)

    df_done = _build_done_dataframe(start_date, end_date)
    if df_done.empty:
        st.info("No completed todos in the selected range.")
        return

    df_done = df_done.copy()
    df_done["completed_date"] = pd.to_datetime(df_done["completed_at"]).dt.date

    # Section 1: Completed per week
    st.markdown("### Completed per week")
    weekly_counts = _compute_weekly_counts(df_done)
    st.bar_chart(weekly_counts.set_index("week_label"))

    # Section 2: Cycle time
    st.markdown("### Cycle time (created → completed)")
    df_done, avg_cycle, p50, p90 = _compute_cycle_time_stats(df_done)
    st.write(
        f"Average: {avg_cycle:.1f} days, median: {p50:.1f} days, 90th percentile: {p90:.1f} days."
    )
    st.bar_chart(df_done.set_index("completed_date")["cycle_days"])

    # Section 3: Helper load (current handoff)
    st.markdown("### Current helper load")
    handoff_todos = query_todos(statuses=[TodoStatus.DELEGATED], include_archived=False)
    if not handoff_todos:
        st.caption("No handoff todos at the moment.")
        return
    helper_counts = _compute_helper_load(handoff_todos)
    st.bar_chart(helper_counts.set_index("helper"))
