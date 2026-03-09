"""Tests for shared date helpers."""

from datetime import date

from handoff.dates import format_next_check, week_bounds


def _freeze_today(monkeypatch) -> None:
    class _FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return cls(2026, 3, 9)

    monkeypatch.setattr("handoff.dates.date", _FixedDate)


def test_format_next_check_none() -> None:
    assert format_next_check(None) == "—"


def test_format_next_check_today(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_next_check(date(2026, 3, 9)) == "Today"


def test_format_next_check_tomorrow(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_next_check(date(2026, 3, 10)) == "Tomorrow"


def test_format_next_check_future_date(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_next_check(date(2026, 3, 12)) == "Mar 12"


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
