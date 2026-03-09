"""Tests for natural-language search parsing."""

from __future__ import annotations

from datetime import date
from unittest.mock import patch

from handoff.search_parse import parse_search_query


@patch("handoff.search_parse.date")
def test_parse_search_query_empty(date_mock: object) -> None:
    """Empty or whitespace input returns no filters."""
    date_mock.today.return_value = date(2026, 3, 9)
    for inp in ["", "  ", "\t"]:
        r = parse_search_query(inp)
        assert r.text_query is None
        assert r.next_check_min is None
        assert r.next_check_max is None
        assert r.deadline_min is None
        assert r.deadline_max is None


@patch("handoff.search_parse.date")
def test_parse_search_query_at_today(date_mock: object) -> None:
    """@today sets next_check_max to today (check due or overdue)."""
    date_mock.today.return_value = date(2026, 3, 9)
    r = parse_search_query("@today")
    assert r.text_query is None
    assert r.next_check_min is None
    assert r.next_check_max == date(2026, 3, 9)
    assert r.deadline_min is None
    assert r.deadline_max is None


@patch("handoff.search_parse.date")
def test_parse_search_query_check_today(date_mock: object) -> None:
    """check today and @check today set next_check_max to today."""
    date_mock.today.return_value = date(2026, 3, 9)
    for inp in ["check today", "@check today", "Check Today"]:
        r = parse_search_query(inp)
        assert r.next_check_max == date(2026, 3, 9)
        assert r.text_query is None


@patch("handoff.search_parse.date")
def test_parse_search_query_due_today(date_mock: object) -> None:
    """@due today and due today set deadline to exact today."""
    date_mock.today.return_value = date(2026, 3, 9)
    for inp in ["@due today", "due today", "Due Today"]:
        r = parse_search_query(inp)
        assert r.deadline_min == date(2026, 3, 9)
        assert r.deadline_max == date(2026, 3, 9)
        assert r.text_query is None


@patch("handoff.search_parse.date")
def test_parse_search_query_overdue(date_mock: object) -> None:
    """overdue and @overdue set deadline_max to yesterday."""
    date_mock.today.return_value = date(2026, 3, 9)
    for inp in ["overdue", "@overdue", "Overdue"]:
        r = parse_search_query(inp)
        assert r.deadline_max == date(2026, 3, 8)
        assert r.text_query is None


@patch("handoff.search_parse.date")
def test_parse_search_query_check_this_week(date_mock: object) -> None:
    """@check this week sets next_check range to current week (Mon–Sun)."""
    date_mock.today.return_value = date(2026, 3, 9)  # Monday
    r = parse_search_query("@check this week")
    assert r.next_check_min == date(2026, 3, 9)
    assert r.next_check_max == date(2026, 3, 15)
    assert r.text_query is None


@patch("handoff.search_parse.date")
def test_parse_search_query_mixed_text_and_date(date_mock: object) -> None:
    """Date patterns are stripped; remaining text becomes text_query."""
    date_mock.today.return_value = date(2026, 3, 9)
    r = parse_search_query("review @today draft")
    assert r.text_query == "review draft"
    assert r.next_check_max == date(2026, 3, 9)


@patch("handoff.search_parse.date")
def test_parse_search_query_no_match(date_mock: object) -> None:
    """Unrecognized text passes through as text_query only."""
    date_mock.today.return_value = date(2026, 3, 9)
    r = parse_search_query("need report from Bob")
    assert r.text_query == "need report from Bob"
    assert r.next_check_min is None
    assert r.next_check_max is None
    assert r.deadline_min is None
    assert r.deadline_max is None


@patch("handoff.search_parse.date")
def test_parse_search_query_due_tomorrow(date_mock: object) -> None:
    """due tomorrow sets deadline to tomorrow."""
    date_mock.today.return_value = date(2026, 3, 9)
    r = parse_search_query("due tomorrow")
    assert r.deadline_min == date(2026, 3, 10)
    assert r.deadline_max == date(2026, 3, 10)
