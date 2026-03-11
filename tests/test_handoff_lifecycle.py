"""Tests for pure handoff lifecycle helpers."""

from __future__ import annotations

from datetime import UTC, date, datetime

from handoff.handoff_lifecycle import (
    _latest_check_in,
    get_handoff_close_date,
    handoff_is_closed,
    handoff_is_open,
)
from handoff.models import CheckIn, CheckInType, Handoff


def test_latest_check_in_returns_none_for_empty_check_in_trail() -> None:
    """Empty check-in trails should have no latest check-in."""
    handoff = Handoff(project_id=1, need_back="No history yet")
    handoff.check_ins = []

    assert _latest_check_in(handoff) is None


def test_latest_check_in_prefers_date_then_created_at_then_id() -> None:
    """Latest check-in ordering should be deterministic across tie-breakers."""
    handoff = Handoff(project_id=1, need_back="Ordering")
    same_day = date(2026, 3, 11)
    morning = datetime(2026, 3, 11, 9, 0, tzinfo=UTC)
    afternoon = datetime(2026, 3, 11, 12, 0, tzinfo=UTC)

    older_date = CheckIn(
        id=99,
        handoff_id=1,
        check_in_date=date(2026, 3, 10),
        check_in_type=CheckInType.CONCLUDED,
        created_at=afternoon,
    )
    newer_created_at = CheckIn(
        id=1,
        handoff_id=1,
        check_in_date=same_day,
        check_in_type=CheckInType.DELAYED,
        created_at=afternoon,
    )
    higher_id_on_tie = CheckIn(
        id=3,
        handoff_id=1,
        check_in_date=same_day,
        check_in_type=CheckInType.ON_TRACK,
        created_at=afternoon,
    )
    lower_id_on_tie = CheckIn(
        id=2,
        handoff_id=1,
        check_in_date=same_day,
        check_in_type=CheckInType.CONCLUDED,
        created_at=afternoon,
    )
    older_created_at = CheckIn(
        id=100,
        handoff_id=1,
        check_in_date=same_day,
        check_in_type=CheckInType.CONCLUDED,
        created_at=morning,
    )
    handoff.check_ins = [
        older_date,
        newer_created_at,
        lower_id_on_tie,
        higher_id_on_tie,
        older_created_at,
    ]

    latest = _latest_check_in(handoff)

    assert latest is not None
    assert latest.id == higher_id_on_tie.id
    assert latest.check_in_type == CheckInType.ON_TRACK


def test_handoff_open_closed_helpers_follow_latest_check_in() -> None:
    """Open/closed status should be derived from the latest check-in only."""
    handoff = Handoff(project_id=1, need_back="Status")
    handoff.check_ins = []
    assert handoff_is_open(handoff) is True
    assert handoff_is_closed(handoff) is False

    handoff.check_ins = [
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 10),
            check_in_type=CheckInType.CONCLUDED,
        ),
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 11),
            check_in_type=CheckInType.ON_TRACK,
        ),
    ]
    assert handoff_is_open(handoff) is True
    assert handoff_is_closed(handoff) is False

    handoff.check_ins = [
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 10),
            check_in_type=CheckInType.ON_TRACK,
        ),
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 11),
            check_in_type=CheckInType.CONCLUDED,
        ),
    ]
    assert handoff_is_open(handoff) is False
    assert handoff_is_closed(handoff) is True


def test_get_handoff_close_date_uses_latest_concluded_even_after_reopen() -> None:
    """Close date should reflect the most recent concluded check-in, not latest status."""
    handoff = Handoff(project_id=1, need_back="Reopened")
    handoff.check_ins = [
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 5),
            check_in_type=CheckInType.CONCLUDED,
        ),
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 7),
            check_in_type=CheckInType.CONCLUDED,
        ),
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 9),
            check_in_type=CheckInType.ON_TRACK,
        ),
    ]

    assert get_handoff_close_date(handoff) == date(2026, 3, 7)
