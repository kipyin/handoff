"""Tests for shared date helpers."""

from datetime import date

from handoff.dates import week_bounds


def test_week_bounds_midweek() -> None:
    """week_bounds returns Monday-Sunday for a midweek date."""
    mon, sun = week_bounds(date(2026, 2, 25))  # Wednesday
    assert mon == date(2026, 2, 23)
    assert sun == date(2026, 3, 1)


def test_week_bounds_monday() -> None:
    mon, sun = week_bounds(date(2026, 3, 2))
    assert mon == date(2026, 3, 2)
    assert sun == date(2026, 3, 8)


def test_week_bounds_sunday() -> None:
    mon, sun = week_bounds(date(2026, 3, 1))
    assert mon == date(2026, 2, 23)
    assert sun == date(2026, 3, 1)
