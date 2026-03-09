"""Tests for handoff service layer."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import handoff.data as data
from handoff.models import CheckInType, Handoff, Project
from handoff.services import add_check_in, create_handoff, query_action_handoffs, snooze_handoff


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


def test_service_create_handoff_with_next_check(session, monkeypatch) -> None:
    """create_handoff passes next_check through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = create_handoff(
        project_id=p.id,
        need_back="Follow up",
        next_check=date(2026, 1, 15),
        pitchman="Alice",
    )
    assert handoff.id is not None
    assert handoff.next_check == date(2026, 1, 15)
    assert handoff.pitchman == "Alice"


def test_service_query_action_handoffs(session, monkeypatch) -> None:
    """query_action_handoffs returns due open handoffs through the service boundary."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr(data, "date", FixedDate)

    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(
        project_id=p.id,
        need_back="Due",
        next_check=date(2000, 1, 1),
    )
    data.create_handoff(
        project_id=p.id,
        need_back="Later",
        next_check=date(2030, 1, 1),
    )

    results = query_action_handoffs()
    names = [r.need_back for r in results]
    assert "Due" in names
    assert "Later" not in names


def test_service_snooze_handoff(session, monkeypatch) -> None:
    """snooze_handoff updates next_check through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(
        project_id=p.id,
        need_back="Snooze me",
        next_check=date(2025, 1, 1),
    )
    assert handoff.id is not None

    updated = snooze_handoff(handoff.id, to_date=date(2026, 1, 15))
    assert updated is not None
    assert updated.next_check == date(2026, 1, 15)


def test_service_add_check_in_updates_next_check(session, monkeypatch) -> None:
    """add_check_in creates a check-in and updates handoff.next_check."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = create_handoff(
        project_id=p.id,
        need_back="Follow-up needed",
        next_check=date(2026, 3, 9),
    )
    assert handoff.id is not None

    check_in = add_check_in(
        handoff.id,
        check_in_type=CheckInType.ON_TRACK,
        note="Looks good",
        next_check_date=date(2026, 3, 16),
        check_in_date=date(2026, 3, 9),
    )
    assert check_in.check_in_type == CheckInType.ON_TRACK
    refreshed = session.get(Handoff, handoff.id)
    assert refreshed is not None
    assert refreshed.next_check == date(2026, 3, 16)
