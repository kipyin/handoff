"""Tests for backup_schema validation and serialization helpers."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from handoff.backup_schema import (
    BackupPayload,
    BackupProjectRecord,
    BackupTodoRecord,
    _require_model_id,
)
from handoff.models import Project, Todo, TodoStatus


def test_require_model_id_returns_value_when_present() -> None:
    assert _require_model_id(42, label="project") == 42


def test_require_model_id_raises_on_none() -> None:
    with pytest.raises(ValueError, match="Cannot serialize todo without a persisted id"):
        _require_model_id(None, label="todo")


class TestBackupProjectRecord:
    def test_from_dict_round_trip(self) -> None:
        raw = {
            "id": 1,
            "name": "Work",
            "created_at": "2026-01-15T10:30:00",
            "is_archived": True,
        }
        record = BackupProjectRecord.from_dict(raw)
        assert record.id == 1
        assert record.name == "Work"
        assert record.created_at == datetime(2026, 1, 15, 10, 30)
        assert record.is_archived is True

        d = record.to_dict()
        assert d["id"] == 1
        assert d["name"] == "Work"
        assert d["is_archived"] is True
        roundtripped = BackupProjectRecord.from_dict(d)
        assert roundtripped == record

    def test_from_dict_defaults_is_archived_false(self) -> None:
        raw = {"id": 2, "name": "Home", "created_at": "2026-02-01T00:00:00"}
        record = BackupProjectRecord.from_dict(raw)
        assert record.is_archived is False

    def test_from_model(self) -> None:
        project = Project(id=5, name="Side", created_at=datetime(2026, 3, 1), is_archived=True)
        record = BackupProjectRecord.from_model(project)
        assert record.id == 5
        assert record.name == "Side"
        assert record.is_archived is True

    def test_from_model_raises_on_none_id(self) -> None:
        project = Project(id=None, name="No ID", created_at=datetime(2026, 1, 1))
        with pytest.raises(ValueError, match="Cannot serialize project"):
            BackupProjectRecord.from_model(project)


class TestBackupTodoRecord:
    def test_from_dict_full(self) -> None:
        raw = {
            "id": 10,
            "project_id": 1,
            "name": "Fix bug",
            "status": "handoff",
            "deadline": "2026-04-01",
            "helper": "Alice",
            "notes": "Important",
            "created_at": "2026-03-01T09:00:00",
            "completed_at": "2026-03-15T17:00:00",
            "is_archived": False,
        }
        record = BackupTodoRecord.from_dict(raw)
        assert record.id == 10
        assert record.status == TodoStatus.HANDOFF
        assert record.deadline == date(2026, 4, 1)
        assert record.helper == "Alice"
        assert record.completed_at == datetime(2026, 3, 15, 17, 0)

    def test_from_dict_legacy_delegated_status(self) -> None:
        raw = {
            "id": 11,
            "project_id": 1,
            "name": "Old task",
            "status": "delegated",
            "created_at": "2026-01-01T00:00:00",
        }
        record = BackupTodoRecord.from_dict(raw)
        assert record.status == TodoStatus.HANDOFF

    def test_from_dict_null_optional_fields(self) -> None:
        raw = {
            "id": 12,
            "project_id": 1,
            "name": "Minimal",
            "status": "done",
            "created_at": "2026-01-01T00:00:00",
        }
        record = BackupTodoRecord.from_dict(raw)
        assert record.deadline is None
        assert record.helper is None
        assert record.notes is None
        assert record.completed_at is None

    def test_to_dict_round_trip(self) -> None:
        record = BackupTodoRecord(
            id=20,
            project_id=3,
            name="Task",
            status=TodoStatus.DONE,
            next_check=date(2026, 5, 15),
            deadline=date(2026, 6, 1),
            helper="Bob",
            notes="Done!",
            created_at=datetime(2026, 5, 1),
            completed_at=datetime(2026, 5, 30),
            is_archived=True,
        )
        d = record.to_dict()
        assert d["status"] == "done"
        assert d["deadline"] == "2026-06-01"
        assert d["completed_at"] == "2026-05-30T00:00:00"
        assert d["is_archived"] is True
        roundtripped = BackupTodoRecord.from_dict(d)
        assert roundtripped == record

    def test_to_dict_null_fields(self) -> None:
        record = BackupTodoRecord(
            id=21,
            project_id=1,
            name="Bare",
            status=TodoStatus.HANDOFF,
            next_check=None,
            deadline=None,
            helper=None,
            notes=None,
            created_at=datetime(2026, 1, 1),
            completed_at=None,
        )
        d = record.to_dict()
        assert d["deadline"] is None
        assert d["completed_at"] is None

    def test_from_model(self) -> None:
        todo = Todo(
            id=30,
            project_id=1,
            name="Test",
            status=TodoStatus.CANCELED,
            deadline=date(2026, 7, 1),
            helper="Carol",
            notes="cancelled",
            created_at=datetime(2026, 6, 1),
            completed_at=None,
            is_archived=False,
        )
        record = BackupTodoRecord.from_model(todo)
        assert record.id == 30
        assert record.status == TodoStatus.CANCELED

    def test_from_model_raises_on_none_id(self) -> None:
        todo = Todo(
            id=None,
            project_id=1,
            name="No ID",
            status=TodoStatus.HANDOFF,
            created_at=datetime(2026, 1, 1),
        )
        with pytest.raises(ValueError, match="Cannot serialize todo"):
            BackupTodoRecord.from_model(todo)


class TestBackupPayload:
    def test_from_dict_valid(self) -> None:
        raw = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "T",
                    "status": "handoff",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }
        payload = BackupPayload.from_dict(raw)
        assert len(payload.projects) == 1
        assert len(payload.todos) == 1

    def test_from_dict_rejects_non_dict(self) -> None:
        with pytest.raises(ValueError, match="must be a JSON object"):
            BackupPayload.from_dict("not a dict")  # type: ignore[arg-type]

    def test_from_dict_rejects_missing_keys(self) -> None:
        with pytest.raises(KeyError, match="projects.*todos"):
            BackupPayload.from_dict({"projects": []})

    def test_from_dict_rejects_non_list_values(self) -> None:
        with pytest.raises(ValueError, match="must both be lists"):
            BackupPayload.from_dict({"projects": "nope", "todos": "nope"})

    def test_to_dict_round_trip(self) -> None:
        raw = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "T",
                    "status": "handoff",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }
        payload = BackupPayload.from_dict(raw)
        d = payload.to_dict()
        assert len(d["projects"]) == 1
        assert len(d["todos"]) == 1
        roundtripped = BackupPayload.from_dict(d)
        assert roundtripped == payload

    def test_from_models(self) -> None:
        project = Project(id=1, name="P", created_at=datetime(2026, 1, 1), is_archived=False)
        todo = Todo(
            id=1,
            project_id=1,
            name="T",
            status=TodoStatus.HANDOFF,
            created_at=datetime(2026, 1, 1),
        )
        payload = BackupPayload.from_models([project], [todo])
        assert len(payload.projects) == 1
        assert len(payload.todos) == 1
        assert payload.projects[0].name == "P"
        assert payload.todos[0].name == "T"
