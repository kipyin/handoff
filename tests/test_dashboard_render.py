"""Tests for pages/dashboard.py render_dashboard_page via Streamlit mocking."""

from __future__ import annotations

from datetime import date, datetime
from unittest.mock import MagicMock

from handoff.models import Todo, TodoStatus
from handoff.pages.dashboard import render_dashboard_page
from handoff.services.dashboard_service import DashboardMetrics


def _make_todo(
    *,
    status: TodoStatus = TodoStatus.DONE,
    created_at: datetime | None = None,
    completed_at: datetime | None = None,
    deadline: date | None = None,
    helper: str | None = None,
) -> Todo:
    return Todo(
        id=1,
        project_id=1,
        name="Task",
        status=status,
        created_at=created_at or datetime(2026, 3, 1),
        completed_at=completed_at,
        deadline=deadline,
        helper=helper,
    )


class TestRenderDashboardPage:
    def _patch(self, monkeypatch, *, metrics=None, weekly_empty=True, helper_load_empty=True):
        st_mock = MagicMock()

        class FakeCol:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        st_mock.columns.return_value = [FakeCol() for _ in range(4)]
        monkeypatch.setattr("handoff.pages.dashboard.st", st_mock)

        default_metrics = DashboardMetrics(
            open_count=0,
            done_this_week=0,
            done_week_delta="same as last week",
            median_cycle_time="—",
            on_time_rate="—",
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_dashboard_metrics",
            lambda _: metrics or default_metrics,
        )

        import pandas as pd

        monkeypatch.setattr(
            "handoff.pages.dashboard.get_weekly_throughput",
            lambda *a, **kw: (
                pd.DataFrame()
                if weekly_empty
                else pd.DataFrame({"week_label": ["2026-W10"], "completed": [1]})
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_per_project_throughput",
            lambda *a, **kw: pd.DataFrame(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_per_helper_throughput",
            lambda *a, **kw: pd.DataFrame(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_cycle_time_by_project",
            lambda *a, **kw: pd.DataFrame(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_deadline_adherence_trend",
            lambda *a, **kw: pd.DataFrame(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_helper_load",
            lambda: (
                pd.DataFrame()
                if helper_load_empty
                else pd.DataFrame({"helper": ["Alice"], "handoff": [2]})
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_exportable_metrics",
            lambda *a, **kw: {"csv": "", "json": ""},
        )

        return st_mock

    def test_empty_dashboard(self, monkeypatch) -> None:
        """Dashboard with no data renders without errors."""
        st_mock = self._patch(monkeypatch)
        render_dashboard_page()
        st_mock.subheader.assert_called_once_with("Dashboard")
        st_mock.info.assert_called_once()

    def test_with_cycle_stats_and_overdue(self, monkeypatch) -> None:
        """Dashboard with completed todos shows cycle time and on-time rate."""
        metrics = DashboardMetrics(
            open_count=0,
            done_this_week=2,
            done_week_delta="+2 vs last week",
            median_cycle_time="4.0d",
            on_time_rate="50%",
        )
        st_mock = self._patch(monkeypatch, metrics=metrics)
        render_dashboard_page()

        metric_calls = list(st_mock.metric.call_args_list)
        labels = [c[0][0] for c in metric_calls]
        assert "Median cycle time" in labels
        assert "On-time rate" in labels
        cycle_call = next(c for c in metric_calls if c[0][0] == "Median cycle time")
        assert "d" in str(cycle_call[0][1])

    def test_with_handoff_todos(self, monkeypatch) -> None:
        """Dashboard with open handoff todos shows helper load chart."""
        st_mock = self._patch(monkeypatch, helper_load_empty=False)
        render_dashboard_page()

        st_mock.markdown.assert_any_call("#### Current helper load")
        assert st_mock.bar_chart.called
