"""Validation and serialization helpers for backup payloads."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from .models import Project, Todo, TodoStatus


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
class BackupTodoRecord:
    """Validated serialized todo row."""

    id: int
    project_id: int
    name: str
    status: TodoStatus
    next_check: date | None
    deadline: date | None
    helper: str | None
    notes: str | None
    created_at: datetime
    completed_at: datetime | None
    is_archived: bool = False

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BackupTodoRecord:
        """Parse a todo record from JSON-like input."""
        raw_status = str(raw["status"])
        if raw_status == "delegated":
            raw_status = TodoStatus.HANDOFF.value
        helper = raw.get("helper")
        notes = raw.get("notes")
        return cls(
            id=int(raw["id"]),
            project_id=int(raw["project_id"]),
            name=str(raw["name"]),
            status=TodoStatus(raw_status),
            next_check=(
                date.fromisoformat(str(raw["next_check"])) if raw.get("next_check") else None
            ),
            deadline=date.fromisoformat(str(raw["deadline"])) if raw.get("deadline") else None,
            helper=str(helper) if helper is not None else None,
            notes=str(notes) if notes is not None else None,
            created_at=datetime.fromisoformat(str(raw["created_at"])),
            completed_at=(
                datetime.fromisoformat(str(raw["completed_at"]))
                if raw.get("completed_at")
                else None
            ),
            is_archived=bool(raw.get("is_archived", False)),
        )

    @classmethod
    def from_model(cls, todo: Todo) -> BackupTodoRecord:
        """Serialize a live todo model."""
        return cls(
            id=_require_model_id(todo.id, label="todo"),
            project_id=todo.project_id,
            name=todo.name,
            status=todo.status,
            next_check=todo.next_check,
            deadline=todo.deadline,
            helper=todo.helper,
            notes=todo.notes,
            created_at=todo.created_at,
            completed_at=todo.completed_at,
            is_archived=todo.is_archived,
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable representation."""
        return {
            "id": self.id,
            "project_id": self.project_id,
            "name": self.name,
            "status": self.status.value,
            "next_check": self.next_check.isoformat() if self.next_check else None,
            "deadline": self.deadline.isoformat() if self.deadline else None,
            "helper": self.helper,
            "notes": self.notes,
            "created_at": self.created_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "is_archived": self.is_archived,
        }


@dataclass(slots=True, frozen=True)
class BackupPayload:
    """Validated backup payload."""

    projects: tuple[BackupProjectRecord, ...]
    todos: tuple[BackupTodoRecord, ...]

    @classmethod
    def from_dict(cls, raw: dict[str, Any]) -> BackupPayload:
        """Validate a JSON-like backup payload before any destructive write."""
        if not isinstance(raw, dict):
            raise ValueError("Backup payload must be a JSON object.")
        if "projects" not in raw or "todos" not in raw:
            raise KeyError("Backup payload must contain 'projects' and 'todos'.")
        projects_raw = raw["projects"]
        todos_raw = raw["todos"]
        if not isinstance(projects_raw, list) or not isinstance(todos_raw, list):
            raise ValueError("'projects' and 'todos' must both be lists.")
        return cls(
            projects=tuple(BackupProjectRecord.from_dict(item) for item in projects_raw),
            todos=tuple(BackupTodoRecord.from_dict(item) for item in todos_raw),
        )

    @classmethod
    def from_models(cls, projects: list[Project], todos: list[Todo]) -> BackupPayload:
        """Build a validated payload from live ORM models."""
        return cls(
            projects=tuple(BackupProjectRecord.from_model(project) for project in projects),
            todos=tuple(BackupTodoRecord.from_model(todo) for todo in todos),
        )

    def to_dict(self) -> dict[str, Any]:
        """Return a JSON-serializable backup payload."""
        return {
            "projects": [project.to_dict() for project in self.projects],
            "todos": [todo.to_dict() for todo in self.todos],
        }
