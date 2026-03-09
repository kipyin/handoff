"""Tests for dashboard service helpers."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

import pytest

from handoff.dates import week_bounds
from handoff.models import CheckInType
from handoff.services.dashboard_service import (
    compute_cycle_time_by_project,
    compute_cycle_time_stats,
    compute_deadline_adherence_trend,
    compute_overdue_rate,
    compute_per_pitchman_throughput,
    compute_per_project_throughput,
    compute_pitchman_load,
    compute_weekly_counts,
    get_cycle_time_by_project,
    get_dashboard_metrics,
    get_deadline_adherence_trend,
    get_exportable_metrics,
    get_per_pitchman_throughput,
    get_per_project_throughput,
    get_pitchman_load,
    get_weekly_throughput,
)


def _make_check_in(check_in_date: date, check_in_type: str = "concluded"):
    return SimpleNamespace(
        check_in_date=check_in_date,
        check_in_type=CheckInType(check_in_type),
    )


def _make_handoff(
    id: int = 1,
    pitchman: str | None = None,
    deadline: date | None = None,
    created_at: datetime | None = None,
    close_date: date | None = None,
    project_id: int = 1,
    project_name: str | None = "Project",
) -> SimpleNamespace:
    proj = SimpleNamespace(name=project_name) if project_name else None
    check_ins = []
    if close_date:
        check_ins.append(_make_check_in(close_date, "concluded"))
    return SimpleNamespace(
        id=id,
        pitchman=pitchman,
        deadline=deadline,
        created_at=created_at or datetime(2026, 1, 1),
        project_id=project_id,
        project=proj,
        check_ins=check_ins,
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
    handoffs = [
        _make_handoff(created_at=datetime(2026, 1, 8), close_date=date(2026, 1, 10)),
        _make_handoff(created_at=datetime(2026, 1, 9), close_date=date(2026, 1, 10)),
        _make_handoff(created_at=datetime(2026, 1, 7), close_date=date(2026, 1, 10)),
        _make_handoff(created_at=datetime(2026, 1, 5), close_date=date(2026, 1, 10)),
    ]
    result = compute_cycle_time_stats(handoffs)
    assert result is not None
    avg, p50, p90 = result
    assert avg == 2.75
    assert p50 == 2.5
    assert 3.0 <= p90 <= 5.0


def test_cycle_time_stats_returns_none_when_empty() -> None:
    assert compute_cycle_time_stats([]) is None


def test_cycle_time_stats_skips_missing_close_date() -> None:
    handoffs = [_make_handoff(close_date=None)]
    assert compute_cycle_time_stats(handoffs) is None


# --- compute_overdue_rate ---


def test_overdue_rate_all_on_time() -> None:
    handoffs = [
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 9)),
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 10)),
    ]
    assert compute_overdue_rate(handoffs) == 0.0


def test_overdue_rate_half_overdue() -> None:
    handoffs = [
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 10)),
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 12)),
    ]
    assert compute_overdue_rate(handoffs) == 0.5


def test_overdue_rate_none_when_no_deadlines() -> None:
    handoffs = [_make_handoff(close_date=date(2026, 1, 10))]
    assert compute_overdue_rate(handoffs) is None


def test_overdue_rate_none_when_empty() -> None:
    assert compute_overdue_rate([]) is None


# --- compute_weekly_counts ---


def test_weekly_counts_aggregates_by_week() -> None:
    handoffs = [
        _make_handoff(id=1, close_date=date(2026, 1, 6)),
        _make_handoff(id=2, close_date=date(2026, 1, 7)),
        _make_handoff(id=3, close_date=date(2026, 1, 14)),
    ]
    result = compute_weekly_counts(handoffs)
    assert "week_label" in result.columns
    assert "completed" in result.columns
    assert len(result) == 2
    assert list(result["completed"]) == [2, 1]
    assert result["week_label"].is_monotonic_increasing


def test_weekly_counts_empty_input() -> None:
    result = compute_weekly_counts([])
    assert result.empty


# --- compute_pitchman_load ---


def test_pitchman_load_aggregates_and_sorts() -> None:
    handoffs = [
        _make_handoff(id=1, pitchman="Alice"),
        _make_handoff(id=2, pitchman="Alice"),
        _make_handoff(id=3, pitchman="Bob"),
        _make_handoff(id=4, pitchman=None),
    ]
    result = compute_pitchman_load(handoffs)
    assert set(result["pitchman"]) == {"Alice", "Bob", "(unassigned)"}
    counts = result.set_index("pitchman")["handoff"]
    assert counts["Alice"] == 2
    assert counts["Bob"] == 1
    assert counts["(unassigned)"] == 1
    assert result.iloc[0]["pitchman"] == "Alice"


def test_pitchman_load_empty_input() -> None:
    result = compute_pitchman_load([])
    assert result.empty


# --- compute_per_project_throughput ---


def test_per_project_throughput_aggregates_by_week_and_project() -> None:
    handoffs = [
        _make_handoff(
            id=1,
            project_id=1,
            project_name="Alpha",
            close_date=date(2026, 1, 6),
        ),
        _make_handoff(
            id=2,
            project_id=1,
            project_name="Alpha",
            close_date=date(2026, 1, 7),
        ),
        _make_handoff(
            id=3,
            project_id=2,
            project_name="Beta",
            close_date=date(2026, 1, 14),
        ),
    ]
    result = compute_per_project_throughput(handoffs)
    assert "week_label" in result.columns
    assert "project" in result.columns
    assert "completed" in result.columns
    alpha_w02 = result[(result["week_label"] == "2026-W02") & (result["project"] == "Alpha")]
    beta_w03 = result[(result["week_label"] == "2026-W03") & (result["project"] == "Beta")]
    assert len(alpha_w02) == 1
    assert alpha_w02.iloc[0]["completed"] == 2
    assert len(beta_w03) == 1
    assert beta_w03.iloc[0]["completed"] == 1


def test_per_project_throughput_filters_by_project_ids() -> None:
    handoffs = [
        _make_handoff(id=1, project_id=1, project_name="A", close_date=date(2026, 1, 6)),
        _make_handoff(id=2, project_id=2, project_name="B", close_date=date(2026, 1, 6)),
        _make_handoff(id=3, project_id=3, project_name="C", close_date=date(2026, 1, 6)),
    ]
    result = compute_per_project_throughput(handoffs, project_ids=[1, 3])
    assert set(result["project"]) == {"A", "C"}
    assert "B" not in result["project"].values


def test_per_project_throughput_empty_input() -> None:
    result = compute_per_project_throughput([])
    assert result.empty
    assert list(result.columns) == ["week_label", "project", "completed"]


# --- compute_per_pitchman_throughput ---


def test_per_pitchman_throughput_shows_trend_up_down_same() -> None:
    today = date(2026, 3, 5)
    handoffs = [
        _make_handoff(pitchman="Alice", close_date=date(2026, 3, 4)),
        _make_handoff(pitchman="Alice", close_date=date(2026, 3, 5)),
        _make_handoff(pitchman="Bob", close_date=date(2026, 2, 25)),
        _make_handoff(pitchman="Carol", close_date=date(2026, 3, 3)),
        _make_handoff(pitchman="Carol", close_date=date(2026, 2, 26)),
    ]
    result = compute_per_pitchman_throughput(handoffs, today=today)
    assert "pitchman" in result.columns
    assert "completed" in result.columns
    assert "last_week" in result.columns
    assert "trend" in result.columns
    alice = result[result["pitchman"] == "Alice"].iloc[0]
    assert alice["completed"] == 2
    assert alice["last_week"] == 0
    assert alice["trend"] == "up"
    bob = result[result["pitchman"] == "Bob"].iloc[0]
    assert bob["trend"] == "down"
    carol = result[result["pitchman"] == "Carol"].iloc[0]
    assert carol["trend"] == "same"


def test_per_pitchman_throughput_empty_input() -> None:
    result = compute_per_pitchman_throughput([], today=date(2026, 3, 5))
    assert result.empty


# --- compute_cycle_time_by_project ---


def test_cycle_time_by_project_aggregates_and_sorts_slowest_first() -> None:
    handoffs = [
        _make_handoff(
            project_name="Slow",
            project_id=1,
            created_at=datetime(2026, 1, 1),
            close_date=date(2026, 1, 10),
        ),
        _make_handoff(
            project_name="Slow",
            project_id=1,
            created_at=datetime(2026, 1, 5),
            close_date=date(2026, 1, 11),
        ),
        _make_handoff(
            project_name="Fast",
            project_id=2,
            created_at=datetime(2026, 1, 1),
            close_date=date(2026, 1, 2),
        ),
    ]
    result = compute_cycle_time_by_project(handoffs)
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
    handoffs = [
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 8)),
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 12)),
        _make_handoff(deadline=date(2026, 1, 17), close_date=date(2026, 1, 15)),
        _make_handoff(deadline=date(2026, 1, 24), close_date=date(2026, 1, 25)),
    ]
    result = compute_deadline_adherence_trend(handoffs, weeks=2)
    assert len(result) == 2
    assert "week_label" in result.columns
    assert "on_time_rate" in result.columns


def test_deadline_adherence_trend_weeks_zero_returns_empty() -> None:
    handoffs = [
        _make_handoff(deadline=date(2026, 1, 10), close_date=date(2026, 1, 8)),
    ]
    result = compute_deadline_adherence_trend(handoffs, weeks=0)
    assert result.empty
    assert list(result.columns) == ["week_label", "on_time_rate", "total"]


def test_deadline_adherence_trend_empty_input() -> None:
    result = compute_deadline_adherence_trend([], weeks=8)
    assert result.empty


# --- get_* functions (with mocked data layer) ---


def test_get_dashboard_metrics(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 5)
    done_this_week = [
        _make_handoff(close_date=date(2026, 3, 4)),
        _make_handoff(close_date=date(2026, 3, 5)),
    ]
    done_last_week = [_make_handoff(close_date=date(2026, 2, 26))]
    done_recent = done_this_week + [
        _make_handoff(
            created_at=datetime(2026, 2, 20),
            close_date=date(2026, 2, 25),
            deadline=date(2026, 2, 24),
        ),
    ]

    monkeypatch.setattr(
        "handoff.services.dashboard_service.count_open_handoffs",
        lambda: 0,
    )

    def fake_completed(start, end):
        if start <= date(2026, 3, 2) and end >= date(2026, 3, 8):
            return done_this_week
        if start <= date(2026, 2, 24) and end >= date(2026, 3, 1):
            return done_last_week
        if start <= date(2026, 2, 6) and end >= date(2026, 3, 5):
            return done_recent
        return []

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
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
        _make_handoff(id=1, close_date=date(2026, 2, 10)),
        _make_handoff(id=2, close_date=date(2026, 2, 11)),
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
        _make_handoff(id=1, project_id=1, project_name="A", close_date=date(2026, 2, 10)),
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


def test_get_per_pitchman_throughput(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_handoff(pitchman="Alice", close_date=date(2026, 3, 5)),
    ]

    def fake_completed(start, end):
        return done

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed,
    )
    result = get_per_pitchman_throughput(today, weeks=8)
    assert "pitchman" in result.columns
    assert "completed" in result.columns
    assert "trend" in result.columns


def test_get_cycle_time_by_project(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_handoff(
            project_id=1,
            project_name="P",
            created_at=datetime(2026, 2, 1),
            close_date=date(2026, 2, 5),
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
        _make_handoff(deadline=date(2026, 2, 10), close_date=date(2026, 2, 9)),
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


def test_get_pitchman_load(monkeypatch: pytest.MonkeyPatch) -> None:
    handoffs = [
        _make_handoff(pitchman="Alice"),
        _make_handoff(pitchman="Alice"),
    ]

    monkeypatch.setattr(
        "handoff.services.dashboard_service.query_handoffs",
        lambda **kwargs: handoffs,
    )
    result = get_pitchman_load()
    assert "pitchman" in result.columns
    assert "handoff" in result.columns
    assert result["handoff"].sum() == 2


def test_get_exportable_metrics_with_data(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_handoff(
            id=1,
            project_id=1,
            project_name="P",
            close_date=date(2026, 2, 10),
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
