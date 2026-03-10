"""Tests for shared date helpers."""

from datetime import date, timedelta

from handoff.dates import (
    add_business_days,
    format_date_smart,
    format_next_check,
    format_risk_reason,
    week_bounds,
)


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


def test_format_risk_reason_none() -> None:
    assert format_risk_reason(None) == ""


def test_format_risk_reason_due_today(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_risk_reason(date(2026, 3, 9)) == "Due today"


def test_format_risk_reason_due_tomorrow(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_risk_reason(date(2026, 3, 10)) == "Due tomorrow"


def test_format_risk_reason_overdue(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_risk_reason(date(2026, 3, 1)) == "Overdue"


def test_format_risk_reason_in_n_days(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_risk_reason(date(2026, 3, 11)) == "in 2 days"
    assert format_risk_reason(date(2026, 3, 15)) == "in 6 days"


def test_format_date_smart_none() -> None:
    assert format_date_smart(None) == "—"


def test_format_date_smart_today(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_date_smart(date(2026, 3, 9)) == "today"


def test_format_date_smart_tomorrow(monkeypatch) -> None:
    _freeze_today(monkeypatch)
    assert format_date_smart(date(2026, 3, 10)) == "tomorrow"


def test_format_date_smart_this_week(monkeypatch) -> None:
    """Same week: 'this Wed', 'this Fri'."""
    _freeze_today(monkeypatch)  # 2026-03-09 Mon
    assert format_date_smart(date(2026, 3, 11)) == "this Wed"
    assert format_date_smart(date(2026, 3, 13)) == "this Fri"


def test_format_date_smart_next_week(monkeypatch) -> None:
    """Next week: 'next Mon', 'next Fri'."""
    _freeze_today(monkeypatch)  # 2026-03-09 Mon
    assert format_date_smart(date(2026, 3, 16)) == "next Mon"
    assert format_date_smart(date(2026, 3, 20)) == "next Fri"


def test_format_date_smart_absolute(monkeypatch) -> None:
    """14+ days: 'Tue, Mar. 10th' style."""
    _freeze_today(monkeypatch)  # 2026-03-09 Mon
    assert format_date_smart(date(2026, 3, 23)) == "Mon, Mar 23rd"
    assert format_date_smart(date(2026, 3, 10)) == "tomorrow"  # not absolute


def test_format_date_smart_past(monkeypatch) -> None:
    """Past dates use absolute format."""
    _freeze_today(monkeypatch)
    assert format_date_smart(date(2026, 3, 1)) == "Sun, Mar 1st"
    assert format_date_smart(date(2026, 2, 21)) == "Sat, Feb 21st"


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


def test_format_next_check_variants() -> None:
    """format_next_check covers none/today/tomorrow/generic dates."""
    today = date.today()
    future = today + timedelta(days=10)

    assert format_next_check(None) == "—"
    assert format_next_check(today) == "Today"
    assert format_next_check(today + timedelta(days=1)) == "Tomorrow"
    assert format_next_check(future) == f"{future:%b} {future.day}"


def test_add_business_days_midweek() -> None:
    """Mon-Thu + 1 biz day = next calendar day."""
    assert add_business_days(date(2026, 3, 9), 1) == date(2026, 3, 10)  # Mon -> Tue
    assert add_business_days(date(2026, 3, 11), 1) == date(2026, 3, 12)  # Wed -> Thu


def test_add_business_days_friday() -> None:
    """Fri + 1 biz day = next Monday."""
    assert add_business_days(date(2026, 3, 13), 1) == date(2026, 3, 16)  # Fri -> Mon


def test_add_business_days_weekend() -> None:
    """Sat/Sun + 1 biz day = next Monday."""
    assert add_business_days(date(2026, 3, 14), 1) == date(2026, 3, 16)  # Sat -> Mon
    assert add_business_days(date(2026, 3, 15), 1) == date(2026, 3, 16)  # Sun -> Mon


def test_add_business_days_multiple() -> None:
    """Multiple business days."""
    assert add_business_days(date(2026, 3, 13), 2) == date(2026, 3, 17)  # Fri +2 -> Tue
