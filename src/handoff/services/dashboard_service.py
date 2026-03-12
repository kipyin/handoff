"""Dashboard service — metrics, throughput, and export for the Dashboard page.

Orchestrates data access and business logic for dashboard analytics.
Pages call this service instead of data.py directly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime, time, timedelta
from typing import Any

import pandas as pd

from handoff.data import count_open_handoffs as _count_open_handoffs
from handoff.data import get_handoff_close_date, query_handoffs, query_risk_handoffs
from handoff.data import get_recent_activity as _get_recent_activity
from handoff.dates import week_bounds
from handoff.models import CheckIn, CheckInType, Handoff
from handoff.services.settings_service import get_deadline_near_days


def get_recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent activity log entries for the dashboard."""
    return _get_recent_activity(limit=limit)


def _project_name(handoff: Handoff) -> str:
    """Return display name for a handoff's project."""
    if handoff.project:
        return handoff.project.name
    return f"Project {handoff.project_id}"


def _pitchman_display(pitchman: str | None) -> str:
    """Return display string for pitchman, handling unassigned."""
    return (pitchman or "").strip() or "(unassigned)"


def _check_in_type(check_in: CheckIn) -> CheckInType | None:
    """Return a normalized check-in type for enum/string test doubles."""
    raw_type = getattr(check_in, "check_in_type", None)
    if isinstance(raw_type, CheckInType):
        return raw_type
    try:
        return CheckInType(raw_type)
    except (TypeError, ValueError):
        return None


def _normalize_sort_timestamp(created_at: datetime | None) -> datetime:
    """Return a timezone-neutral timestamp for deterministic sorting."""
    if created_at is None:
        return datetime.min
    if created_at.tzinfo is not None:
        return created_at.replace(tzinfo=None)
    return created_at


def _sorted_check_ins(handoff: Handoff) -> list[CheckIn]:
    """Return a handoff trail sorted by date, timestamp, and id."""
    check_ins = getattr(handoff, "check_ins", []) or []
    return sorted(
        check_ins,
        key=lambda ci: (
            ci.check_in_date,
            _normalize_sort_timestamp(getattr(ci, "created_at", None)),
            getattr(ci, "id", 0) or 0,
        ),
    )


def _iter_close_events(
    handoffs: list[Handoff],
    *,
    start: date,
    end: date,
) -> list[dict[str, Any]]:
    """Return close events between dates with reopened/on-time/cycle metadata."""
    events: list[dict[str, Any]] = []
    for handoff in handoffs:
        check_ins = _sorted_check_ins(handoff)
        for idx, check_in in enumerate(check_ins):
            if _check_in_type(check_in) != CheckInType.CONCLUDED:
                continue
            close_date = check_in.check_in_date
            if close_date < start or close_date > end:
                continue
            reopened = any(
                _check_in_type(next_check_in) in {CheckInType.ON_TRACK, CheckInType.DELAYED}
                for next_check_in in check_ins[idx + 1 :]
            )
            on_time = (
                close_date <= handoff.deadline
                if getattr(handoff, "deadline", None) is not None
                else None
            )
            cycle_days = None
            created_at = getattr(handoff, "created_at", None)
            if created_at is not None:
                cycle_days = max(
                    (
                        datetime.combine(close_date, time.min) - created_at.replace(tzinfo=None)
                    ).total_seconds()
                    / 86400,
                    0.0,
                )
            iso = close_date.isocalendar()
            events.append(
                {
                    "week_label": f"{iso[0]}-W{iso[1]:02d}",
                    "on_time": on_time,
                    "reopened": reopened,
                    "cycle_days": cycle_days,
                }
            )
    return events


def count_open_handoffs() -> int:
    """Return the number of currently open handoffs."""
    return _count_open_handoffs()


def completed_in_range(start: date, end: date) -> list[Handoff]:
    """Return handoffs concluded between *start* and *end* (inclusive)."""
    return query_handoffs(
        concluded_start=start,
        concluded_end=end,
        include_concluded=True,
        include_archived_projects=False,
    )


