"""Shared date helpers (e.g. week bounds) used by todos and calendar."""

from __future__ import annotations

from datetime import date, timedelta


def format_risk_reason(deadline: date | None) -> str:
    """Return human-readable risk label: Overdue, Due today, Due tomorrow, or in N days.

    Args:
        deadline: The deadline date, or None (returns empty string).

    Returns:
        Empty string if no deadline; otherwise 'Overdue', 'Due today', 'Due tomorrow',
        or 'in N days' for future dates within the risk window.
    """
    if deadline is None:
        return ""
    today = date.today()
    if deadline < today:
        return "Overdue"
    if deadline == today:
        return "Due today"
    if deadline == today + timedelta(days=1):
        return "Due tomorrow"
    delta = (deadline - today).days
    return f"in {delta} days"


WEEKDAYS = ("Mon", "Tue", "Wed", "Thu", "Fri", "Sat", "Sun")
MONTHS_ABBREV = (
    "Jan",
    "Feb",
    "Mar",
    "Apr",
    "May",
    "Jun",
    "Jul",
    "Aug",
    "Sep",
    "Oct",
    "Nov",
    "Dec",
)


def _ordinal(n: int) -> str:
    """Return ordinal suffix: 1 -> 1st, 2 -> 2nd, 3 -> 3rd, 4 -> 4th, etc."""
    if 10 <= n % 100 <= 20:
        return f"{n}th"
    suffix = {1: "st", 2: "nd", 3: "rd"}.get(n % 10, "th")
    return f"{n}{suffix}"


def format_date_smart(d: date | None) -> str:
    """Mixed relative/absolute: today, tomorrow, this Wed, next Fri, or Tue, Mar. 10th.

    Closer dates use distance: today, tomorrow, this {Weekday}, next {Weekday}.
    Further dates (14+ days) use absolute: {Weekday}, {Mon}. {Ordinal}.
    Past dates return absolute format.
    """
    if d is None:
        return "—"
    today = date.today()
    if d == today:
        return "today"
    if d == today + timedelta(days=1):
        return "tomorrow"
    if d < today:
        wd = WEEKDAYS[d.weekday()]
        month = MONTHS_ABBREV[d.month - 1]
        return f"{wd}, {month} {_ordinal(d.day)}"
    delta = (d - today).days
    wd = WEEKDAYS[d.weekday()]
    if 2 <= delta <= 6:
        mon_today, _ = week_bounds(today)
        mon_d, _ = week_bounds(d)
        if mon_today == mon_d:
            return f"this {wd}"
        return f"next {wd}"
    if 7 <= delta <= 13:
        return f"next {wd}"
    month = MONTHS_ABBREV[d.month - 1]
    return f"{wd}, {month} {_ordinal(d.day)}"


def format_next_check(d: date | None) -> str:
    """Format next_check for display (Today / Tomorrow / Mar 12). Never 'overdue'."""
    if d is None:
        return "—"
    today = date.today()
    if d == today:
        return "Today"
    if d == today + timedelta(days=1):
        return "Tomorrow"
    return f"{d:%b} {d.day}"


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


def add_business_days(base: date, n: int = 1) -> date:
    """Return the date n business days after base. Skips Saturday and Sunday.

    Args:
        base: The starting date.
        n: Number of business days to add. Defaults to 1.

    Returns:
        The date n business days after base.

    """
    result = base
    for _ in range(n):
        result += timedelta(days=1)
        while result.weekday() >= 5:  # Sat=5, Sun=6
            result += timedelta(days=1)
    return result
