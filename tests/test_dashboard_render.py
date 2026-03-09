"""Tests for pages/dashboard.py render_dashboard_page via Streamlit mocking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from handoff.pages.dashboard import render_dashboard_page
from handoff.services.dashboard_service import DashboardMetrics


def _nonempty_weekly() -> pd.DataFrame:
    return pd.DataFrame({"week_label": ["2026-W10"], "completed": [1]})


def _nonempty_project_throughput() -> pd.DataFrame:
    return pd.DataFrame({"project": ["P1"], "completed": [3]})


def _nonempty_helper_throughput() -> pd.DataFrame:
    return pd.DataFrame({"helper": ["Alice"], "completed": [2]})


def _nonempty_cycle_by_project() -> pd.DataFrame:
    return pd.DataFrame({"project": ["P1"], "median_days": [2.0]})


def _nonempty_adherence_trend() -> pd.DataFrame:
    return pd.DataFrame({"week_label": ["2026-W10"], "on_time_rate": [0.8]})


class TestRenderDashboardPage:
    def _patch(
        self,
        monkeypatch,
        *,
        metrics=None,
        weekly_empty=True,
        helper_load_empty=True,
        project_throughput_empty=True,
        helper_throughput_empty=True,
        cycle_empty=True,
        adherence_empty=True,
        recent_activity=None,
        export_has_data=False,
    ):
        st_mock = MagicMock()

        class FakeCol:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        def _columns(n: int):
            return [FakeCol() for _ in range(n)]

        st_mock.columns.side_effect = _columns
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

        monkeypatch.setattr(
            "handoff.pages.dashboard.get_weekly_throughput",
            lambda *a, **kw: pd.DataFrame() if weekly_empty else _nonempty_weekly(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_per_project_throughput",
            lambda *a, **kw: (
                pd.DataFrame() if project_throughput_empty else _nonempty_project_throughput()
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_per_helper_throughput",
            lambda *a, **kw: (
                pd.DataFrame() if helper_throughput_empty else _nonempty_helper_throughput()
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_cycle_time_by_project",
            lambda *a, **kw: pd.DataFrame() if cycle_empty else _nonempty_cycle_by_project(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_deadline_adherence_trend",
            lambda *a, **kw: pd.DataFrame() if adherence_empty else _nonempty_adherence_trend(),
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
            lambda *a, **kw: (
                {"csv": "x", "json": "{}"} if export_has_data else {"csv": "", "json": ""}
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_recent_activity",
            lambda *a, **kw: recent_activity if recent_activity is not None else [],
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

    def test_with_weekly_throughput(self, monkeypatch) -> None:
        """Dashboard with weekly throughput shows bar chart."""
        st_mock = self._patch(monkeypatch, weekly_empty=False)
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Completed per week (last 8 weeks)")
        assert st_mock.bar_chart.called

    def test_with_project_and_helper_throughput(self, monkeypatch) -> None:
        """Dashboard with per-project and per-helper throughput shows dataframe and chart."""
        st_mock = self._patch(
            monkeypatch,
            project_throughput_empty=False,
            helper_throughput_empty=False,
        )
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Per-project throughput (last 8 weeks)")
        st_mock.markdown.assert_any_call("#### Per-helper throughput (last 8 weeks)")
        assert st_mock.dataframe.called
        assert st_mock.bar_chart.called

    def test_with_cycle_time_and_adherence_trend(self, monkeypatch) -> None:
        """Dashboard with cycle time and adherence trend shows dataframe and line chart."""
        st_mock = self._patch(
            monkeypatch,
            cycle_empty=False,
            adherence_empty=False,
        )
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Cycle time by project (last 28 days)")
        st_mock.markdown.assert_any_call("#### Deadline adherence trend (on-time rate per week)")
        assert st_mock.dataframe.called
        assert st_mock.line_chart.called

    def test_with_recent_activity(self, monkeypatch) -> None:
        """Dashboard with recent activity shows activity captions."""
        st_mock = self._patch(
            monkeypatch,
            recent_activity=[
                {
                    "timestamp": "2026-03-09 12:00",
                    "entity_type": "todo",
                    "entity_id": "1",
                    "action": "completed",
                    "details": {"name": "Task"},
                },
            ],
        )
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Recent activity")
        caption_calls = [str(c) for c in st_mock.caption.call_args_list]
        assert any("Task" in c or "todo" in c for c in caption_calls)

    def test_with_export_metrics(self, monkeypatch) -> None:
        """Dashboard with exportable metrics shows CSV and JSON download buttons."""
        st_mock = self._patch(monkeypatch, export_has_data=True)
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Export metrics")
        assert st_mock.download_button.call_count >= 2
        download_calls = st_mock.download_button.call_args_list
        file_names = [c[1].get("file_name", "") for c in download_calls]
        assert any("csv" in f.lower() for f in file_names)
        assert any("json" in f.lower() for f in file_names)
