"""Tests for settings service layer (get_export_payload, import_payload)."""

from __future__ import annotations

from contextlib import contextmanager

from sqlmodel import select

import handoff.data as data
from handoff.models import Project, Todo, TodoStatus
from handoff.services import settings_service


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


def test_get_export_payload_via_service(session, monkeypatch) -> None:
    """get_export_payload returns backup dict through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="P"))
    session.commit()
    payload = settings_service.get_export_payload()
    assert "projects" in payload
    assert "todos" in payload
    assert isinstance(payload["projects"], list)
    assert isinstance(payload["todos"], list)
    assert len(payload["projects"]) == 1
    assert payload["projects"][0]["name"] == "P"


def test_import_payload_via_service(session, monkeypatch) -> None:
    """import_payload replaces data through the service boundary."""
    _patch_session_context(monkeypatch, session)
    payload = {
        "projects": [
            {
                "id": 1,
                "name": "Imported",
                "created_at": "2026-03-01T00:00:00",
                "is_archived": False,
            },
        ],
        "todos": [
            {
                "id": 1,
                "project_id": 1,
                "name": "Imported todo",
                "status": "handoff",
                "next_check": "2026-04-01",
                "deadline": None,
                "helper": "Alice",
                "notes": "",
                "created_at": "2026-03-01T00:00:00",
                "completed_at": None,
                "is_archived": False,
            },
        ],
    }
    settings_service.import_payload(payload)
    projects = list(session.exec(select(Project)).all())
    todos = list(session.exec(select(Todo)).all())
    assert len(projects) == 1
    assert projects[0].name == "Imported"
    assert len(todos) == 1
    assert todos[0].name == "Imported todo"
    assert todos[0].status == TodoStatus.HANDOFF
