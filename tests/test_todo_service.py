"""Tests for handoff service layer."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import handoff.data as data
from handoff.models import CheckInType, Handoff, Project
from handoff.services import (
    add_check_in,
    conclude_handoff,
    create_handoff,
    delete_handoff,
    get_handoff_close_date,
    list_pitchmen,
    list_pitchmen_with_open_handoffs,
    query_action_handoffs,
    query_concluded_handoffs,
    query_handoffs,
    query_now_items,
    query_risk_handoffs,
    query_upcoming_handoffs,
    snooze_handoff,
    update_handoff,
)


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


def test_service_update_handoff(session, monkeypatch) -> None:
    """update_handoff persists field changes through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(project_id=p.id, need_back="Original")
    assert handoff.id is not None

    updated = update_handoff(handoff.id, need_back="Updated")
    assert updated is not None
    assert updated.need_back == "Updated"


def test_service_delete_handoff(session, monkeypatch) -> None:
    """delete_handoff removes the handoff through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(project_id=p.id, need_back="To delete")
    assert handoff.id is not None

    result = delete_handoff(handoff.id)
    assert result is True
    assert session.get(Handoff, handoff.id) is None


def test_service_query_handoffs(session, monkeypatch) -> None:
    """query_handoffs returns matching handoffs through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h1 = data.create_handoff(project_id=p.id, need_back="Alpha")
    h2 = data.create_handoff(project_id=p.id, need_back="Beta")
    assert h1.id is not None
    assert h2.id is not None

    results = query_handoffs(project_ids=[p.id])
    names = [r.need_back for r in results]
    assert "Alpha" in names
    assert "Beta" in names


def test_service_list_pitchmen(session, monkeypatch) -> None:
    """list_pitchmen returns all distinct pitchman names."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(project_id=p.id, need_back="A", pitchman="Alice")
    data.create_handoff(project_id=p.id, need_back="B", pitchman="Bob")

    names = list_pitchmen()
    assert "Alice" in names
    assert "Bob" in names


def test_service_list_pitchmen_with_open_handoffs(session, monkeypatch) -> None:
    """list_pitchmen_with_open_handoffs returns only pitchmen with open handoffs."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(project_id=p.id, need_back="Open", pitchman="Alice")

    names = list_pitchmen_with_open_handoffs()
    assert "Alice" in names


def test_service_query_now_items(session, monkeypatch) -> None:
    """query_now_items returns due open handoffs through the service boundary."""
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

    data.create_handoff(project_id=p.id, need_back="Due", next_check=date(2000, 1, 1))
    data.create_handoff(project_id=p.id, need_back="Later", next_check=date(2030, 1, 1))

    results = query_now_items()
    names = [h.need_back for h, _ in results]
    assert "Due" in names
    assert "Later" not in names


def test_service_query_risk_handoffs(session, monkeypatch) -> None:
    """query_risk_handoffs returns at-risk handoffs through the service boundary."""
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

    # At-risk: deadline within 1 day AND latest check-in is DELAYED.
    h = data.create_handoff(
        project_id=p.id,
        need_back="At risk",
        next_check=date(2000, 1, 1),
        deadline=date(2026, 3, 9),
    )
    assert h.id is not None
    data.create_check_in(
        handoff_id=h.id,
        check_in_type=CheckInType.DELAYED,
        check_in_date=date(2026, 3, 9),
    )

    results = query_risk_handoffs(deadline_near_days=1)
    names = [r.need_back for r in results]
    assert "At risk" in names


def test_service_query_upcoming_handoffs(session, monkeypatch) -> None:
    """query_upcoming_handoffs returns handoffs with future next_check."""
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

    data.create_handoff(project_id=p.id, need_back="Upcoming", next_check=date(2026, 4, 1))
    data.create_handoff(project_id=p.id, need_back="Overdue", next_check=date(2000, 1, 1))

    results = query_upcoming_handoffs()
    names = [r.need_back for r in results]
    assert "Upcoming" in names
    assert "Overdue" not in names


def test_service_query_concluded_handoffs(session, monkeypatch) -> None:
    """query_concluded_handoffs returns handoffs with a concluded check-in."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = data.create_handoff(project_id=p.id, need_back="Conclude me")
    assert h.id is not None
    data.conclude_handoff(h.id)

    results = query_concluded_handoffs()
    names = [r.need_back for r in results]
    assert "Conclude me" in names


def test_service_conclude_handoff(session, monkeypatch) -> None:
    """conclude_handoff creates a concluded check-in through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = data.create_handoff(project_id=p.id, need_back="Wrap up")
    assert h.id is not None

    check_in = conclude_handoff(h.id, note="All done.")
    assert check_in.check_in_type == CheckInType.CONCLUDED
    assert check_in.note == "All done."


def test_service_get_handoff_close_date(session, monkeypatch) -> None:
    """get_handoff_close_date returns the conclusion date for a closed handoff."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = data.create_handoff(project_id=p.id, need_back="Close me")
    assert h.id is not None
    data.conclude_handoff(h.id)
    refreshed = session.get(Handoff, h.id)
    assert refreshed is not None

    close_date = get_handoff_close_date(refreshed)
    assert close_date == date.today()
