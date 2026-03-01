"""Shared date helpers (e.g. week bounds) used by todos and calendar."""

from __future__ import annotations

from datetime import date, timedelta


def week_bounds(reference: date) -> tuple[date, date]:
    """Return (monday, sunday) for the week containing the reference date.

    Week is Monday–Sunday. Uses reference.weekday() (0=Monday, 6=Sunday).

    Args:
        reference: Any date in the target week.

    Returns:
        Tuple of (monday_date, sunday_date) for that week.
    """
    weekday = reference.weekday()
    monday = reference - timedelta(days=weekday)
    sunday = monday + timedelta(days=6)
    return monday, sunday