def compute_cycle_time_stats(handoffs: list[Handoff]) -> tuple[float, float, float] | None:
    """Return (mean, median, p90) cycle-time in days, or None if empty.

    Cycle time is created_at to close date (last concluded check-in).
    """
    days = []
    for h in handoffs:
        close = get_handoff_close_date(h)
        if h.created_at and close:
            delta = (
                datetime.combine(close, time.min) - h.created_at.replace(tzinfo=None)
            ).total_seconds() / 86400
            days.append(max(delta, 0))
    if not days:
        return None
    s = pd.Series(days)
    return float(s.mean()), float(s.median()), float(s.quantile(0.9))


def compute_overdue_rate(handoffs: list[Handoff]) -> float | None:
    """Fraction of concluded handoffs finished after their deadline.

    Only considers handoffs that have both a deadline and a close date.
    Returns None when no qualifying handoffs exist.
    """
    with_deadline = [h for h in handoffs if h.deadline and get_handoff_close_date(h)]
    if not with_deadline:
        return None
    overdue = sum(1 for h in with_deadline if get_handoff_close_date(h) > h.deadline)
    return overdue / len(with_deadline)


def compute_weekly_counts(handoffs: list[Handoff]) -> pd.DataFrame:
    """Return a DataFrame with columns (week_label, completed) sorted by week."""
    rows = []
    for h in handoffs:
        close = get_handoff_close_date(h)
        if close:
            rows.append({"close_date": close, "id": h.id})
    if not rows:
        return pd.DataFrame(columns=["week_label", "completed"])
    df = pd.DataFrame(rows)
    iso = pd.to_datetime(df["close_date"]).dt.isocalendar()
    df["week_label"] = iso["year"].astype(str) + "-W" + iso["week"].astype(str).str.zfill(2)
    weekly = df.groupby("week_label")["id"].count().reset_index(name="completed")
    return weekly.sort_values("week_label")


def compute_pitchman_load(handoffs: list[Handoff]) -> pd.DataFrame:
    """Return a DataFrame with columns (pitchman, handoff) sorted desc."""
    rows = []
    for h in handoffs:
        pitchman = _pitchman_display(h.pitchman)
        rows.append({"pitchman": pitchman, "id": h.id})
    if not rows:
        return pd.DataFrame(columns=["pitchman", "handoff"])
    df = pd.DataFrame(rows)
    counts = df.groupby("pitchman")["id"].count().reset_index(name="handoff")
    return counts.sort_values("handoff", ascending=False)


def compute_per_project_throughput(
    handoffs: list[Handoff], *, project_ids: list[int] | None = None
) -> pd.DataFrame:
    """Return concluded-per-week by project, filterable by project_ids."""
    rows = []
    for h in handoffs:
        close = get_handoff_close_date(h)
        if close and (project_ids is None or h.project_id in project_ids):
            proj = _project_name(h)
            iso = close.isocalendar()
            week_label = f"{iso[0]}-W{iso[1]:02d}"
            rows.append({"week_label": week_label, "project": proj, "id": h.id})
    if not rows:
        return pd.DataFrame(columns=["week_label", "project", "completed"])
    df = pd.DataFrame(rows)
    weekly = df.groupby(["week_label", "project"])["id"].count().reset_index(name="completed")
    return weekly.sort_values(["week_label", "project"])


def compute_per_pitchman_throughput(handoffs: list[Handoff], *, today: date) -> pd.DataFrame:
    """Return concluded-per-pitchman with trend (this week vs last week)."""
    if not handoffs:
        return pd.DataFrame(columns=["pitchman", "completed", "last_week", "trend"])
    this_mon, this_sun = week_bounds(today)
    last_mon = this_mon - timedelta(days=7)
    last_sun = this_mon - timedelta(days=1)

    def in_range(h: Handoff, start: date, end: date) -> bool:
        close = get_handoff_close_date(h)
        return close is not None and start <= close <= end

    this_week = [h for h in handoffs if in_range(h, this_mon, this_sun)]
    last_week = [h for h in handoffs if in_range(h, last_mon, last_sun)]

    def count_by_pitchman(items: list[Handoff]) -> dict[str, int]:
        out: dict[str, int] = {}
        for h in items:
            p = _pitchman_display(h.pitchman)
            out[p] = out.get(p, 0) + 1
        return out

    this_counts = count_by_pitchman(this_week)
    last_counts = count_by_pitchman(last_week)
    all_pitchmen = set(this_counts) | set(last_counts)

    rows = []
    for p in sorted(all_pitchmen, key=str.lower):
        tc = this_counts.get(p, 0)
        lc = last_counts.get(p, 0)
        if tc > lc:
            trend = "up"
        elif tc < lc:
            trend = "down"
        else:
            trend = "same"
        rows.append({"pitchman": p, "completed": tc, "last_week": lc, "trend": trend})
    df = pd.DataFrame(rows)
    return df.sort_values("completed", ascending=False)


