"""Pure lifecycle helpers for handoffs and their check-in trails."""

from __future__ import annotations

from datetime import date

from handoff.models import CheckIn, CheckInType, Handoff


def _latest_check_in(handoff: Handoff) -> CheckIn | None:
    """Return the latest check-in on a handoff trail, or None."""
    if not handoff.check_ins:
        return None
    return max(
        handoff.check_ins,
        key=lambda check_in: (
            check_in.check_in_date,
            check_in.created_at,
            check_in.id or 0,
        ),
    )


def handoff_is_open(handoff: Handoff) -> bool:
    """Return True when the latest check-in is not concluded."""
    latest = _latest_check_in(handoff)
    return latest is None or latest.check_in_type != CheckInType.CONCLUDED


def handoff_is_closed(handoff: Handoff) -> bool:
    """Return True when the latest check-in is concluded."""
    latest = _latest_check_in(handoff)
    return latest is not None and latest.check_in_type == CheckInType.CONCLUDED


def get_handoff_close_date(handoff: Handoff) -> date | None:
    """Return the date of the most recent concluded check-in, if any."""
    concluded = [ci for ci in handoff.check_ins if ci.check_in_type == CheckInType.CONCLUDED]
    if not concluded:
        return None
    return max(ci.check_in_date for ci in concluded)
