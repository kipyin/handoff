"""Tests for dashboard service helpers."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from handoff.dates import week_bounds
from handoff.services.dashboard_service import (
    compute_cycle_time_by_project,
    compute_cycle_time_stats,
    compute_deadline_adherence_trend,
    compute_helper_load,
    compute_overdue_rate,
    compute_per_helper_throughput,
    compute_per_project_throughput,
    compute_weekly_counts,
    get_cycle_time_by_project,
    get_dashboard_metrics,
    get_deadline_adherence_trend,
    get_exportable_metrics,
    get_helper_load,
    get_per_helper_throughput,
    get_per_project_throughput,
    get_weekly_throughput,
)


def _make_todo(
    id: int = 1,
    helper: str | None = None,
    deadline: date | None = None,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
    project_id: int = 1,
    project_name: str | None = "Project",
) -> SimpleNamespace:
    proj = SimpleNamespace(name=project_name) if project_name else None
    return SimpleNamespace(
        id=id,
        helper=helper,
        deadline=deadline,
        created_at=created_at or datetime(2026, 1, 1),
        completed_at=completed_at,
        project_id=project_id,
        project=proj,
    )


# --- week_bounds (shared helper, imported from handoff.dates) ---


def test_week_bounds_returns_monday_to_sunday() -> None:
    mon, sun = week_bounds(date(2026, 2, 27))  # Friday
    assert mon == date(2026, 2, 23)
    assert sun == date(2026, 3, 1)


def test_week_bounds_on_monday() -> None:
    mon, sun = week_bounds(date(2026, 3, 2))
    assert mon == date(2026, 3, 2)
    assert sun == date(2026, 3, 8)


def test_week_bounds_on_sunday() -> None:
    mon, sun = week_bounds(date(2026, 3, 8))
    assert mon == date(2026, 3, 2)
    assert sun == date(2026, 3, 8)


# --- compute_cycle_time_stats ---


def test_cycle_time_stats_returns_mean_median_p90() -> None:
    todos = [
        _make_todo(created_at=datetime(2026, 1, 8), completed_at=datetime(2026, 1, 10)),
        _make_todo(created_at=datetime(2026, 1, 9), completed_at=datetime(2026, 1, 10)),
        _make_todo(created_at=datetime(2026, 1, 7), completed_at=datetime(2026, 1, 10)),
        _make_todo(created_at=datetime(2026, 1, 5), completed_at=datetime(2026, 1, 10)),
    ]
    result = compute_cycle_time_stats(todos)
    assert result is not None
    avg, p50, p90 = result
    assert avg == 2.75
    assert p50 == 2.5
    assert 3.0 <= p90 <= 5.0


def test_cycle_time_stats_returns_none_when_empty() -> None:
    assert compute_cycle_time_stats([]) is None


def test_cycle_time_stats_skips_missing_completed_at() -> None:
    todos = [_make_todo(completed_at=None)]
    assert compute_cycle_time_stats(todos) is None


# --- compute_overdue_rate ---


def test_overdue_rate_all_on_time() -> None:
    todos = [
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 9)),
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 10)),
    ]
    assert compute_overdue_rate(todos) == 0.0


def test_overdue_rate_half_overdue() -> None:
    todos = [
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 10)),
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 12)),
    ]
    assert compute_overdue_rate(todos) == 0.5


def test_overdue_rate_none_when_no_deadlines() -> None:
    todos = [_make_todo(completed_at=datetime(2026, 1, 10))]
    assert compute_overdue_rate(todos) is None


def test_overdue_rate_none_when_empty() -> None:
    assert compute_overdue_rate([]) is None


# --- compute_weekly_counts ---


def test_weekly_counts_aggregates_by_week() -> None:
    todos = [
        _make_todo(id=1, completed_at=datetime(2026, 1, 6)),
        _make_todo(id=2, completed_at=datetime(2026, 1, 7)),
        _make_todo(id=3, completed_at=datetime(2026, 1, 14)),
    ]
    result = compute_weekly_counts(todos)
    assert "week_label" in result.columns
    assert "completed" in result.columns
    assert len(result) == 2
    assert list(result["completed"]) == [2, 1]
    assert result["week_label"].is_monotonic_increasing


def test_weekly_counts_empty_input() -> None:
    result = compute_weekly_counts([])
    assert result.empty


# --- compute_helper_load ---


def test_helper_load_aggregates_and_sorts() -> None:
    todos = [
        _make_todo(id=1, helper="Alice"),
        _make_todo(id=2, helper="Alice"),
        _make_todo(id=3, helper="Bob"),
        _make_todo(id=4, helper=None),
    ]
    result = compute_helper_load(todos)
    assert set(result["helper"]) == {"Alice", "Bob", "(unassigned)"}
    counts = result.set_index("helper")["handoff"]
    assert counts["Alice"] == 2
    assert counts["Bob"] == 1
    assert counts["(unassigned)"] == 1
    assert result.iloc[0]["helper"] == "Alice"


def test_helper_load_empty_input() -> None:
    result = compute_helper_load([])
    assert result.empty


# --- compute_per_project_throughput ---


def test_per_project_throughput_aggregates_by_week_and_project() -> None:
    todos = [
        _make_todo(
            id=1,
            project_id=1,
            project_name="Alpha",
            completed_at=datetime(2026, 1, 6),
        ),
        _make_todo(
            id=2,
            project_id=1,
            project_name="Alpha",
            completed_at=datetime(2026, 1, 7),
        ),
        _make_todo(
            id=3,
            project_id=2,
            project_name="Beta",
            completed_at=datetime(2026, 1, 14),
        ),
    ]
    result = compute_per_project_throughput(todos)
    assert "week_label" in result.columns
    assert "project" in result.columns
    assert "completed" in result.columns
    # Jan 6-7 are in 2026-W02, Jan 14 is in 2026-W03
    alpha_w02 = result[(result["week_label"] == "2026-W02") & (result["project"] == "Alpha")]
    beta_w03 = result[(result["week_label"] == "2026-W03") & (result["project"] == "Beta")]
    assert len(alpha_w02) == 1
    assert alpha_w02.iloc[0]["completed"] == 2
    assert len(beta_w03) == 1
    assert beta_w03.iloc[0]["completed"] == 1


def test_per_project_throughput_filters_by_project_ids() -> None:
    todos = [
        _make_todo(id=1, project_id=1, project_name="A", completed_at=datetime(2026, 1, 6)),
        _make_todo(id=2, project_id=2, project_name="B", completed_at=datetime(2026, 1, 6)),
        _make_todo(id=3, project_id=3, project_name="C", completed_at=datetime(2026, 1, 6)),
    ]
    result = compute_per_project_throughput(todos, project_ids=[1, 3])
    assert set(result["project"]) == {"A", "C"}
    assert "B" not in result["project"].values


def test_per_project_throughput_empty_input() -> None:
    result = compute_per_project_throughput([])
    assert result.empty
    assert list(result.columns) == ["week_label", "project", "completed"]


# --- compute_per_helper_throughput ---


def test_per_helper_throughput_shows_trend_up_down_same() -> None:
    # Week of 2026-03-02: Mon 2nd - Sun 8th
    # This week: March 3–8; Last week: Feb 24 – March 1
    today = date(2026, 3, 5)  # Thursday in that week
    todos = [
        _make_todo(helper="Alice", completed_at=datetime(2026, 3, 4)),  # this week
        _make_todo(helper="Alice", completed_at=datetime(2026, 3, 5)),  # this week
        _make_todo(helper="Bob", completed_at=datetime(2026, 2, 25)),  # last week only
        _make_todo(helper="Carol", completed_at=datetime(2026, 3, 3)),  # this week
        _make_todo(helper="Carol", completed_at=datetime(2026, 2, 26)),  # last week
    ]
    result = compute_per_helper_throughput(todos, today=today)
    assert "helper" in result.columns
    assert "completed" in result.columns
    assert "last_week" in result.columns
    assert "trend" in result.columns
    alice = result[result["helper"] == "Alice"].iloc[0]
    assert alice["completed"] == 2
    assert alice["last_week"] == 0
    assert alice["trend"] == "up"
    bob = result[result["helper"] == "Bob"].iloc[0]
    assert bob["trend"] == "down"
    carol = result[result["helper"] == "Carol"].iloc[0]
    assert carol["trend"] == "same"


def test_per_helper_throughput_empty_input() -> None:
    result = compute_per_helper_throughput([], today=date(2026, 3, 5))
    assert result.empty


# --- compute_cycle_time_by_project ---


def test_cycle_time_by_project_aggregates_and_sorts_slowest_first() -> None:
    todos = [
        _make_todo(
            project_name="Slow",
            project_id=1,
            created_at=datetime(2026, 1, 1),
            completed_at=datetime(2026, 1, 10),
        ),
        _make_todo(
            project_name="Slow",
            project_id=1,
            created_at=datetime(2026, 1, 5),
            completed_at=datetime(2026, 1, 11),
        ),
        _make_todo(
            project_name="Fast",
            project_id=2,
            created_at=datetime(2026, 1, 1),
            completed_at=datetime(2026, 1, 2),
        ),
    ]
    result = compute_cycle_time_by_project(todos)
    assert "project" in result.columns
    assert "median_days" in result.columns
    assert "count" in result.columns
    assert result.iloc[0]["project"] == "Slow"
    assert result.iloc[1]["project"] == "Fast"
    assert result.iloc[0]["median_days"] == 7.5
    assert result.iloc[0]["count"] == 2


def test_cycle_time_by_project_empty_input() -> None:
    result = compute_cycle_time_by_project([])
    assert result.empty


# --- compute_deadline_adherence_trend ---


def test_deadline_adherence_trend_weeks_limit() -> None:
    todos = [
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 8)),
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 12)),
        _make_todo(deadline=date(2026, 1, 17), completed_at=datetime(2026, 1, 15)),
        _make_todo(deadline=date(2026, 1, 24), completed_at=datetime(2026, 1, 25)),
    ]
    result = compute_deadline_adherence_trend(todos, weeks=2)
    assert len(result) == 2
    assert "week_label" in result.columns
    assert "on_time_rate" in result.columns


def test_deadline_adherence_trend_weeks_zero_returns_empty() -> None:
    todos = [
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 8)),
    ]
    result = compute_deadline_adherence_trend(todos, weeks=0)
    assert result.empty
    assert list(result.columns) == ["week_label", "on_time_rate", "total"]


def test_deadline_adherence_trend_empty_input() -> None:
    result = compute_deadline_adherence_trend([], weeks=8)
    assert result.empty


# --- get_* functions (with mocked data layer) ---


def test_get_dashboard_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 5)
    done_this_week = [
        _make_todo(completed_at=datetime(2026, 3, 4)),
        _make_todo(completed_at=datetime(2026, 3, 5)),
    ]
    done_last_week = [_make_todo(completed_at=datetime(2026, 2, 26))]
    done_recent = done_this_week + [
        _make_todo(
            created_at=datetime(2026, 2, 20),
            completed_at=datetime(2026, 2, 25),
            deadline=date(2026, 2, 24),
        ),
    ]

    def fake_query(
        *, statuses=None, completed_start=None, completed_end=None, include_archived=False, **kwargs
    ):
        if statuses and any(s.value == "handoff" for s in statuses):
            return []
        if completed_start is not None and completed_end is not None:
            start_d = (
                completed_start.date() if hasattr(completed_start, "date") else completed_start
            )
            end_d = completed_end.date() if hasattr(completed_end, "date") else completed_end
            if start_d <= date(2026, 3, 2) and end_d >= date(2026, 3, 8):
                return done_this_week
            if start_d <= date(2026, 2, 24) and end_d >= date(2026, 3, 1):
                return done_last_week
            if start_d <= date(2026, 2, 6) and end_d >= date(2026, 3, 5):
                return done_recent
        return []

    monkeypatch.setattr(
        "handoff.services.dashboard_service.query_todos",
        fake_query,
    )
    metrics = get_dashboard_metrics(today)
    assert metrics.open_count == 0
    assert metrics.done_this_week == 2
    assert metrics.done_week_delta == "+1 vs last week"
    assert "d" in metrics.median_cycle_time or metrics.median_cycle_time == "—"
    assert "%" in metrics.on_time_rate or metrics.on_time_rate == "—"


def test_get_weekly_throughput(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_todo(id=1, completed_at=datetime(2026, 2, 10)),
        _make_todo(id=2, completed_at=datetime(2026, 2, 11)),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_weekly_throughput(today, weeks=8)
    assert "week_label" in result.columns
    assert "completed" in result.columns
    assert len(result) >= 1


def test_get_per_project_throughput(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_todo(id=1, project_id=1, project_name="A", completed_at=datetime(2026, 2, 10)),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_per_project_throughput(today, weeks=8)
    assert "week_label" in result.columns
    assert "project" in result.columns
    assert "completed" in result.columns


def test_get_per_helper_throughput(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_todo(helper="Alice", completed_at=datetime(2026, 3, 5)),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_per_helper_throughput(today, weeks=8)
    assert "helper" in result.columns
    assert "completed" in result.columns
    assert "trend" in result.columns


def test_get_cycle_time_by_project(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_todo(
            project_id=1,
            project_name="P",
            created_at=datetime(2026, 2, 1),
            completed_at=datetime(2026, 2, 5),
        ),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_cycle_time_by_project(today, days=28)
    assert "project" in result.columns
    assert "median_days" in result.columns


def test_get_deadline_adherence_trend(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_todo(deadline=date(2026, 2, 10), completed_at=datetime(2026, 2, 9)),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_deadline_adherence_trend(today, weeks=8)
    assert "week_label" in result.columns
    assert "on_time_rate" in result.columns


def test_get_helper_load(monkeypatch: pytest.MonkeyPatch) -> None:
    handoffs = [
        _make_todo(helper="Alice", completed_at=None),
        _make_todo(helper="Alice", completed_at=None),
    ]

    def fake_query(*, statuses, include_archived, **kwargs):
        if statuses and "handoff" in [s.value for s in statuses]:
            return handoffs
        return []

    monkeypatch.setattr(
        "handoff.services.dashboard_service.query_todos",
        fake_query,
    )
    result = get_helper_load()
    assert "helper" in result.columns
    assert "handoff" in result.columns
    assert result["handoff"].sum() == 2


def test_get_exportable_metrics_with_data(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_todo(
            id=1,
            project_id=1,
            project_name="P",
            completed_at=datetime(2026, 2, 10),
            created_at=datetime(2026, 2, 8),
            deadline=date(2026, 2, 12),
        ),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_exportable_metrics(today, weeks=12)
    assert "csv" in result
    assert "json" in result
    assert len(result["csv"]) > 0
    assert "week_label" in result["csv"] or "2026" in result["csv"]


def test_get_exportable_metrics_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)

    def fake_completed(start, end):
        return []

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_exportable_metrics(today, weeks=12)
    assert result["csv"] == ""
    assert result["json"] == ""