def compute_cycle_time_by_project(handoffs: list[Handoff]) -> pd.DataFrame:
    """Return p50/p90 cycle time (days) per project."""
    by_project: dict[str, list[float]] = {}
    for h in handoffs:
        close = get_handoff_close_date(h)
        if h.created_at and close:
            delta = (
                datetime.combine(close, time.min) - h.created_at.replace(tzinfo=None)
            ).total_seconds() / 86400
            proj = _project_name(h)
            by_project.setdefault(proj, []).append(max(delta, 0))
    if not by_project:
        return pd.DataFrame(columns=["project", "p50_days", "p90_days", "closes"])
    rows = []
    for proj, days in by_project.items():
        s = pd.Series(days)
        rows.append(
            {
                "project": proj,
                "p50_days": float(s.quantile(0.5)),
                "p90_days": float(s.quantile(0.9)),
                "closes": len(days),
            }
        )
    df = pd.DataFrame(rows)
    return df.sort_values("p90_days", ascending=False)


def compute_open_aging_profile(handoffs: list[Handoff], *, today: date) -> pd.DataFrame:
    """Return bucketed open handoff aging counts."""
    if not handoffs:
        return pd.DataFrame(columns=["aging_bucket", "handoffs"])
    buckets = {"0-7d": 0, "8-14d": 0, "15-30d": 0, "31+d": 0}
    for handoff in handoffs:
        created_at = getattr(handoff, "created_at", None)
        if created_at is None:
            continue
        age_days = max((today - created_at.date()).days, 0)
        if age_days <= 7:
            buckets["0-7d"] += 1
        elif age_days <= 14:
            buckets["8-14d"] += 1
        elif age_days <= 30:
            buckets["15-30d"] += 1
        else:
            buckets["31+d"] += 1
    rows = [{"aging_bucket": bucket, "handoffs": count} for bucket, count in buckets.items()]
    return pd.DataFrame(rows)


@dataclass
class ReopenRateSummary:
    """Summary of how often concluded handoffs reopen in a time window."""

    reopened_closes: int
    total_closes: int

    @property
    def rate(self) -> float | None:
        """Return reopen fraction, or None when there are no closes."""
        if self.total_closes <= 0:
            return None
        return self.reopened_closes / self.total_closes

    @property
    def rate_display(self) -> str:
        """Return display-friendly percentage for dashboard cards."""
        if self.rate is None:
            return "—"
        return f"{self.rate * 100:.0f}%"

    @property
    def detail_display(self) -> str:
        """Return display-friendly reopen detail for dashboard cards."""
        if self.total_closes <= 0:
            return "No closes in window"
        return f"{self.reopened_closes} of {self.total_closes} closes reopened"


def compute_reopen_rate_summary(
    handoffs: list[Handoff],
    *,
    today: date,
    window_days: int = 90,
) -> ReopenRateSummary:
    """Return reopen-rate summary for concluded check-ins in the window."""
    start = today - timedelta(days=max(window_days, 1))
    events = _iter_close_events(handoffs, start=start, end=today)
    total_closes = len(events)
    reopened_closes = sum(1 for event in events if bool(event["reopened"]))
    return ReopenRateSummary(reopened_closes=reopened_closes, total_closes=total_closes)


