"""Tests for todo service layer (query_now_items, snooze_todo, create_todo)."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import handoff.data as data
from handoff.models import Project, TodoStatus
from handoff.services import create_todo, query_now_items, snooze_todo


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


def test_service_create_todo_with_next_check(session, monkeypatch) -> None:
    """create_todo passes next_check through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    todo = create_todo(
        project_id=p.id,
        name="Follow up",
        next_check=date(2026, 1, 15),
        helper="Alice",
    )
    assert todo.id is not None
    assert todo.next_check == date(2026, 1, 15)
    assert todo.helper == "Alice"


def test_service_query_now_items(session, monkeypatch) -> None:
    """query_now_items returns open items through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_todo(
        project_id=p.id,
        name="Due",
        next_check=date(2000, 1, 1),
        status=TodoStatus.HANDOFF,
    )
    data.create_todo(
        project_id=p.id,
        name="Later",
        next_check=date(2030, 1, 1),
        status=TodoStatus.HANDOFF,
    )

    results = query_now_items()
    assert len(results) >= 1
    names = [r[0].name for r in results]
    assert "Due" in names


def test_service_snooze_todo(session, monkeypatch) -> None:
    """snooze_todo updates next_check through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    todo = data.create_todo(
        project_id=p.id,
        name="Snooze me",
        next_check=date(2025, 1, 1),
        status=TodoStatus.HANDOFF,
    )
    assert todo.id is not None

    updated = snooze_todo(todo.id, to_date=date(2026, 1, 15))
    assert updated is not None
    assert updated.next_check == date(2026, 1, 15)
