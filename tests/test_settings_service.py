"""Tests for settings service layer (get_export_payload, import_payload, deadline_near_days)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlmodel import select

import handoff.data as data
from handoff.models import Project, Todo, TodoStatus
from handoff.services import settings_service


def _patch_settings_path(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    """Patch settings path so tests use a controlled file."""
    settings_path = path / "handoff_settings.json"

    def _get_path() -> Path:
        return settings_path

    monkeypatch.setattr(settings_service, "_get_settings_path", _get_path)


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


# --- deadline_near_days persistence ---


def test_get_deadline_near_days_missing_file_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When settings file does not exist, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    assert not (tmp_path / "handoff_settings.json").exists()
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_invalid_json_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When settings file has invalid JSON, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text("not valid json {", encoding="utf-8")
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_non_int_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When deadline_near_days is not an int, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text(
        '{"deadline_near_days": "seven"}', encoding="utf-8"
    )
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_out_of_range_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When value is outside min/max, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text('{"deadline_near_days": 99}', encoding="utf-8")
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_valid_returns_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When value is valid, return it."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text('{"deadline_near_days": 3}', encoding="utf-8")
    assert settings_service.get_deadline_near_days() == 3


def test_set_deadline_near_days_clamps_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_deadline_near_days clamps to min/max and persists."""
    _patch_settings_path(monkeypatch, tmp_path)

    settings_service.set_deadline_near_days(0)
    assert settings_service.get_deadline_near_days() == 1

    settings_service.set_deadline_near_days(99)
    assert settings_service.get_deadline_near_days() == 14

    settings_service.set_deadline_near_days(5)
    assert settings_service.get_deadline_near_days() == 5
    assert (tmp_path / "handoff_settings.json").read_text(encoding="utf-8") == (
        '{\n  "deadline_near_days": 5\n}'
    )
