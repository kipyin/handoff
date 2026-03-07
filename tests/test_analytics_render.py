"""Tests for pages/analytics.py render_analytics_page via Streamlit mocking."""

from __future__ import annotations

from datetime import date, datetime, timedelta
from unittest.mock import MagicMock

from handoff.models import Todo, TodoStatus
from handoff.pages.analytics import render_analytics_page


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


class TestRenderAnalyticsPage:
    def _patch(self, monkeypatch, *, open_handoffs=None, done_recent=None, handoff_todos=None):
        st_mock = MagicMock()

        class FakeCol:
            def __enter__(self):
                return self

            def __exit__(self, *a):
                return False

        st_mock.columns.return_value = [FakeCol() for _ in range(4)]
        monkeypatch.setattr("handoff.pages.analytics.st", st_mock)

        monkeypatch.setattr(
            "handoff.pages.analytics._count_open_handoffs",
            lambda: len(open_handoffs or []),
        )

        def fake_completed(start, end):
            return done_recent or []

        monkeypatch.setattr("handoff.pages.analytics._completed_in_range", fake_completed)
        monkeypatch.setattr(
            "handoff.pages.analytics.query_todos",
            lambda statuses, include_archived: handoff_todos or [],
        )

        return st_mock

    def test_empty_dashboard(self, monkeypatch) -> None:
        """Dashboard with no data renders without errors."""
        st_mock = self._patch(monkeypatch)
        render_analytics_page()
        st_mock.subheader.assert_called_once_with("Dashboard")
        st_mock.info.assert_called_once()

    def test_with_cycle_stats_and_overdue(self, monkeypatch) -> None:
        """Dashboard with completed todos shows cycle time and on-time rate."""
        today = date.today()
        todos = [
            _make_todo(
                created_at=datetime(2026, 2, 1),
                completed_at=datetime(2026, 2, 5),
                deadline=today + timedelta(days=10),
            ),
            _make_todo(
                created_at=datetime(2026, 2, 10),
                completed_at=datetime(2026, 2, 12),
                deadline=today - timedelta(days=30),
            ),
        ]
        st_mock = self._patch(monkeypatch, done_recent=todos)
        render_analytics_page()

        metric_calls = list(st_mock.metric.call_args_list)
        labels = [c[0][0] for c in metric_calls]
        assert "Median cycle time" in labels
        assert "On-time rate" in labels
        cycle_call = next(c for c in metric_calls if c[0][0] == "Median cycle time")
        assert "d" in str(cycle_call[0][1])

    def test_with_handoff_todos(self, monkeypatch) -> None:
        """Dashboard with open handoff todos shows helper load chart."""
        handoffs = [
            _make_todo(status=TodoStatus.HANDOFF, helper="Alice"),
            _make_todo(status=TodoStatus.HANDOFF, helper="Bob"),
        ]
        st_mock = self._patch(monkeypatch, handoff_todos=handoffs)
        render_analytics_page()

        st_mock.markdown.assert_any_call("#### Current helper load")
        assert st_mock.bar_chart.called
