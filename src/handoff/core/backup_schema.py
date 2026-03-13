"""Validation and serialization helpers for backup payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from handoff.core.models import CheckIn, CheckInType, Handoff, Project


def _require_model_id(value: int | None, *, label: str) -> int:
    """Return a non-null model id or raise a helpful error."""
    if value is None:
        raise ValueError(f"Cannot serialize {label} without a persisted id.")
    return value


@dataclass(slots=True, frozen=True)
class BackupProjectRecord:
    """Validated serialized project row."""

    id: int
    name: str
    created_at: datetime
    is_archived: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BackupProjectRecord:
        """Parse a project record from JSON-like input."""
        return cls(
            id=int(raw["id"]),
            name=str(raw["name"]),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
            is_archived=bool(raw.get("is_archived", False)),
        )

    @classmethod
    def from_model(cls, project: Project) -> BackupProjectRecord:
        """Serialize a live project model."""
        return cls(
            id=_require_model_id(project.id, label="project"),
            name=project.name,
            created_at=project.created_at,
            is_archived=project.is_archived,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "name": self.name,
            "created_at": self.created_at.isoformat(),
            "is_archived": self.is_archived,
        }


@dataclass(slots=True, frozen=True)
class BackupHandoffRecord:
    """Validated serialized handoff row."""

    id: int
    project_id: int
    need_back: str
    pitchman: str | None
    next_check: date | None
    deadline: date | None
    notes: str | None
    created_at: datetime

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BackupHandoffRecord:
        """Parse a handoff record from JSON-like input."""
        pitchman = raw.get("pitchman")
        notes = raw.get("notes")
        return cls(
            id=int(raw["id"]),
            project_id=int(raw["project_id"]),
            need_back=str(raw["need_back"]),
            pitchman=str(pitchman) if pitchman is not None else None,
            next_check=(
                date.fromisoformat(str(raw["next_check"])) if raw.get("next_check") else None
            ),
            deadline=date.fromisoformat(str(raw["deadline"])) if raw.get("deadline") else None,
            notes=str(notes) if notes is not None else None,
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )

    @classmethod
    def from_model(cls, handoff: Handoff) -> BackupHandoffRecord:
        """Serialize a live handoff model."""
        return cls(
            id=_require_model_id(handoff.id, label="handoff"),
            project_id=handoff.project_id,
            need_back=handoff.need_back,
            pitchman=handoff.pitchman,
            next_check=handoff.next_check,
            deadline=handoff.deadline,
            notes=handoff.notes,
            created_at=handoff.created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "need_back": self.need_back,
            "pitchman": self.pitchman,
            "next_check": self.next_check.isoformat() if self.next_check else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
        }


@dataclass(slots=True, frozen=True)
class BackupCheckInRecord:
    """Validated serialized check-in row."""

    id: int
    handoff_id: int
    check_in_date: date
    note: str | None
    check_in_type: CheckInType
    created_at: datetime

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BackupCheckInRecord:
        """Parse a check-in record from JSON-like input."""
        note = raw.get("note")
        return cls(
            id=int(raw["id"]),
            handoff_id=int(raw["handoff_id"]),
            check_in_date=date.fromisoformat(str(raw["check_in_date"])),
            note=str(note) if note is not None else None,
            check_in_type=CheckInType(str(raw["check_in_type"])),
            created_at=datetime.fromisoformat(str(raw["created_at"])),
        )

    @classmethod
    def from_model(cls, check_in: CheckIn) -> BackupCheckInRecord:
        """Serialize a live check-in model."""
        return cls(
            id=_require_model_id(check_in.id, label="check_in"),
            handoff_id=check_in.handoff_id,
            check_in_date=check_in.check_in_date,
            note=check_in.note,
            check_in_type=check_in.check_in_type,
            created_at=check_in.created_at,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "handoff_id": self.handoff_id,
            "check_in_date": self.check_in_date.isoformat(),
            "note": self.note,
            "check_in_type": self.check_in_type.value,
            "created_at": self.created_at.isoformat(),
        }


def _legacy_todo_to_handoff_record(raw: dict[str, Any]) -> BackupHandoffRecord:
    """Convert a legacy todo dict to a BackupHandoffRecord."""
    return BackupHandoffRecord(
        id=int(raw["id"]),
        project_id=int(raw["project_id"]),
        need_back=str(raw["name"]),
        pitchman=str(raw["helper"]) if raw.get("helper") is not None else None,
        next_check=(date.fromisoformat(str(raw["next_check"])) if raw.get("next_check") else None),
        deadline=date.fromisoformat(str(raw["deadline"])) if raw.get("deadline") else None,
        notes=str(raw["notes"]) if raw.get("notes") is not None else None,
        created_at=datetime.fromisoformat(str(raw["created_at"])),
    )


def _legacy_todo_to_check_in(
    raw: dict[str, Any], *, check_in_id: int
) -> BackupCheckInRecord | None:
    """If a legacy todo is done/canceled, produce a concluded check-in record."""
    status = str(raw.get("status", "")).lower()
    if status not in ("done", "canceled"):
        return None
    completed_at_str = raw.get("completed_at")
    if completed_at_str:
        created_at = datetime.fromisoformat(str(completed_at_str))
        ci_date = created_at.date()
    else:
        created_at = datetime.fromisoformat(str(raw["created_at"]))
        ci_date = created_at.date()
    note = "canceled" if status == "canceled" else None
    return BackupCheckInRecord(
        id=check_in_id,
        handoff_id=int(raw["id"]),
        check_in_date=ci_date,
        note=note,
        check_in_type=CheckInType.CONCLUDED,
        created_at=created_at,
    )


@dataclass(slots=True, frozen=True)
class BackupPayload:
    """Validated backup payload."""

    projects: tuple[BackupProjectRecord, ...]
    handoffs: tuple[BackupHandoffRecord, ...]
    check_ins: tuple[BackupCheckInRecord, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BackupPayload:
        """Validate a JSON-like backup payload before any destructive write.

        Accepts both the new format (``handoffs`` + ``check_ins``) and the
        legacy format (``todos``).
        """
        if not isinstance(raw, dict):
            raise ValueError("Backup payload must be a JSON object.")
        if "projects" not in raw:
            raise KeyError("Backup payload must contain 'projects' and 'handoffs' (or 'todos').")
        projects_raw = raw["projects"]
        if not isinstance(projects_raw, list):
            raise ValueError("'projects' must be a list.")

        if "handoffs" in raw:
            handoffs_raw = raw["handoffs"]
            check_ins_raw = raw.get("check_ins", [])
            if not isinstance(handoffs_raw, list) or not isinstance(check_ins_raw, list):
                raise ValueError("'handoffs' and 'check_ins' must both be lists.")
            return cls(
                projects=tuple(BackupProjectRecord.from_dict(item) for item in projects_raw),
                handoffs=tuple(BackupHandoffRecord.from_dict(item) for item in handoffs_raw),
                check_ins=tuple(BackupCheckInRecord.from_dict(item) for item in check_ins_raw),
            )

        if "todos" in raw:
            todos_raw = raw["todos"]
            if not isinstance(todos_raw, list):
                raise ValueError("'todos' must be a list.")
            handoffs = []
            check_ins = []
            ci_id = 1
            for todo_raw in todos_raw:
                handoffs.append(_legacy_todo_to_handoff_record(todo_raw))
                ci = _legacy_todo_to_check_in(todo_raw, check_in_id=ci_id)
                if ci is not None:
                    check_ins.append(ci)
                    ci_id += 1
            return cls(
                projects=tuple(BackupProjectRecord.from_dict(item) for item in projects_raw),
                handoffs=tuple(handoffs),
                check_ins=tuple(check_ins),
            )

        raise KeyError("Backup payload must contain 'projects' and 'handoffs' (or 'todos').")

    @classmethod
    def from_models(
        cls,
        projects: list[Project],
        handoffs: list[Handoff],
        check_ins: list[CheckIn],
    ) -> BackupPayload:
        """Build a validated payload from live ORM models."""
        return cls(
            projects=tuple(BackupProjectRecord.from_model(project) for project in projects),
            handoffs=tuple(BackupHandoffRecord.from_model(handoff) for handoff in handoffs),
            check_ins=tuple(BackupCheckInRecord.from_model(ci) for ci in check_ins),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable backup payload."""
        return {
            "projects": [project.to_dict() for project in self.projects],
            "handoffs": [handoff.to_dict() for handoff in self.handoffs],
            "check_ins": [ci.to_dict() for ci in self.check_ins],
        }
