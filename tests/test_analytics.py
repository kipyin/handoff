"""Tests for dashboard/analytics page helpers."""

from __future__ import annotations

from datetime import date, datetime
from types import SimpleNamespace

from handoff.pages.analytics import (
    _compute_cycle_time_stats,
    _compute_helper_load,
    _compute_overdue_rate,
    _compute_weekly_counts,
    _week_bounds,
)


def _make_todo(
    id: int = 1,
    helper: str | None = None,
    deadline: date | None = None,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        helper=helper,
        deadline=deadline,
        created_at=created_at or datetime(2026, 1, 1),
        completed_at=completed_at,
    )


# --- _week_bounds ---


def test_week_bounds_returns_monday_to_sunday() -> None:
    """_week_bounds returns the ISO week for the given date."""
    mon, sun = _week_bounds(date(2026, 2, 27))  # Friday
    assert mon == date(2026, 2, 23)  # Monday
    assert sun == date(2026, 3, 1)  # Sunday


def test_week_bounds_on_monday() -> None:
    mon, sun = _week_bounds(date(2026, 3, 2))  # Monday
    assert mon == date(2026, 3, 2)
    assert sun == date(2026, 3, 8)


def test_week_bounds_on_sunday() -> None:
    mon, sun = _week_bounds(date(2026, 3, 8))  # Sunday
    assert mon == date(2026, 3, 2)
    assert sun == date(2026, 3, 8)


# --- _compute_cycle_time_stats ---


def test_cycle_time_stats_returns_mean_median_p90() -> None:
    todos = [
        _make_todo(created_at=datetime(2026, 1, 8), completed_at=datetime(2026, 1, 10)),
        _make_todo(created_at=datetime(2026, 1, 9), completed_at=datetime(2026, 1, 10)),
        _make_todo(created_at=datetime(2026, 1, 7), completed_at=datetime(2026, 1, 10)),
        _make_todo(created_at=datetime(2026, 1, 5), completed_at=datetime(2026, 1, 10)),
    ]
    result = _compute_cycle_time_stats(todos)
    assert result is not None
    avg, p50, p90 = result
    assert avg == 2.75
    assert p50 == 2.5
    assert 3.0 <= p90 <= 5.0


def test_cycle_time_stats_returns_none_when_empty() -> None:
    assert _compute_cycle_time_stats([]) is None


def test_cycle_time_stats_skips_missing_completed_at() -> None:
    todos = [_make_todo(completed_at=None)]
    assert _compute_cycle_time_stats(todos) is None


# --- _compute_overdue_rate ---


def test_overdue_rate_all_on_time() -> None:
    todos = [
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 9)),
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 10)),
    ]
    assert _compute_overdue_rate(todos) == 0.0


def test_overdue_rate_half_overdue() -> None:
    todos = [
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 10)),
        _make_todo(deadline=date(2026, 1, 10), completed_at=datetime(2026, 1, 12)),
    ]
    assert _compute_overdue_rate(todos) == 0.5


def test_overdue_rate_none_when_no_deadlines() -> None:
    todos = [_make_todo(completed_at=datetime(2026, 1, 10))]
    assert _compute_overdue_rate(todos) is None


def test_overdue_rate_none_when_empty() -> None:
    assert _compute_overdue_rate([]) is None


# --- _compute_weekly_counts ---


def test_weekly_counts_aggregates_by_week() -> None:
    todos = [
        _make_todo(id=1, completed_at=datetime(2026, 1, 6)),
        _make_todo(id=2, completed_at=datetime(2026, 1, 7)),
        _make_todo(id=3, completed_at=datetime(2026, 1, 14)),
    ]
    result = _compute_weekly_counts(todos)
    assert "week_label" in result.columns
    assert "completed" in result.columns
    assert len(result) == 2
    assert list(result["completed"]) == [2, 1]
    assert result["week_label"].is_monotonic_increasing


def test_weekly_counts_empty_input() -> None:
    result = _compute_weekly_counts([])
    assert result.empty


# --- _compute_helper_load ---


def test_helper_load_aggregates_and_sorts() -> None:
    todos = [
        _make_todo(id=1, helper="Alice"),
        _make_todo(id=2, helper="Alice"),
        _make_todo(id=3, helper="Bob"),
        _make_todo(id=4, helper=None),
    ]
    result = _compute_helper_load(todos)
    assert set(result["helper"]) == {"Alice", "Bob", "(unassigned)"}
    counts = result.set_index("helper")["handoff"]
    assert counts["Alice"] == 2
    assert counts["Bob"] == 1
    assert counts["(unassigned)"] == 1
    assert result.iloc[0]["helper"] == "Alice"


def test_helper_load_empty_input() -> None:
    result = _compute_helper_load([])
    assert result.empty


# --- _count_open_handoffs and _completed_in_range are thin wrappers
# around query_todos; covered by the AppTest integration test.
