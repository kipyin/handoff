"""Tests for analytics page helpers."""

from __future__ import annotations

from datetime import date, datetime

import pandas as pd
import pytest

from handoff.pages.analytics import (
    _build_done_dataframe,
    _compute_cycle_time_stats,
    _compute_helper_load,
    _compute_weekly_counts,
    _parse_date_range,
)


def test_parse_date_range_two_element_tuple() -> None:
    """_parse_date_range returns (start, end) for a 2-element tuple."""
    start, end = date(2026, 1, 1), date(2026, 1, 31)
    assert _parse_date_range((start, end)) == (start, end)


def test_parse_date_range_two_element_list() -> None:
    """_parse_date_range returns (start, end) for a 2-element list."""
    start, end = date(2026, 2, 1), date(2026, 2, 28)
    assert _parse_date_range([start, end]) == (start, end)


def test_parse_date_range_single_date_returns_none() -> None:
    """_parse_date_range returns (None, None) for a single date."""
    assert _parse_date_range(date(2026, 3, 1)) == (None, None)


def test_parse_date_range_empty_or_wrong_length_returns_none() -> None:
    """_parse_date_range returns (None, None) for wrong-length sequences."""
    assert _parse_date_range([]) == (None, None)
    assert _parse_date_range([date(2026, 1, 1)]) == (None, None)
    assert _parse_date_range((date(2026, 1, 1), date(2026, 1, 2), date(2026, 1, 3))) == (
        None,
        None,
    )


def test_compute_weekly_counts_aggregates_by_week() -> None:
    """_compute_weekly_counts returns weekly completed counts sorted by week."""
    df = pd.DataFrame(
        {
            "id": [1, 2, 3],
            "completed_at": [
                datetime(2026, 1, 6),
                datetime(2026, 1, 7),
                datetime(2026, 1, 14),
            ],
        }
    )
    result = _compute_weekly_counts(df)
    assert "week_label" in result.columns
    assert "completed" in result.columns
    assert len(result) == 2
    # Two todos in one week, one in another; order by week_label ascending
    assert list(result["completed"]) == [2, 1]
    assert result["week_label"].is_monotonic_increasing


def test_compute_cycle_time_stats_returns_mean_p50_p90() -> None:
    """_compute_cycle_time_stats returns (df_with_cycle_days, mean, p50, p90)."""
    df = pd.DataFrame(
        {
            "completed_at": [datetime(2026, 1, 10)] * 4,
            "created_at": [
                datetime(2026, 1, 8),
                datetime(2026, 1, 9),
                datetime(2026, 1, 7),
                datetime(2026, 1, 5),
            ],
        }
    )
    df_out, avg, p50, p90 = _compute_cycle_time_stats(df)
    assert "cycle_days" in df_out.columns
    # cycle_days: 2, 1, 3, 5 -> mean 2.75, median 2.5, p90 interpolated
    assert avg == 2.75
    assert p50 == 2.5
    assert p90 >= 3.0 and p90 <= 5.0


def test_compute_helper_load_aggregates_and_sorts() -> None:
    """_compute_helper_load returns helper counts sorted by handoff descending."""

    class Todo:
        def __init__(self, id: int, helper: str | None):
            self.id = id
            self.helper = helper

    todos = [
        Todo(1, "Alice"),
        Todo(2, "Alice"),
        Todo(3, "Bob"),
        Todo(4, None),
    ]
    result = _compute_helper_load(todos)
    assert set(result["helper"]) == {"Alice", "Bob", "(unassigned)"}
    counts = result.set_index("helper")["handoff"]
    assert counts["Alice"] == 2
    assert counts["Bob"] == 1
    assert counts["(unassigned)"] == 1
    # First row should be the one with highest count (Alice)
    assert result.iloc[0]["helper"] == "Alice"
    assert result.iloc[0]["handoff"] == 2


def test_build_done_dataframe_empty_when_no_todos(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_done_dataframe returns empty DataFrame with expected columns when query returns []."""
    monkeypatch.setattr(
        "handoff.pages.analytics.query_todos",
        lambda **kwargs: [],
    )
    result = _build_done_dataframe(None, None)
    assert result.empty
    assert list(result.columns) == [
        "id",
        "name",
        "helper",
        "project",
        "created_at",
        "completed_at",
    ]


def test_build_done_dataframe_with_todos(monkeypatch: pytest.MonkeyPatch) -> None:
    """_build_done_dataframe returns rows from query_todos with correct columns."""

    class Project:
        name = "Proj"

    class Todo:
        id = 1
        name = "Done task"
        helper = "Alice"
        project = Project()
        created_at = datetime(2026, 1, 1)
        completed_at = datetime(2026, 1, 5)

    monkeypatch.setattr(
        "handoff.pages.analytics.query_todos",
        lambda **kwargs: [Todo()],
    )
    result = _build_done_dataframe(date(2026, 1, 1), date(2026, 1, 31))
    assert len(result) == 1
    assert result.iloc[0]["name"] == "Done task"
    assert result.iloc[0]["helper"] == "Alice"
    assert result.iloc[0]["project"] == "Proj"
