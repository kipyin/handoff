"""Regression tests for PR #179 restructuring coverage gaps.

This module adds critical coverage for business logic introduced during the
massive restructure in PR #179 (Release/2026.3.12). Focuses on:

1. dashboard_service.py compute functions (cycle time, overdue rate, trends)
2. Complex aggregations and edge cases in dashboard analytics
3. Critical data aggregation paths with timezone/deadline handling
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from types import SimpleNamespace

from handoff.core.models import CheckInType
from handoff.services.dashboard_service import (
    ReopenRateSummary,
    compute_cycle_time_by_project,
    compute_cycle_time_stats,
    compute_deadline_adherence_trend,
    compute_on_time_close_rate_trend,
    compute_open_aging_profile,
    compute_overdue_rate,
    compute_per_pitchman_throughput,
    compute_per_project_throughput,
    compute_pitchman_load,
    compute_reopen_rate_summary,
    compute_weekly_counts,
)


def _make_check_in(
    check_in_date: date,
    check_in_type: CheckInType,
    *,
    id: int = 1,
    note: str = "",
    created_at: datetime | None = None,
) -> SimpleNamespace:
    """Factory for test check-in objects."""
    return SimpleNamespace(
        id=id,
        check_in_date=check_in_date,
        check_in_type=check_in_type,
        created_at=created_at or datetime(2026, 1, 1, 0, 0, 0),
        note=note,
    )


def _make_handoff(
    *,
    id: int,
    created_at: datetime,
    deadline: date | None = None,
    pitchman: str | None = None,
    project_id: int = 1,
    project_name: str = "Test Project",
    check_ins: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    """Factory for test handoff objects."""
    return SimpleNamespace(
        id=id,
        project_id=project_id,
        project=SimpleNamespace(name=project_name),
        created_at=created_at,
        deadline=deadline,
        pitchman=pitchman,
        check_ins=list(check_ins or []),
    )


# =============================================================================
# Cycle Time Tests
# =============================================================================


def test_compute_cycle_time_stats_calculates_mean_median_p90() -> None:
    """compute_cycle_time_stats returns (mean, median, p90) for cycle days."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 21), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=3,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 6), CheckInType.CONCLUDED)],
        ),
    ]

    stats = compute_cycle_time_stats(handoffs)
    assert stats is not None
    mean, median, p90 = stats
    assert mean > 0
    assert median > 0
    assert p90 > 0
    assert median == 10.0  # middle value
    assert 10 <= mean <= 20  # reasonable range


def test_compute_cycle_time_stats_returns_none_for_empty_list() -> None:
    """compute_cycle_time_stats returns None when no closures exist."""
    stats = compute_cycle_time_stats([])
    assert stats is None


def test_compute_cycle_time_stats_ignores_handoffs_without_close_date() -> None:
    """compute_cycle_time_stats only uses handoffs with concluded check-ins."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 15), CheckInType.ON_TRACK)],
        ),
    ]

    stats = compute_cycle_time_stats(handoffs)
    assert stats is not None
    _mean, median, _p90 = stats
    assert median == 10.0  # only first handoff counted


def test_compute_cycle_time_stats_handles_timezone_aware_created_at() -> None:
    """compute_cycle_time_stats strips timezone when computing cycle days."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0, tzinfo=UTC),
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
    ]

    stats = compute_cycle_time_stats(handoffs)
    assert stats is not None
    _mean, median, _p90 = stats
    assert median == 10.0


def test_compute_cycle_time_stats_negative_delta_clamped_to_zero() -> None:
    """compute_cycle_time_stats clamps negative deltas to 0 (clock drift)."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 11, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 10), CheckInType.CONCLUDED)],
        ),
    ]

    stats = compute_cycle_time_stats(handoffs)
    assert stats is not None
    _mean, median, _p90 = stats
    assert median == 0.0


# =============================================================================
# Overdue Rate Tests
# =============================================================================


def test_compute_overdue_rate_with_mixed_on_time_and_overdue() -> None:
    """compute_overdue_rate counts fraction of handoffs past deadline."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            deadline=date(2026, 1, 10),
            check_ins=[_make_check_in(date(2026, 1, 9), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            deadline=date(2026, 1, 10),
            check_ins=[_make_check_in(date(2026, 1, 12), CheckInType.CONCLUDED)],
        ),
    ]

    rate = compute_overdue_rate(handoffs)
    assert rate == 0.5


def test_compute_overdue_rate_returns_none_when_no_deadlines() -> None:
    """compute_overdue_rate returns None when no handoffs have deadlines."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
    ]

    rate = compute_overdue_rate(handoffs)
    assert rate is None


def test_compute_overdue_rate_ignores_open_handoffs() -> None:
    """compute_overdue_rate only considers closed handoffs."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            deadline=date(2026, 1, 10),
            check_ins=[_make_check_in(date(2026, 1, 15), CheckInType.ON_TRACK)],
        ),
    ]

    rate = compute_overdue_rate(handoffs)
    assert rate is None


