"""Dashboard service — metrics, throughput, and export for the Dashboard page.

Orchestrates data access and business logic for dashboard analytics.
Pages call this service instead of data.py directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd

from handoff.data import get_recent_activity as _get_recent_activity
from handoff.data import query_todos
from handoff.dates import week_bounds
from handoff.models import Todo, TodoStatus


def get_recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent activity log entries for the dashboard.

    Delegates to data layer; kept in service so dashboard uses one entry point.
    """
    return _get_recent_activity(limit=limit)


def _project_name(todo: Todo) -> str:
    """Return display name for a todo's project."""
    if todo.project:
        return todo.project.name
    return f"Project {todo.project_id}"


def _helper_display(helper: str | None) -> str:
    """Return display string for helper, handling unassigned."""
    return (helper or "").strip() or "(unassigned)"


def count_open_handoffs() -> int:
    """Return the number of currently open (delegated) todos."""
    return len(query_todos(statuses=[TodoStatus.HANDOFF], include_archived=False))


def completed_in_range(start: date, end: date) -> list[Todo]:
    """Return todos completed between *start* and *end* (inclusive)."""
    return query_todos(
        statuses=[TodoStatus.DONE],
        completed_start=datetime.combine(start, time.min),
        completed_end=datetime.combine(end, time.max),
        include_archived=False,
    )


def compute_cycle_time_stats(todos: list[Todo]) -> tuple[float, float, float] | None:
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


def compute_overdue_rate(todos: list[Todo]) -> float | None:
    """Fraction of completed todos that were finished after their deadline.

    Only considers todos that have both a deadline and a completed_at.
    Returns None when no qualifying todos exist.
    """
    with_deadline = [t for t in todos if t.deadline and t.completed_at]
    if not with_deadline:
        return None
    overdue = sum(1 for t in with_deadline if t.completed_at.date() > t.deadline)
    return overdue / len(with_deadline)


def compute_weekly_counts(todos: list[Todo]) -> pd.DataFrame:
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


def compute_helper_load(todos: list[Todo]) -> pd.DataFrame:
    """Return a DataFrame with columns (helper, handoff) sorted desc."""
    rows = []
    for t in todos:
        helper = _helper_display(t.helper)
        rows.append({"helper": helper, "id": t.id})
    if not rows:
        return pd.DataFrame(columns=["helper", "handoff"])
    df = pd.DataFrame(rows)
    counts = df.groupby("helper")["id"].count().reset_index(name="handoff")
    return counts.sort_values("handoff", ascending=False)


# --- A6: Enhanced Dashboard Analytics ---


def compute_per_project_throughput(
    todos: list[Todo], *, project_ids: list[int] | None = None
) -> pd.DataFrame:
    """Return completed-per-week by project, filterable by project_ids.

    Columns: week_label, project, completed. Sorted by week then project.
    """
    rows = []
    for t in todos:
        if t.completed_at and (project_ids is None or t.project_id in project_ids):
            proj = _project_name(t)
            iso = t.completed_at.isocalendar()
            week_label = f"{iso[0]}-W{iso[1]:02d}"
            rows.append({"week_label": week_label, "project": proj, "id": t.id})
    if not rows:
        return pd.DataFrame(columns=["week_label", "project", "completed"])
    df = pd.DataFrame(rows)
    weekly = df.groupby(["week_label", "project"])["id"].count().reset_index(name="completed")
    return weekly.sort_values(["week_label", "project"])


