"""Tests for pages/dashboard.py render_dashboard_page via Streamlit mocking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from handoff.pages.dashboard import render_dashboard_page
from handoff.services.dashboard_service import DashboardMetrics


def _nonempty_trend() -> pd.DataFrame:
    return pd.DataFrame(
        {
            "week_label": ["2026-W10"],
            "on_time_rate": [0.8],
            "on_time_rate_pct": ["80%"],
            "total": [5],
        }
    )


def _nonempty_aging() -> pd.DataFrame:
    return pd.DataFrame({"aging_bucket": ["0-7d"], "handoffs": [2]})


def _nonempty_cycle() -> pd.DataFrame:
    return pd.DataFrame({"project": ["P1"], "p50_days": [4.0], "p90_days": [9.0], "closes": [3]})


class TestRenderDashboardPage:
    def _patch(
        self,
        monkeypatch,
        *,
        metrics=None,
        trend_empty=True,
        aging_empty=True,
        cycle_empty=True,
        recent_activity=None,
        export_has_data=False,
    ):
        st_mock = MagicMock()
        st_mock.download_button.return_value = False

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
            at_risk_now=0,
            missed_check_in=0,
            check_in_due_today=0,
            open_handoffs=0,
            reopen_rate="—",
            reopen_rate_detail="No closes in window",
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_dashboard_metrics",
            lambda _: metrics or default_metrics,
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_on_time_close_rate_trend",
            lambda *a, **kw: pd.DataFrame() if trend_empty else _nonempty_trend(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_open_aging_profile",
            lambda *a, **kw: pd.DataFrame() if aging_empty else _nonempty_aging(),
        )
        monkeypatch.setattr(
            "handoff.pages.dashboard.get_cycle_time_by_project",
            lambda *a, **kw: pd.DataFrame() if cycle_empty else _nonempty_cycle(),
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
        st_mock = self._patch(monkeypatch)
        render_dashboard_page()
        st_mock.subheader.assert_called_once_with("Dashboard")
        st_mock.info.assert_called_once_with(
            "No closed handoffs with deadlines in the last 8 weeks."
        )

    def test_pm_cards_render(self, monkeypatch) -> None:
        metrics = DashboardMetrics(
            at_risk_now=3,
            missed_check_in=2,
            check_in_due_today=1,
            open_handoffs=8,
            reopen_rate="25%",
            reopen_rate_detail="1 of 4 closes reopened",
        )
        st_mock = self._patch(monkeypatch, metrics=metrics)
        render_dashboard_page()
        labels = [call[0][0] for call in st_mock.metric.call_args_list]
        assert "At risk now" in labels
        assert "Missed check-in" in labels
        assert "Open handoffs" in labels
        assert "Reopen rate (90d)" in labels
        st_mock.metric.assert_any_call("Missed check-in", 2, delta="1 due today")
        st_mock.caption.assert_any_call(
            "Risk uses the System Settings deadline-near window. "
            "Missed check-in means the scheduled check date has passed."
        )

    def test_reliability_and_flow_sections_render(self, monkeypatch) -> None:
        st_mock = self._patch(monkeypatch, trend_empty=False, aging_empty=False, cycle_empty=False)
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Reliability")
        st_mock.markdown.assert_any_call("#### Flow")
        st_mock.markdown.assert_any_call("On-time close rate trend (weekly)")
        st_mock.markdown.assert_any_call("Open aging profile")
        st_mock.markdown.assert_any_call("Cycle time by project (p50/p90, last 90 days)")
        assert st_mock.line_chart.called
        assert st_mock.bar_chart.called
        assert st_mock.dataframe.called

    def test_with_recent_activity(self, monkeypatch) -> None:
        st_mock = self._patch(
            monkeypatch,
            recent_activity=[
                {
                    "timestamp": "2026-03-09 12:00",
                    "entity_type": "handoff",
                    "entity_id": "1",
                    "action": "reopened",
                    "details": {"name": "Spec"},
                }
            ],
        )
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Recent activity")
        assert any("Spec" in str(call) for call in st_mock.caption.call_args_list)

    def test_with_export_metrics(self, monkeypatch) -> None:
        st_mock = self._patch(monkeypatch, export_has_data=True)
        render_dashboard_page()
        st_mock.markdown.assert_any_call("#### Export metrics")
        assert st_mock.download_button.call_count >= 2

    def test_export_downloads_log_application_actions(self, monkeypatch) -> None:
        st_mock = self._patch(monkeypatch, export_has_data=True)
        st_mock.download_button.side_effect = [True, True]
        logged: list[tuple[str, dict[str, str]]] = []

        monkeypatch.setattr(
            "handoff.pages.dashboard.log_application_action",
            lambda action, **details: logged.append((action, details)),
        )

        render_dashboard_page()

        assert logged == [
            ("metrics_export", {"format": "csv"}),
            ("metrics_export", {"format": "json"}),
        ]