# =============================================================================
# Weekly Counts and Throughput Tests
# =============================================================================


def test_compute_weekly_counts_groups_by_iso_week() -> None:
    """compute_weekly_counts returns DataFrame with weekly completion counts."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 10), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 1, 17), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_weekly_counts(handoffs)
    assert len(df) == 2
    assert list(df.columns) == ["week_label", "completed"]
    assert df["completed"].sum() == 2


def test_compute_weekly_counts_returns_empty_df_for_no_closures() -> None:
    """compute_weekly_counts returns empty DataFrame when no handoffs closed."""
    df = compute_weekly_counts([])
    assert df.empty
    assert list(df.columns) == ["week_label", "completed"]


def test_compute_pitchman_load_aggregates_by_person() -> None:
    """compute_pitchman_load counts handoffs per pitchman."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            pitchman="Alice",
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            pitchman="Bob",
            check_ins=[_make_check_in(date(2026, 1, 12), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=3,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            pitchman="Alice",
            check_ins=[_make_check_in(date(2026, 1, 13), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_pitchman_load(handoffs)
    assert len(df) == 2
    assert list(df.columns) == ["pitchman", "handoff"]
    alice_row = df[df["pitchman"] == "Alice"]
    assert alice_row["handoff"].values[0] == 2


def test_compute_pitchman_load_displays_unassigned_for_none() -> None:
    """compute_pitchman_load shows '(unassigned)' for null pitchman."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            pitchman=None,
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_pitchman_load(handoffs)
    assert "(unassigned)" in df["pitchman"].values


# =============================================================================
# Project-Level Aggregations
# =============================================================================


def test_compute_cycle_time_by_project_returns_p50_p90_per_project() -> None:
    """compute_cycle_time_by_project returns quantile stats grouped by project."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_id=1,
            project_name="Project A",
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_id=1,
            project_name="Project A",
            check_ins=[_make_check_in(date(2026, 1, 21), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_cycle_time_by_project(handoffs)
    assert len(df) == 1
    assert list(df.columns) == ["project", "p50_days", "p90_days", "closes"]
    assert df["closes"].values[0] == 2


def test_compute_cycle_time_by_project_empty_returns_empty_df() -> None:
    """compute_cycle_time_by_project returns empty DataFrame for no closures."""
    df = compute_cycle_time_by_project([])
    assert df.empty


def test_compute_per_project_throughput_filters_by_project_id() -> None:
    """compute_per_project_throughput respects project_ids filter when provided."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_id=1,
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_id=2,
            check_ins=[_make_check_in(date(2026, 1, 12), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_per_project_throughput(handoffs, project_ids=[1])
    assert len(df) == 1


def test_compute_per_project_throughput_includes_all_when_no_filter() -> None:
    """compute_per_project_throughput includes all projects when project_ids is None."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_id=1,
            check_ins=[_make_check_in(date(2026, 1, 11), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            project_id=2,
            check_ins=[_make_check_in(date(2026, 1, 12), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_per_project_throughput(handoffs)
    assert len(df) == 2


# =============================================================================
# Aging Profile Tests
# =============================================================================


def test_compute_open_aging_profile_categorizes_age_buckets() -> None:
    """compute_open_aging_profile buckets open handoffs by age."""
    today = date(2026, 3, 10)
    handoffs = [
        _make_handoff(id=1, created_at=datetime(2026, 3, 8)),  # 2 days old
        _make_handoff(id=2, created_at=datetime(2026, 2, 23)),  # 15 days old
        _make_handoff(id=3, created_at=datetime(2026, 2, 1)),  # 37 days old
    ]

    df = compute_open_aging_profile(handoffs, today=today)
    by_bucket = df.set_index("aging_bucket")["handoffs"]
    assert by_bucket["0-7d"] == 1
    assert by_bucket["8-14d"] == 0
    assert by_bucket["15-30d"] == 1
    assert by_bucket["31+d"] == 1


def test_compute_open_aging_profile_handles_missing_created_at() -> None:
    """compute_open_aging_profile skips handoffs without created_at."""
    today = date(2026, 3, 10)
    handoff = SimpleNamespace(
        id=1,
        project_id=1,
        created_at=None,
    )

    df = compute_open_aging_profile([handoff], today=today)
    assert df["handoffs"].sum() == 0


# =============================================================================
# Reopen Rate Tests
# =============================================================================


def test_compute_reopen_rate_summary_counts_reopened_closes() -> None:
    """compute_reopen_rate_summary tracks reopened vs total closes."""
    today = date(2026, 3, 12)
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
            check_ins=[
                _make_check_in(date(2026, 3, 10), CheckInType.CONCLUDED),
                _make_check_in(date(2026, 3, 11), CheckInType.ON_TRACK),
            ],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
            check_ins=[
                _make_check_in(date(2026, 3, 10), CheckInType.CONCLUDED),
            ],
        ),
    ]

    summary = compute_reopen_rate_summary(handoffs, today=today, window_days=30)
    assert summary.total_closes == 2
    assert summary.reopened_closes == 1
    assert summary.rate == 0.5


def test_reopen_rate_summary_rate_property_handles_zero_closes() -> None:
    """ReopenRateSummary.rate returns None when no closes exist."""
    summary = ReopenRateSummary(reopened_closes=0, total_closes=0)
    assert summary.rate is None


def test_reopen_rate_summary_rate_display_shows_percentage() -> None:
    """ReopenRateSummary.rate_display formats rate as percentage."""
    summary = ReopenRateSummary(reopened_closes=1, total_closes=4)
    assert summary.rate_display == "25%"


def test_reopen_rate_summary_detail_display_shows_summary_text() -> None:
    """ReopenRateSummary.detail_display provides user-friendly text."""
    summary = ReopenRateSummary(reopened_closes=2, total_closes=5)
    assert "2 of 5" in summary.detail_display


def test_reopen_rate_summary_detail_display_handles_empty_window() -> None:
    """ReopenRateSummary.detail_display shows message for empty window."""
    summary = ReopenRateSummary(reopened_closes=0, total_closes=0)
    assert "No closes" in summary.detail_display


# =============================================================================
# On-Time Close Rate Trend Tests
# =============================================================================


def test_compute_on_time_close_rate_trend_calculates_weekly_rates() -> None:
    """compute_on_time_close_rate_trend returns weekly on-time percentages."""
    today = date(2026, 3, 12)
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            deadline=date(2026, 3, 10),
            check_ins=[_make_check_in(date(2026, 3, 9), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            deadline=date(2026, 3, 10),
            check_ins=[_make_check_in(date(2026, 3, 11), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_on_time_close_rate_trend(handoffs, today=today, weeks=2)
    assert len(df) > 0
    assert "on_time_rate_pct" in df.columns
    assert "50%" in df["on_time_rate_pct"].values


def test_compute_on_time_close_rate_trend_returns_empty_for_no_closes() -> None:
    """compute_on_time_close_rate_trend returns empty DataFrame for no closures."""
    today = date(2026, 3, 12)
    df = compute_on_time_close_rate_trend([], today=today, weeks=8)
    assert df.empty


def test_compute_on_time_close_rate_trend_handles_none_deadline() -> None:
    """compute_on_time_close_rate_trend ignores handoffs without deadline."""
    today = date(2026, 3, 12)
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            check_ins=[_make_check_in(date(2026, 3, 9), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_on_time_close_rate_trend(handoffs, today=today, weeks=2)
    assert df.empty


# =============================================================================
# Deadline Adherence Trend Tests
# =============================================================================


def test_compute_deadline_adherence_trend_derives_today_from_data() -> None:
    """compute_deadline_adherence_trend automatically derives 'today' from close dates."""
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 1, 1, 0, 0, 0),
            deadline=date(2026, 3, 10),
            check_ins=[_make_check_in(date(2026, 3, 9), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_deadline_adherence_trend(handoffs, weeks=4)
    assert "week_label" in df.columns
    assert "on_time_rate" in df.columns


def test_compute_deadline_adherence_trend_returns_empty_for_no_data() -> None:
    """compute_deadline_adherence_trend returns empty DataFrame for no handoffs."""
    df = compute_deadline_adherence_trend([], weeks=4)
    assert df.empty


# =============================================================================
# Pitchman Throughput Trend Tests
# =============================================================================


def test_compute_per_pitchman_throughput_shows_week_over_week_trend() -> None:
    """compute_per_pitchman_throughput compares this week vs last week."""
    today = date(2026, 3, 12)  # Wednesday
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
            pitchman="Alice",
            check_ins=[_make_check_in(date(2026, 3, 10), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
            pitchman="Alice",
            check_ins=[_make_check_in(date(2026, 3, 3), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_per_pitchman_throughput(handoffs, today=today)
    assert "trend" in df.columns
    alice = df[df["pitchman"] == "Alice"]
    assert len(alice) == 1


def test_compute_per_pitchman_throughput_shows_trend_up_down_same() -> None:
    """compute_per_pitchman_throughput calculates week-over-week trend."""
    today = date(2026, 3, 12)
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
            pitchman="Alice",
            check_ins=[_make_check_in(date(2026, 3, 10), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 3, 1, 9, 0, 0),
            pitchman="Bob",
            check_ins=[_make_check_in(date(2026, 3, 3), CheckInType.CONCLUDED)],
        ),
    ]

    df = compute_per_pitchman_throughput(handoffs, today=today)
    trends = df["trend"].unique()
    assert all(t in {"up", "down", "same"} for t in trends)