def compute_per_helper_throughput(todos: list[Todo], *, today: date) -> pd.DataFrame:
    """Return completed-per-helper with trend (this week vs last week).

    Columns: helper, completed, last_week, trend (up/down/same).
    Sorted by completed desc.
    """
    if not todos:
        return pd.DataFrame(columns=["helper", "completed", "last_week", "trend"])
    this_mon, this_sun = week_bounds(today)
    last_mon = this_mon - timedelta(days=7)
    last_sun = this_mon - timedelta(days=1)

    def in_range(t: Todo, start: date, end: date) -> bool:
        if not t.completed_at:
            return False
        d = t.completed_at.date()
        return start <= d <= end

    this_week = [t for t in todos if in_range(t, this_mon, this_sun)]
    last_week = [t for t in todos if in_range(t, last_mon, last_sun)]

    def count_by_helper(items: list[Todo]) -> dict[str, int]:
        out: dict[str, int] = {}
        for t in items:
            h = _helper_display(t.helper)
            out[h] = out.get(h, 0) + 1
        return out

    this_counts = count_by_helper(this_week)
    last_counts = count_by_helper(last_week)
    all_helpers = set(this_counts) | set(last_counts)

    rows = []
    for h in sorted(all_helpers, key=str.lower):
        tc = this_counts.get(h, 0)
        lc = last_counts.get(h, 0)
        if tc > lc:
            trend = "up"
        elif tc < lc:
            trend = "down"
        else:
            trend = "same"
        rows.append({"helper": h, "completed": tc, "last_week": lc, "trend": trend})
    df = pd.DataFrame(rows)
    return df.sort_values("completed", ascending=False)


def compute_cycle_time_by_project(todos: list[Todo]) -> pd.DataFrame:
    """Return median cycle time (days) per project. Identifies slow-turnaround projects.

    Columns: project, median_days, count. Sorted by median_days desc (slowest first).
    """
    by_project: dict[str, list[float]] = {}
    for t in todos:
        if t.created_at and t.completed_at:
            delta = (t.completed_at - t.created_at).total_seconds() / 86400
            proj = _project_name(t)
            by_project.setdefault(proj, []).append(delta)
    if not by_project:
        return pd.DataFrame(columns=["project", "median_days", "count"])
    rows = []
    for proj, days in by_project.items():
        s = pd.Series(days)
        rows.append({"project": proj, "median_days": float(s.median()), "count": len(days)})
    df = pd.DataFrame(rows)
    return df.sort_values("median_days", ascending=False)


def compute_deadline_adherence_trend(todos: list[Todo], weeks: int = 8) -> pd.DataFrame:
    """Return on-time rate per week over time.

    The weeks parameter limits the result to the most recent N ISO weeks present
    in the data. Columns: week_label, on_time_rate, total. Sorted by week.
    """
    if weeks <= 0:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total"])
    with_deadline = [t for t in todos if t.deadline and t.completed_at]
    if not with_deadline:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total"])
    by_week: dict[str, list[bool]] = {}
    for t in with_deadline:
        iso = t.completed_at.date().isocalendar()
        week_label = f"{iso[0]}-W{iso[1]:02d}"
        on_time = t.completed_at.date() <= t.deadline
        by_week.setdefault(week_label, []).append(on_time)
    sorted_weeks = sorted(by_week)
    sorted_weeks = sorted_weeks[-weeks:]
    rows = []
    for week_label in sorted_weeks:
        vals = by_week[week_label]
        rate = sum(1 for v in vals if v) / len(vals)
        rows.append({"week_label": week_label, "on_time_rate": rate, "total": len(vals)})
    return pd.DataFrame(rows)


@dataclass
class DashboardMetrics:
    """Core dashboard metrics for the top row."""

    open_count: int
    done_this_week: int
    done_week_delta: str
    median_cycle_time: str
    on_time_rate: str


def get_dashboard_metrics(today: date) -> DashboardMetrics:
    """Return core metrics for the dashboard top row."""
    open_count = count_open_handoffs()
    this_mon, this_sun = week_bounds(today)
    last_mon = this_mon - timedelta(days=7)
    done_this_week = completed_in_range(this_mon, this_sun)
    done_last_week = completed_in_range(last_mon, this_mon - timedelta(days=1))
    delta = len(done_this_week) - len(done_last_week)
    done_week_delta = f"{delta:+d} vs last week" if delta else "same as last week"

    done_recent = completed_in_range(today - timedelta(days=28), today)
    cycle_stats = compute_cycle_time_stats(done_recent)
    overdue_rate = compute_overdue_rate(done_recent)
    median_cycle_time = f"{cycle_stats[1]:.1f}d" if cycle_stats else "—"
    on_time_rate = f"{(1 - overdue_rate) * 100:.0f}%" if overdue_rate is not None else "—"

    return DashboardMetrics(
        open_count=open_count,
        done_this_week=len(done_this_week),
        done_week_delta=done_week_delta,
        median_cycle_time=median_cycle_time,
        on_time_rate=on_time_rate,
    )


