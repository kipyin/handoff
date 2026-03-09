"""Tests for handoff service layer (query_now_items, snooze_handoff, create_handoff)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import handoff.data as data
from handoff.models import Project
from handoff.services import create_handoff, query_now_items, snooze_handoff


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


def test_service_query_now_items(session, monkeypatch) -> None:
    """query_now_items returns open items through the service boundary."""
    _patch_session_context(monkeypatch, session)
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

    results = query_now_items()
    assert len(results) >= 1
    names = [r[0].need_back for r in results]
    assert "Due" in names


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