def compute_on_time_close_rate_trend(
    handoffs: list[Handoff],
    *,
    today: date,
    weeks: int = 8,
) -> pd.DataFrame:
    """Return weekly on-time close trend for the requested window."""
    if weeks <= 0:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total", "on_time_rate_pct"])
    start = today - timedelta(weeks=max(weeks, 1))
    events = _iter_close_events(handoffs, start=start, end=today)
    by_week: dict[str, list[bool]] = {}
    for event in events:
        on_time = event["on_time"]
        if on_time is None:
            continue
        by_week.setdefault(event["week_label"], []).append(bool(on_time))
    if not by_week:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total", "on_time_rate_pct"])
    rows = []
    for week_label in sorted(by_week)[-weeks:]:
        values = by_week[week_label]
        rate = sum(1 for value in values if value) / len(values)
        rows.append(
            {
                "week_label": week_label,
                "on_time_rate": rate,
                "total": len(values),
                "on_time_rate_pct": f"{rate * 100:.0f}%",
            }
        )
    return pd.DataFrame(rows)


def compute_deadline_adherence_trend(handoffs: list[Handoff], weeks: int = 8) -> pd.DataFrame:
    """Compatibility wrapper that derives an effective 'today' from input data."""
    if weeks <= 0:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total"])
    close_dates = [get_handoff_close_date(handoff) for handoff in handoffs]
    close_dates = [close_date for close_date in close_dates if close_date is not None]
    if not close_dates:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total"])
    trend = compute_on_time_close_rate_trend(
        handoffs,
        today=max(close_dates),
        weeks=weeks,
    )
    if trend.empty:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total"])
    return trend[["week_label", "on_time_rate", "total"]]


@dataclass
class DashboardMetrics:
    """Core PM-operational metrics for the top row."""

    at_risk_now: int
    missed_check_in: int
    check_in_due_today: int
    open_handoffs: int
    reopen_rate: str
    reopen_rate_detail: str


def get_dashboard_metrics(today: date) -> DashboardMetrics:
    """Return PM-operations dashboard cards for current state."""
    reopen_window_days = 90
    reopen_window_start = today - timedelta(days=reopen_window_days)
    deadline_near_days = get_deadline_near_days()
    open_handoffs = query_handoffs(
        include_concluded=False,
        include_archived_projects=False,
    )
    at_risk_now = len(
        query_risk_handoffs(
            deadline_near_days=deadline_near_days,
            include_archived_projects=False,
        )
    )
    missed_check_in = sum(
        1
        for handoff in open_handoffs
        if handoff.next_check is not None and handoff.next_check < today
    )
    check_in_due_today = sum(
        1
        for handoff in open_handoffs
        if handoff.next_check is not None and handoff.next_check == today
    )
    analytics_handoffs = query_handoffs(
        include_concluded=True,
        include_archived_projects=False,
        concluded_start=reopen_window_start,
        concluded_end=today,
    )
    reopen_summary = compute_reopen_rate_summary(
        analytics_handoffs,
        today=today,
        window_days=reopen_window_days,
    )

    return DashboardMetrics(
        at_risk_now=at_risk_now,
        missed_check_in=missed_check_in,
        check_in_due_today=check_in_due_today,
        open_handoffs=len(open_handoffs),
        reopen_rate=reopen_summary.rate_display,
        reopen_rate_detail=reopen_summary.detail_display,
    )


def get_weekly_throughput(today: date, *, weeks: int = 8) -> pd.DataFrame:
    """Return concluded-per-week for the last N weeks."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    return compute_weekly_counts(done)


def get_per_project_throughput(
    today: date,
    *,
    weeks: int = 8,
    project_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return concluded-per-week by project for the last N weeks."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    return compute_per_project_throughput(done, project_ids=project_ids)


def get_per_pitchman_throughput(today: date, *, weeks: int = 8) -> pd.DataFrame:
    """Return per-pitchman throughput with trend (this week vs last week)."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    return compute_per_pitchman_throughput(done, today=today)