def get_weekly_throughput(today: date, *, weeks: int = 8) -> pd.DataFrame:
    """Return completed-per-week for the last N weeks."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    return compute_weekly_counts(done)


def get_per_project_throughput(
    today: date,
    *,
    weeks: int = 8,
    project_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return completed-per-week by project for the last N weeks."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    return compute_per_project_throughput(done, project_ids=project_ids)


def get_per_helper_throughput(today: date, *, weeks: int = 8) -> pd.DataFrame:
    """Return per-helper throughput with trend (this week vs last week)."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    return compute_per_helper_throughput(done, today=today)


def get_cycle_time_by_project(
    today: date,
    *,
    days: int = 28,
    project_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return median cycle time per project for the last N days."""
    done = completed_in_range(today - timedelta(days=days), today)
    if project_ids:
        done = [t for t in done if t.project_id in project_ids]
    return compute_cycle_time_by_project(done)


def get_deadline_adherence_trend(
    today: date,
    *,
    weeks: int = 8,
    project_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return on-time rate per week over the last N weeks."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    if project_ids:
        done = [t for t in done if t.project_id in project_ids]
    return compute_deadline_adherence_trend(done, weeks=weeks)


def get_helper_load() -> pd.DataFrame:
    """Return current open handoff count by helper."""
    handoffs = query_todos(statuses=[TodoStatus.HANDOFF], include_archived=False)
    return compute_helper_load(handoffs)


def _build_export_rows(todos: list[Todo], weeks: int = 12) -> list[dict[str, Any]]:
    """Return aggregated weekly stats for external reporting (CSV/JSON).

    Each dict has: week_label, completed, on_time_rate, median_cycle_days.
    """
    if not todos:
        return []
    weekly = compute_weekly_counts(todos)
    adherence = compute_deadline_adherence_trend(todos, weeks=weeks)
    adherence_by_week = adherence.set_index("week_label").to_dict("index")

    rows = []
    for _, row in weekly.iterrows():
        wl = row["week_label"]
        completed = int(row["completed"])
        week_todos = [t for t in todos if t.completed_at and _week_label(t.completed_at) == wl]
        cycle = compute_cycle_time_stats(week_todos)
        median_cycle = float(cycle[1]) if cycle else None
        adj = adherence_by_week.get(wl, {})
        on_time = adj.get("on_time_rate")
        rows.append(
            {
                "week_label": wl,
                "completed": completed,
                "on_time_rate": on_time,
                "median_cycle_days": median_cycle,
            }
        )
    return rows


def _week_label(dt: datetime) -> str:
    """Return ISO week label for a datetime."""
    iso = dt.date().isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def get_exportable_metrics(
    today: date,
    *,
    weeks: int = 12,
    project_ids: list[int] | None = None,
) -> dict[str, str]:
    """Return CSV and JSON strings for download buttons.

    Keys: "csv", "json". Empty strings when no data.
    """
    import json

    done = completed_in_range(today - timedelta(weeks=weeks), today)
    if project_ids:
        done = [t for t in done if t.project_id in project_ids]
    rows = _build_export_rows(done, weeks=weeks)
    if not rows:
        return {"csv": "", "json": ""}
    df = pd.DataFrame(rows)
    csv_str = df.to_csv(index=False)
    json_str = json.dumps(rows, indent=2)
    return {"csv": csv_str, "json": json_str}
