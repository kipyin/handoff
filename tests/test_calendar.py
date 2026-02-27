"""Tests for calendar week-bound helpers."""

from __future__ import annotations

from datetime import date, datetime

from todo_app.pages.calendar import _get_week_bounds


def test_get_week_bounds_returns_monday_to_sunday_for_reference_date() -> None:
    """_get_week_bounds should return the ISO week (Mon–Sun) around the reference date."""
    reference = date(2026, 2, 27)  # Friday
    start_dt, end_dt = _get_week_bounds(reference)

    # Monday of that week is 2026-02-23 and Sunday is 2026-03-01.
    assert start_dt == datetime(2026, 2, 23)
    assert end_dt == datetime(2026, 3, 1, 23, 59, 59, 999999)