def get_cycle_time_by_project(
    today: date,
    *,
    days: int = 90,
    project_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return p50/p90 cycle time per project for the last N days."""
    done = completed_in_range(today - timedelta(days=days), today)
    if project_ids:
        done = [h for h in done if h.project_id in project_ids]
    return compute_cycle_time_by_project(done)


def get_open_aging_profile(today: date) -> pd.DataFrame:
    """Return current open-handoff aging buckets."""
    open_handoffs = query_handoffs(
        include_concluded=False,
        include_archived_projects=False,
    )
    return compute_open_aging_profile(open_handoffs, today=today)


def get_on_time_close_rate_trend(today: date, *, weeks: int = 8) -> pd.DataFrame:
    """Return weekly on-time close trend for recent concluded check-ins."""
    done = completed_in_range(today - timedelta(weeks=max(weeks, 1)), today)
    return compute_on_time_close_rate_trend(done, today=today, weeks=weeks)


def get_deadline_adherence_trend(
    today: date,
    *,
    weeks: int = 8,
    project_ids: list[int] | None = None,
) -> pd.DataFrame:
    """Return on-time rate per week over the last N weeks."""
    done = completed_in_range(today - timedelta(weeks=weeks), today)
    if project_ids:
        done = [h for h in done if h.project_id in project_ids]
    trend = compute_on_time_close_rate_trend(done, today=today, weeks=weeks)
    if trend.empty:
        return pd.DataFrame(columns=["week_label", "on_time_rate", "total"])
    return trend[["week_label", "on_time_rate", "total"]]


def get_pitchman_load() -> pd.DataFrame:
    """Return current open handoff count by pitchman."""
    handoffs = query_handoffs(include_concluded=False, include_archived_projects=False)
    return compute_pitchman_load(handoffs)


def _build_export_rows(
    handoffs: list[Handoff],
    *,
    today: date,
    weeks: int = 12,
) -> list[dict[str, Any]]:
    """Return PM-focused weekly export rows (reliability + flow)."""
    if not handoffs:
        return []
    end = today
    start = end - timedelta(weeks=max(weeks, 1))
    events = _iter_close_events(handoffs, start=start, end=end)
    if not events:
        return []
    by_week: dict[str, list[dict[str, Any]]] = {}
    for event in events:
        by_week.setdefault(event["week_label"], []).append(event)

    rows: list[dict[str, Any]] = []
    for week_label in sorted(by_week)[-weeks:]:
        week_events = by_week[week_label]
        total_closes = len(week_events)
        on_time_events = [e for e in week_events if e["on_time"] is not None]
        on_time_rate = (
            sum(1 for event in on_time_events if bool(event["on_time"])) / len(on_time_events)
            if on_time_events
            else None
        )
        reopened_closes = sum(1 for event in week_events if bool(event["reopened"]))
        cycle_days = [
            event["cycle_days"] for event in week_events if event["cycle_days"] is not None
        ]
        cycle_series = pd.Series(cycle_days) if cycle_days else None
        p50_cycle_days = float(cycle_series.quantile(0.5)) if cycle_series is not None else None
        p90_cycle_days = float(cycle_series.quantile(0.9)) if cycle_series is not None else None
        rows.append(
            {
                "week_label": week_label,
                "closed": total_closes,
                "on_time_rate": on_time_rate,
                "reopen_rate": reopened_closes / total_closes if total_closes else None,
                "p50_cycle_days": p50_cycle_days,
                "p90_cycle_days": p90_cycle_days,
            }
        )
    return rows


def _week_label_for(handoff: Handoff) -> str | None:
    """Return ISO week label for a handoff's close date."""
    close = get_handoff_close_date(handoff)
    if not close:
        return None
    iso = close.isocalendar()
    return f"{iso[0]}-W{iso[1]:02d}"


def get_exportable_metrics(
    today: date,
    *,
    weeks: int = 12,
    project_ids: list[int] | None = None,
) -> dict[str, str]:
    """Return CSV and JSON strings for download buttons."""
    import json

    done = completed_in_range(today - timedelta(weeks=weeks), today)
    if project_ids:
        done = [h for h in done if h.project_id in project_ids]
    rows = _build_export_rows(done, today=today, weeks=weeks)
    if not rows:
        return {"csv": "", "json": ""}
    df = pd.DataFrame(rows)
    csv_str = df.to_csv(index=False)
    json_str = json.dumps(rows, indent=2)
    return {"csv": csv_str, "json": json_str}
