"""Tests for UI deadline helpers (non-Streamlit logic)."""

from datetime import date, timedelta

from handoff.ui_components import get_urgency_bucket
from handoff.ui_facade import (
    DEADLINE_ANY,
    DEADLINE_CUSTOM,
    DEADLINE_THIS_WEEK,
    DEADLINE_TODAY,
    DEADLINE_TOMORROW,
    _deadline_preset_bounds,
)


def test_deadline_preset_bounds_any() -> None:
    """Any preset returns no date bounds."""
    assert _deadline_preset_bounds(DEADLINE_ANY) == (None, None)


def test_deadline_preset_bounds_today() -> None:
    """Today preset returns today for both start and end."""
    today = date.today()
    start, end = _deadline_preset_bounds(DEADLINE_TODAY)
    assert start == today
    assert end == today


def test_deadline_preset_bounds_tomorrow() -> None:
    """Tomorrow preset returns tomorrow for both start and end."""
    tomorrow = date.today() + timedelta(days=1)
    start, end = _deadline_preset_bounds(DEADLINE_TOMORROW)
    assert start == tomorrow
    assert end == tomorrow


def test_deadline_preset_bounds_this_week() -> None:
    """This week preset returns Monday and Sunday of current ISO week."""
    today = date.today()
    start, end = _deadline_preset_bounds(DEADLINE_THIS_WEEK)
    weekday = today.weekday()
    expected_monday = today - timedelta(days=weekday)
    expected_sunday = expected_monday + timedelta(days=6)
    assert start == expected_monday
    assert end == expected_sunday


def test_deadline_preset_bounds_custom_returns_none() -> None:
    """Custom preset returns (None, None); UI handles range separately."""
    assert _deadline_preset_bounds(DEADLINE_CUSTOM) == (None, None)


def test_get_urgency_bucket_overdue_today_soon_and_none() -> None:
    """Urgency helper buckets delegated todos by date."""
    today = date.today()
    monday = today - timedelta(days=today.weekday())
    sunday = monday + timedelta(days=6)

    assert get_urgency_bucket(today - timedelta(days=1), "delegated") == "overdue"
    assert get_urgency_bucket(today, "delegated") == "today"
    # Pick a day later this week, but not today.
    if today < sunday:
        assert get_urgency_bucket(today + timedelta(days=1), "delegated") == "soon"
    assert get_urgency_bucket(None, "delegated") == "none"
    # Non-delegated statuses are never considered urgent.
    assert get_urgency_bucket(today, "done") == "none"
