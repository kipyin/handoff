"""Tests for PM-focused dashboard service helpers."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd
import pytest

from handoff.models import CheckInType
from handoff.services.dashboard_service import (
    ReopenRateSummary,
    compute_cycle_time_by_project,
    compute_deadline_adherence_trend,
    compute_on_time_close_rate_trend,
    compute_open_aging_profile,
    compute_reopen_rate_summary,
    get_cycle_time_by_project,
    get_dashboard_metrics,
    get_deadline_adherence_trend,
    get_exportable_metrics,
    get_on_time_close_rate_trend,
    get_open_aging_profile,
)


def _make_check_in(
    check_in_date: date,
    check_in_type: CheckInType,
    *,
    id: int = 1,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        check_in_date=check_in_date,
        check_in_type=check_in_type,
        created_at=datetime(2026, 1, 1, 9, 0, 0),
    )


def _make_handoff(
    *,
    id: int,
    created_at: datetime,
    deadline: date | None = None,
    next_check: date | None = None,
    project_name: str = "Project",
    check_ins: list[SimpleNamespace] | None = None,
) -> SimpleNamespace:
    return SimpleNamespace(
        id=id,
        project_id=1,
        project=SimpleNamespace(name=project_name),
        created_at=created_at,
        deadline=deadline,
        next_check=next_check,
        check_ins=list(check_ins or []),
    )


def test_compute_open_aging_profile_bucket_counts() -> None:
    today = date(2026, 3, 10)
    handoffs = [
        _make_handoff(id=1, created_at=datetime(2026, 3, 8)),
        _make_handoff(id=2, created_at=datetime(2026, 3, 1)),
        _make_handoff(id=3, created_at=datetime(2026, 2, 22)),
        _make_handoff(id=4, created_at=datetime(2026, 1, 15)),
    ]
    profile_df = compute_open_aging_profile(handoffs, today=today)
    profile = profile_df.set_index("aging_bucket")["handoffs"]
    assert profile["0-7d"] == 1
    assert profile["8-14d"] == 1
    assert profile["15-30d"] == 1
    assert profile["31+d"] == 1


def test_compute_on_time_close_rate_trend_weekly_rates() -> None:
    today = date(2026, 3, 10)
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 2, 20),
            deadline=date(2026, 3, 3),
            check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=1)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 2, 20),
            deadline=date(2026, 3, 3),
            check_ins=[_make_check_in(date(2026, 3, 4), CheckInType.CONCLUDED, id=2)],
        ),
        _make_handoff(
            id=3,
            created_at=datetime(2026, 3, 1),
            deadline=date(2026, 3, 10),
            check_ins=[_make_check_in(date(2026, 3, 9), CheckInType.CONCLUDED, id=3)],
        ),
    ]
    trend = compute_on_time_close_rate_trend(handoffs, today=today, weeks=8)
    assert {"week_label", "on_time_rate", "total", "on_time_rate_pct"}.issubset(set(trend.columns))
    week_w10 = trend[trend["week_label"] == "2026-W10"].iloc[0]
    week_w11 = trend[trend["week_label"] == "2026-W11"].iloc[0]
    assert week_w10["on_time_rate"] == 0.5
    assert week_w10["total"] == 2
    assert week_w11["on_time_rate"] == 1.0
    assert week_w11["total"] == 1


def test_compute_on_time_close_rate_trend_ignores_missing_deadlines() -> None:
    today = date(2026, 3, 10)
    handoffs = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 2, 20),
            deadline=None,
            check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=1)],
        ),
        _make_handoff(
            id=2,
            created_at=datetime(2026, 2, 20),
            deadline=date(2026, 3, 3),
            check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=2)],
        ),
    ]
    trend = compute_on_time_close_rate_trend(handoffs, today=today, weeks=8)
    assert len(trend) == 1
    week = trend.iloc[0]
    assert week["total"] == 1
    assert week["on_time_rate"] == 1.0
    assert week["on_time_rate_pct"] == "100%"


def test_compute_cycle_time_by_project_returns_p50_and_p90() -> None:
    handoffs = [
        _make_handoff(
            id=1,
            project_name="Alpha",
            created_at=datetime(2026, 2, 1),
            check_ins=[_make_check_in(date(2026, 2, 4), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=2,
            project_name="Alpha",
            created_at=datetime(2026, 2, 1),
            check_ins=[_make_check_in(date(2026, 2, 10), CheckInType.CONCLUDED)],
        ),
        _make_handoff(
            id=3,
            project_name="Beta",
            created_at=datetime(2026, 2, 5),
            check_ins=[_make_check_in(date(2026, 2, 6), CheckInType.CONCLUDED)],
        ),
    ]
    result = compute_cycle_time_by_project(handoffs)
    assert {"project", "p50_days", "p90_days", "closes"}.issubset(set(result.columns))
    alpha = result[result["project"] == "Alpha"].iloc[0]
    assert alpha["closes"] == 2
    assert alpha["p90_days"] >= alpha["p50_days"]


def test_compute_reopen_rate_summary_tracks_reopened_closes() -> None:
    today = date(2026, 3, 10)
    reopened = _make_handoff(
        id=1,
        created_at=datetime(2026, 2, 1),
        check_ins=[
            _make_check_in(date(2026, 3, 1), CheckInType.CONCLUDED, id=1),
            _make_check_in(date(2026, 3, 3), CheckInType.ON_TRACK, id=2),
        ],
    )
    kept_closed = _make_handoff(
        id=2,
        created_at=datetime(2026, 2, 1),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=3)],
    )
    summary = compute_reopen_rate_summary([reopened, kept_closed], today=today, window_days=30)
    assert summary.total_closes == 2
    assert summary.reopened_closes == 1
    assert summary.rate == 0.5
    assert summary.rate_display == "50%"


def test_compute_reopen_rate_summary_handles_mixed_timezone_created_at() -> None:
    today = date(2026, 3, 10)
    check_ins = [
        SimpleNamespace(
            id=1,
            check_in_date=date(2026, 3, 1),
            check_in_type=CheckInType.CONCLUDED,
            created_at=None,
        ),
        SimpleNamespace(
            id=2,
            check_in_date=date(2026, 3, 1),
            check_in_type=CheckInType.ON_TRACK,
            created_at=datetime(2026, 3, 1, 9, 0, tzinfo=UTC),
        ),
    ]
    handoff = _make_handoff(
        id=1,
        created_at=datetime(2026, 2, 1),
        check_ins=check_ins,
    )
    summary = compute_reopen_rate_summary([handoff], today=today, window_days=30)
    assert summary.total_closes == 1
    assert summary.reopened_closes == 1


def test_compute_reopen_rate_summary_accepts_string_check_in_types() -> None:
    today = date(2026, 3, 10)
    check_ins = [
        SimpleNamespace(
            id=1,
            check_in_date=date(2026, 3, 1),
            check_in_type="concluded",
            created_at=datetime(2026, 3, 1, 8, 0, 0),
        ),
        SimpleNamespace(
            id=2,
            check_in_date=date(2026, 3, 2),
            check_in_type="on_track",
            created_at=datetime(2026, 3, 2, 8, 0, 0),
        ),
    ]
    handoff = _make_handoff(
        id=1,
        created_at=datetime(2026, 2, 1),
        check_ins=check_ins,
    )
    summary = compute_reopen_rate_summary([handoff], today=today, window_days=30)
    assert summary.total_closes == 1
    assert summary.reopened_closes == 1


def test_compute_deadline_adherence_trend_uses_dataset_timeframe() -> None:
    historical = _make_handoff(
        id=1,
        created_at=datetime(2020, 1, 1),
        deadline=date(2020, 1, 15),
        check_ins=[_make_check_in(date(2020, 1, 10), CheckInType.CONCLUDED)],
    )
    trend = compute_deadline_adherence_trend([historical], weeks=8)
    assert not trend.empty
    assert trend.iloc[0]["week_label"].startswith("2020-")


def test_compute_deadline_adherence_trend_empty_without_closes_or_weeks() -> None:
    open_handoff = _make_handoff(
        id=1,
        created_at=datetime(2026, 3, 1),
        deadline=date(2026, 3, 20),
        check_ins=[_make_check_in(date(2026, 3, 10), CheckInType.ON_TRACK)],
    )
    no_close_trend = compute_deadline_adherence_trend([open_handoff], weeks=8)
    assert no_close_trend.empty
    assert list(no_close_trend.columns) == ["week_label", "on_time_rate", "total"]

    zero_week_trend = compute_deadline_adherence_trend([open_handoff], weeks=0)
    assert zero_week_trend.empty
    assert list(zero_week_trend.columns) == ["week_label", "on_time_rate", "total"]


def test_get_dashboard_metrics_returns_pm_cards(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    open_handoffs = [
        _make_handoff(id=1, created_at=datetime(2026, 2, 1), next_check=date(2026, 3, 9)),
        _make_handoff(id=2, created_at=datetime(2026, 2, 2), next_check=date(2026, 3, 10)),
        _make_handoff(id=3, created_at=datetime(2026, 2, 3), next_check=date(2026, 3, 12)),
    ]
    analytics_handoffs = [_make_handoff(id=4, created_at=datetime(2026, 2, 1))]
    query_calls: list[dict[str, object]] = []
    risk_calls: list[dict[str, object]] = []

    def fake_query_handoffs(**kwargs):
        query_calls.append(kwargs)
        if kwargs.get("include_concluded"):
            return analytics_handoffs
        return open_handoffs

    monkeypatch.setattr("handoff.services.dashboard_service.query_handoffs", fake_query_handoffs)
    monkeypatch.setattr(
        "handoff.services.dashboard_service.query_risk_handoffs",
        lambda **kwargs: risk_calls.append(kwargs) or [open_handoffs[0], open_handoffs[1]],
    )
    monkeypatch.setattr("handoff.services.dashboard_service.get_deadline_near_days", lambda: 2)
    monkeypatch.setattr(
        "handoff.services.dashboard_service.compute_reopen_rate_summary",
        lambda *args, **kwargs: ReopenRateSummary(reopened_closes=1, total_closes=4),
    )

    metrics = get_dashboard_metrics(today)
    assert metrics.at_risk_now == 2
    assert metrics.action_overdue == 1
    assert metrics.action_due_today == 1
    assert metrics.open_handoffs == 3
    assert metrics.reopen_rate == "25%"
    assert metrics.reopen_rate_detail == "1 of 4 closes reopened"
    analytics_call = next(call for call in query_calls if call.get("include_concluded"))
    assert analytics_call["concluded_start"] == today - timedelta(days=90)
    assert analytics_call["concluded_end"] == today
    assert risk_calls == [{"deadline_near_days": 2, "include_archived_projects": False}]


def test_get_on_time_close_rate_trend_uses_service_query(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 2, 20),
            deadline=date(2026, 3, 3),
            check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED)],
        )
    ]
    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        lambda start, end: done,
    )
    trend = get_on_time_close_rate_trend(today, weeks=8)
    assert {"week_label", "on_time_rate", "total", "on_time_rate_pct"}.issubset(set(trend.columns))


def test_get_exportable_metrics_with_data(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    done = [
        _make_handoff(
            id=1,
            created_at=datetime(2026, 2, 20),
            deadline=date(2026, 3, 3),
            check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED)],
        )
    ]
    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        lambda start, end: done,
    )
    export_data = get_exportable_metrics(today, weeks=12)
    assert export_data["csv"]
    assert "on_time_rate" in export_data["csv"]
    assert "reopen_rate" in export_data["csv"]
    assert "p90_cycle_days" in export_data["csv"]


def test_get_exportable_metrics_filters_selected_project_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date(2026, 3, 10)
    project_a = _make_handoff(
        id=1,
        created_at=datetime(2026, 2, 20),
        deadline=date(2026, 3, 3),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=1)],
    )
    project_b = _make_handoff(
        id=2,
        created_at=datetime(2026, 2, 20),
        deadline=date(2026, 3, 3),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=2)],
    )
    project_b.project_id = 2
    project_b.project = SimpleNamespace(name="Project B")
    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        lambda start, end: [project_a, project_b],
    )
    export_data = get_exportable_metrics(today, weeks=12, project_ids=[2])
    rows = json.loads(export_data["json"])
    assert len(rows) == 1
    assert rows[0]["closed"] == 1
    assert rows[0]["on_time_rate"] == 1.0


def test_get_exportable_metrics_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        lambda start, end: [],
    )
    export_data = get_exportable_metrics(today, weeks=12)
    assert export_data["csv"] == ""
    assert export_data["json"] == ""


def test_get_cycle_time_by_project_filters_selected_project_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date(2026, 3, 10)
    project_a = _make_handoff(
        id=1,
        created_at=datetime(2026, 2, 20),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=1)],
    )
    project_b = _make_handoff(
        id=2,
        created_at=datetime(2026, 2, 20),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=2)],
    )
    project_b.project_id = 2
    query_windows: list[tuple[date, date]] = []
    captured_ids: list[int] = []
    sentinel = object()

    def fake_completed_in_range(start: date, end: date):
        query_windows.append((start, end))
        return [project_a, project_b]

    def fake_compute_cycle_time_by_project(handoffs):
        captured_ids.extend(h.id for h in handoffs)
        return sentinel

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        fake_completed_in_range,
    )
    monkeypatch.setattr(
        "handoff.services.dashboard_service.compute_cycle_time_by_project",
        fake_compute_cycle_time_by_project,
    )

    result = get_cycle_time_by_project(today, days=30, project_ids=[2])

    assert result is sentinel
    assert query_windows == [(today - timedelta(days=30), today)]
    assert captured_ids == [2]


def test_get_open_aging_profile_queries_open_handoffs(monkeypatch: pytest.MonkeyPatch) -> None:
    today = date(2026, 3, 10)
    open_handoffs = [_make_handoff(id=1, created_at=datetime(2026, 3, 1))]
    query_calls: list[dict[str, object]] = []
    sentinel = object()

    def fake_query_handoffs(**kwargs):
        query_calls.append(kwargs)
        return open_handoffs

    def fake_compute_open_aging_profile(handoffs, *, today):
        assert handoffs == open_handoffs
        assert today == date(2026, 3, 10)
        return sentinel

    monkeypatch.setattr("handoff.services.dashboard_service.query_handoffs", fake_query_handoffs)
    monkeypatch.setattr(
        "handoff.services.dashboard_service.compute_open_aging_profile",
        fake_compute_open_aging_profile,
    )

    result = get_open_aging_profile(today)

    assert result is sentinel
    assert query_calls == [{"include_concluded": False, "include_archived_projects": False}]


def test_get_deadline_adherence_trend_filters_selected_project_ids(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    today = date(2026, 3, 10)
    project_a = _make_handoff(
        id=1,
        created_at=datetime(2026, 2, 20),
        deadline=date(2026, 3, 3),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=1)],
    )
    project_b = _make_handoff(
        id=2,
        created_at=datetime(2026, 2, 20),
        deadline=date(2026, 3, 3),
        check_ins=[_make_check_in(date(2026, 3, 2), CheckInType.CONCLUDED, id=2)],
    )
    project_b.project_id = 2
    captured_ids: list[int] = []

    monkeypatch.setattr(
        "handoff.services.dashboard_service.completed_in_range",
        lambda start, end: [project_a, project_b],
    )

    def fake_compute_on_time_close_rate_trend(handoffs, *, today, weeks):
        assert today == date(2026, 3, 10)
        assert weeks == 6
        captured_ids.extend(h.id for h in handoffs)
        return pd.DataFrame(
            [
                {
                    "week_label": "2026-W10",
                    "on_time_rate": 1.0,
                    "total": 1,
                    "on_time_rate_pct": "100%",
                }
            ]
        )

    monkeypatch.setattr(
        "handoff.services.dashboard_service.compute_on_time_close_rate_trend",
        fake_compute_on_time_close_rate_trend,
    )

    trend = get_deadline_adherence_trend(today, weeks=6, project_ids=[2])

    assert captured_ids == [2]
    assert list(trend.columns) == ["week_label", "on_time_rate", "total"]
    assert trend.iloc[0]["total"] == 1
