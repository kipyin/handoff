"""Tests for backup_schema validation and serialization helpers."""

from __future__ import annotations

from datetime import date, datetime

import pytest

from handoff.backup_schema import (
    BackupCheckInRecord,
    BackupHandoffRecord,
    BackupPayload,
    BackupProjectRecord,
    _require_model_id,
)
from handoff.models import CheckIn, CheckInType, Handoff, Project


def test_require_model_id_returns_value_when_present() -> None:
    assert _require_model_id(42, label="project") == 42


def test_require_model_id_raises_on_none() -> None:
    with pytest.raises(ValueError, match="Cannot serialize handoff without a persisted id"):
        _require_model_id(None, label="handoff")


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


class TestBackupHandoffRecord:
    def test_from_dict_full(self) -> None:
        raw = {
            "id": 10,
            "project_id": 1,
            "need_back": "Fix bug",
            "deadline": "2026-04-01",
            "pitchman": "Alice",
            "notes": "Important",
            "created_at": "2026-03-01T09:00:00",
        }
        record = BackupHandoffRecord.from_dict(raw)
        assert record.id == 10
        assert record.need_back == "Fix bug"
        assert record.deadline == date(2026, 4, 1)
        assert record.pitchman == "Alice"

    def test_from_dict_null_optional_fields(self) -> None:
        raw = {
            "id": 12,
            "project_id": 1,
            "need_back": "Minimal",
            "created_at": "2026-01-01T00:00:00",
        }
        record = BackupHandoffRecord.from_dict(raw)
        assert record.deadline is None
        assert record.pitchman is None
        assert record.notes is None

    def test_to_dict_round_trip(self) -> None:
        record = BackupHandoffRecord(
            id=20,
            project_id=3,
            need_back="Task",
            pitchman="Bob",
            next_check=date(2026, 5, 15),
            deadline=date(2026, 6, 1),
            notes="Done!",
            created_at=datetime(2026, 5, 1),
        )
        d = record.to_dict()
        assert d["deadline"] == "2026-06-01"
        roundtripped = BackupHandoffRecord.from_dict(d)
        assert roundtripped == record

    def test_to_dict_null_fields(self) -> None:
        record = BackupHandoffRecord(
            id=21,
            project_id=1,
            need_back="Bare",
            pitchman=None,
            next_check=None,
            deadline=None,
            notes=None,
            created_at=datetime(2026, 1, 1),
        )
        d = record.to_dict()
        assert d["deadline"] is None
        assert d["pitchman"] is None

    def test_from_model(self) -> None:
        handoff = Handoff(
            id=30,
            project_id=1,
            need_back="Test",
            pitchman="Carol",
            deadline=date(2026, 7, 1),
            notes="testing",
            created_at=datetime(2026, 6, 1),
        )
        record = BackupHandoffRecord.from_model(handoff)
        assert record.id == 30
        assert record.need_back == "Test"

    def test_from_model_raises_on_none_id(self) -> None:
        handoff = Handoff(
            id=None,
            project_id=1,
            need_back="No ID",
            created_at=datetime(2026, 1, 1),
        )
        with pytest.raises(ValueError, match="Cannot serialize handoff"):
            BackupHandoffRecord.from_model(handoff)


class TestBackupCheckInRecord:
    def test_from_dict_round_trip(self) -> None:
        raw = {
            "id": 1,
            "handoff_id": 10,
            "check_in_date": "2026-03-01",
            "note": "All good",
            "check_in_type": "on_track",
            "created_at": "2026-03-01T09:00:00",
        }
        record = BackupCheckInRecord.from_dict(raw)
        assert record.id == 1
        assert record.check_in_type == CheckInType.ON_TRACK
        assert record.check_in_date == date(2026, 3, 1)

        d = record.to_dict()
        roundtripped = BackupCheckInRecord.from_dict(d)
        assert roundtripped == record

    def test_from_model(self) -> None:
        ci = CheckIn(
            id=5,
            handoff_id=10,
            check_in_date=date(2026, 3, 5),
            check_in_type=CheckInType.CONCLUDED,
            note="Done",
            created_at=datetime(2026, 3, 5),
        )
        record = BackupCheckInRecord.from_model(ci)
        assert record.id == 5
        assert record.check_in_type == CheckInType.CONCLUDED


class TestBackupPayload:
    def test_from_dict_valid(self) -> None:
        raw = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "handoffs": [
                {
                    "id": 1,
                    "project_id": 1,
                    "need_back": "T",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
            "check_ins": [],
        }
        payload = BackupPayload.from_dict(raw)
        assert len(payload.projects) == 1
        assert len(payload.handoffs) == 1
        assert len(payload.check_ins) == 0

    def test_from_dict_rejects_non_dict(self) -> None:
        with pytest.raises(ValueError, match="must be a JSON object"):
            BackupPayload.from_dict("not a dict")  # type: ignore[arg-type]

    def test_from_dict_rejects_missing_keys(self) -> None:
        with pytest.raises(KeyError, match=r"projects.*handoffs"):
            BackupPayload.from_dict({"projects": []})

    def test_from_dict_rejects_non_list_values(self) -> None:
        with pytest.raises(ValueError, match="must be a list"):
            BackupPayload.from_dict({"projects": "nope", "handoffs": "nope"})

    def test_to_dict_round_trip(self) -> None:
        raw = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "handoffs": [
                {
                    "id": 1,
                    "project_id": 1,
                    "need_back": "T",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
            "check_ins": [],
        }
        payload = BackupPayload.from_dict(raw)
        d = payload.to_dict()
        assert len(d["projects"]) == 1
        assert len(d["handoffs"]) == 1
        roundtripped = BackupPayload.from_dict(d)
        assert roundtripped == payload

    def test_from_models(self) -> None:
        project = Project(id=1, name="P", created_at=datetime(2026, 1, 1), is_archived=False)
        handoff = Handoff(
            id=1,
            project_id=1,
            need_back="T",
            created_at=datetime(2026, 1, 1),
        )
        ci = CheckIn(
            id=1,
            handoff_id=1,
            check_in_date=date(2026, 1, 5),
            check_in_type=CheckInType.ON_TRACK,
            created_at=datetime(2026, 1, 5),
        )
        payload = BackupPayload.from_models([project], [handoff], [ci])
        assert len(payload.projects) == 1
        assert len(payload.handoffs) == 1
        assert len(payload.check_ins) == 1
        assert payload.handoffs[0].need_back == "T"

    def test_legacy_todo_format(self) -> None:
        """Legacy 'todos' key is converted to handoffs and check-ins."""
        raw = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "Done task",
                    "status": "done",
                    "helper": "Alice",
                    "created_at": "2026-01-01T00:00:00",
                    "completed_at": "2026-01-15T00:00:00",
                },
                {
                    "id": 2,
                    "project_id": 1,
                    "name": "Open task",
                    "status": "handoff",
                    "helper": "Bob",
                    "created_at": "2026-01-01T00:00:00",
                },
            ],
        }
        payload = BackupPayload.from_dict(raw)
        assert len(payload.handoffs) == 2
        assert payload.handoffs[0].need_back == "Done task"
        assert payload.handoffs[0].pitchman == "Alice"
        assert len(payload.check_ins) == 1
        assert payload.check_ins[0].check_in_type == CheckInType.CONCLUDED
