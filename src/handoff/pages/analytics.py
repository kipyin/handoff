"""Dashboard page — at-a-glance pulse check for the Handoff app."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta

import pandas as pd
import streamlit as st

from handoff.data import query_todos
from handoff.dates import week_bounds
from handoff.models import Todo, TodoStatus


def _count_open_handoffs() -> int:
    """Return the number of currently open (delegated) todos."""
    return len(query_todos(statuses=[TodoStatus.HANDOFF], include_archived=False))


def _completed_in_range(start: date, end: date) -> list[Todo]:
    """Return todos completed between *start* and *end* (inclusive)."""
    return query_todos(
        statuses=[TodoStatus.DONE],
        completed_start=datetime.combine(start, time.min),
        completed_end=datetime.combine(end, time.max),
        include_archived=False,
    )


def _compute_cycle_time_stats(
    todos: list[Todo],
) -> tuple[float, float, float] | None:
    """Return (mean, median, p90) cycle-time in days, or None if empty.

    Skips todos that have no created_at or completed_at.
    """
    days = []
    for t in todos:
        if t.created_at and t.completed_at:
            delta = (t.completed_at - t.created_at).total_seconds() / 86400
            days.append(delta)
    if not days:
        return None
    s = pd.Series(days)
    return float(s.mean()), float(s.median()), float(s.quantile(0.9))


def _compute_overdue_rate(todos: list[Todo]) -> float | None:
    """Fraction of completed todos that were finished after their deadline.

    Only considers todos that have both a deadline and a completed_at.
    Returns None when no qualifying todos exist.
    """
    with_deadline = [t for t in todos if t.deadline and t.completed_at]
    if not with_deadline:
        return None
    overdue = sum(1 for t in with_deadline if t.completed_at.date() > t.deadline)
    return overdue / len(with_deadline)


def _compute_weekly_counts(todos: list[Todo]) -> pd.DataFrame:
    """Return a DataFrame with columns (week_label, completed) sorted by week."""
    rows = []
    for t in todos:
        if t.completed_at:
            rows.append({"completed_at": t.completed_at, "id": t.id})
    if not rows:
        return pd.DataFrame(columns=["week_label", "completed"])
    df = pd.DataFrame(rows)
    iso = pd.to_datetime(df["completed_at"]).dt.isocalendar()
    df["week_label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weekly = df.groupby("week_label")["id"].count().reset_index(name="completed")
    return weekly.sort_values("week_label")


def _compute_helper_load(todos: list[Todo]) -> pd.DataFrame:
    """Return a DataFrame with columns (helper, handoff) sorted desc."""
    rows = []
    for t in todos:
        helper = (t.helper or "").strip() or "(unassigned)"
        rows.append({"helper": helper, "id": t.id})
    if not rows:
        return pd.DataFrame(columns=["helper", "handoff"])
    df = pd.DataFrame(rows)
    counts = df.groupby("helper")["id"].count().reset_index(name="handoff")
    return counts.sort_values("handoff", ascending=False)


def render_analytics_page() -> None:
    """Render a compact dashboard with key metrics and one throughput chart."""
    st.subheader("Dashboard")

    today = date.today()

    this_mon, this_sun = week_bounds(today)
    last_mon = this_mon - timedelta(days=7)
    last_sun = this_mon - timedelta(days=1)

    open_count = _count_open_handoffs()
    done_this_week = _completed_in_range(this_mon, this_sun)
    done_last_week = _completed_in_range(last_mon, last_sun)

    done_recent = _completed_in_range(today - timedelta(days=28), today)
    cycle_stats = _compute_cycle_time_stats(done_recent)
    overdue_rate = _compute_overdue_rate(done_recent)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open handoffs", open_count)
    with col2:
        delta = len(done_this_week) - len(done_last_week)
        delta_str = f"{delta:+d} vs last week" if delta else "same as last week"
        st.metric("Done this week", len(done_this_week), delta=delta_str)
    with col3:
        if cycle_stats:
            _mean, median, _p90 = cycle_stats
            st.metric("Median cycle time", f"{median:.1f}d")
        else:
            st.metric("Median cycle time", "—")
    with col4:
        if overdue_rate is not None:
            st.metric("On-time rate", f"{(1 - overdue_rate) * 100:.0f}%")
        else:
            st.metric("On-time rate", "—")

    st.caption("Cycle time and on-time rate are based on the last 28 days.")

    st.markdown("---")

    done_8w = _completed_in_range(today - timedelta(weeks=8), today)
    if done_8w:
        st.markdown("#### Completed per week (last 8 weeks)")
        weekly = _compute_weekly_counts(done_8w)
        if not weekly.empty:
            st.bar_chart(weekly.set_index("week_label"))
    else:
        st.info("No completed todos in the last 8 weeks.")

    handoff_todos = query_todos(statuses=[TodoStatus.HANDOFF], include_archived=False)
    if handoff_todos:
        st.markdown("#### Current helper load")
        helper_counts = _compute_helper_load(handoff_todos)
        if not helper_counts.empty:
            st.bar_chart(helper_counts.set_index("helper"))
