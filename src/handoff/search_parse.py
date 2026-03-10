"""Parse natural-language search queries into structured date filters and text.

Supports expressions like @today (check due/overdue), @due today, overdue,
check this week, due next 7 days. Remaining text is passed through for ILIKE.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import date, timedelta

from handoff.dates import week_bounds


@dataclass
class SearchParseResult:
    """Result of parsing a search query.

    Attributes:
        text_query: Remaining free text for ILIKE search, or None if empty.
        next_check_min: Minimum next_check date (inclusive), or None.
        next_check_max: Maximum next_check date (inclusive), or None.
        deadline_min: Minimum deadline date (inclusive), or None.
        deadline_max: Maximum deadline date (inclusive), or None.
    """

    text_query: str | None
    next_check_min: date | None
    next_check_max: date | None
    deadline_min: date | None
    deadline_max: date | None


def parse_search_query(text: str) -> SearchParseResult:
    """Parse natural-language search text into date filters and remaining text.

    Recognized patterns (case-insensitive):
    - @today, @check today, check today: next_check <= today (today or overdue)
    - @check this week, check this week: next_check in current week
    - check tomorrow, check next week, check next 7 days: next_check ranges
    - @due today, due today: deadline == today
    - @due tomorrow, due tomorrow, due next 7 days: deadline in range
    - overdue, @overdue: deadline < today

    Args:
        text: Raw search input.

    Returns:
        SearchParseResult with date bounds and remaining text for ILIKE.
    """
    today = date.today()
    yesterday = today - timedelta(days=1)
    tomorrow = today + timedelta(days=1)
    mon_this, sun_this = week_bounds(today)
    mon_next, sun_next = week_bounds(today + timedelta(days=7))
    next_7_end = today + timedelta(days=6)

    next_check_min: date | None = None
    next_check_max: date | None = None
    deadline_min: date | None = None
    deadline_max: date | None = None

    remainder = (text or "").strip()
    if not remainder:
        return SearchParseResult(
            text_query=None,
            next_check_min=None,
            next_check_max=None,
            deadline_min=None,
            deadline_max=None,
        )

    # Check patterns (next_check)
    def set_check_today() -> None:
        nonlocal next_check_max
        next_check_max = today

    def set_check_tomorrow() -> None:
        nonlocal next_check_min, next_check_max
        next_check_min = tomorrow
        next_check_max = tomorrow

    def set_check_this_week() -> None:
        nonlocal next_check_min, next_check_max
        next_check_min = mon_this
        next_check_max = sun_this

    def set_check_next_week() -> None:
        nonlocal next_check_min, next_check_max
        next_check_min = mon_next
        next_check_max = sun_next

    def set_check_next_7_days() -> None:
        nonlocal next_check_min, next_check_max
        next_check_min = today
        next_check_max = next_7_end

    # Due patterns (deadline)
    def set_due_today() -> None:
        nonlocal deadline_min, deadline_max
        deadline_min = today
        deadline_max = today

    def set_due_tomorrow() -> None:
        nonlocal deadline_min, deadline_max
        deadline_min = tomorrow
        deadline_max = tomorrow

    def set_due_this_week() -> None:
        nonlocal deadline_min, deadline_max
        deadline_min = mon_this
        deadline_max = sun_this

    def set_due_next_week() -> None:
        nonlocal deadline_min, deadline_max
        deadline_min = mon_next
        deadline_max = sun_next

    def set_due_next_7_days() -> None:
        nonlocal deadline_min, deadline_max
        deadline_min = today
        deadline_max = next_7_end

    def set_overdue() -> None:
        nonlocal deadline_max
        deadline_max = yesterday

    # Build pattern list: (pattern, repl, action)
    # Use \b for word boundaries to avoid matching "today" inside "today123"
    patterns = [
        (re.compile(r"@today\b", re.I), " ", set_check_today),
        (re.compile(r"@check\s+today\b", re.I), " ", set_check_today),
        (re.compile(r"\bcheck\s+today\b", re.I), " ", set_check_today),
        (re.compile(r"@check\s+this\s+week\b", re.I), " ", set_check_this_week),
        (re.compile(r"\bcheck\s+this\s+week\b", re.I), " ", set_check_this_week),
        (re.compile(r"@check\s+next\s+week\b", re.I), " ", set_check_next_week),
        (re.compile(r"\bcheck\s+next\s+week\b", re.I), " ", set_check_next_week),
        (re.compile(r"@check\s+next\s+7\s+days\b", re.I), " ", set_check_next_7_days),
        (re.compile(r"\bcheck\s+next\s+7\s+days\b", re.I), " ", set_check_next_7_days),
        (re.compile(r"@check\s+tomorrow\b", re.I), " ", set_check_tomorrow),
        (re.compile(r"\bcheck\s+tomorrow\b", re.I), " ", set_check_tomorrow),
        (re.compile(r"@due\s+today\b", re.I), " ", set_due_today),
        (re.compile(r"\bdue\s+today\b", re.I), " ", set_due_today),
        (re.compile(r"@due\s+tomorrow\b", re.I), " ", set_due_tomorrow),
        (re.compile(r"\bdue\s+tomorrow\b", re.I), " ", set_due_tomorrow),
        (re.compile(r"@due\s+this\s+week\b", re.I), " ", set_due_this_week),
        (re.compile(r"\bdue\s+this\s+week\b", re.I), " ", set_due_this_week),
        (re.compile(r"@due\s+next\s+week\b", re.I), " ", set_due_next_week),
        (re.compile(r"\bdue\s+next\s+week\b", re.I), " ", set_due_next_week),
        (re.compile(r"@due\s+next\s+7\s+days\b", re.I), " ", set_due_next_7_days),
        (re.compile(r"\bdue\s+next\s+7\s+days\b", re.I), " ", set_due_next_7_days),
        (re.compile(r"@overdue\b", re.I), " ", set_overdue),
        (re.compile(r"\boverdue\b", re.I), " ", set_overdue),
    ]

    for pat, repl, action in patterns:
        if pat.search(remainder):
            remainder = pat.sub(repl, remainder)
            action()

    remainder = " ".join(remainder.split()).strip()
    text_query = remainder if remainder else None

    return SearchParseResult(
        text_query=text_query,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
    )
