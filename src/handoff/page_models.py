"""Typed page-facing contracts shared by UI modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime

from .models import Todo, TodoStatus


def _require_todo_id(value: int | None) -> int:
    """Return a persisted todo id or raise a clear error."""
    if value is None:
        raise ValueError("Todo rows require persisted todos with ids.")
    return value


@dataclass(slots=True, frozen=True)
class TodoQuery:
    """Interface-neutral query contract for listing todos."""

    search_text: str = ""
    statuses: tuple[TodoStatus, ...] = ()
    project_ids: tuple[int, ...] = ()
    helper_names: tuple[str, ...] = ()
    deadline_start: date | None = None
    deadline_end: date | None = None
    include_archived: bool = False


@dataclass(slots=True, frozen=True)
class TodoRow:
    """Stable display shape for editable todo rows."""

    todo_id: int
    project_id: int
    project_name: str
    name: str
    status: TodoStatus
    helper: str
    deadline: date | None
    notes: str
    created_at: datetime

    @classmethod
    def from_todo(cls, todo: Todo) -> TodoRow:
        """Build a page row from an ORM todo with its project loaded."""
        return cls(
            todo_id=_require_todo_id(todo.id),
            project_id=todo.project_id,
            project_name=todo.project.name if todo.project else "",
            name=todo.name,
            status=todo.status,
            helper=(todo.helper or "").strip(),
            deadline=todo.deadline,
            notes=todo.notes or "",
            created_at=todo.created_at,
        )


@dataclass(slots=True, frozen=True)
class TodoMutationDefaults:
    """Default values applied to newly inserted rows in the todos editor."""

    project_id: int | None
    project_name: str | None
    status: TodoStatus
    helper: str


@dataclass(slots=True, frozen=True)
class TodoUpdateInput:
    """Typed edit request derived from a Streamlit data editor delta."""

    todo_id: int
    project_id: int | None
    name: str | None
    status: TodoStatus | None
    deadline: date | None
    helper: str | None
    notes: str | None


@dataclass(slots=True, frozen=True)
class TodoCreateInput:
    """Typed create request derived from a Streamlit data editor delta."""

    project_id: int
    name: str
    status: TodoStatus
    deadline: date | None
    helper: str | None
    notes: str | None


@dataclass(slots=True, frozen=True)
class ProjectSummaryRow:
    """Stable display shape for the projects page."""

    project_id: int
    name: str
    is_archived: bool
    handoff: int
    done: int
    canceled: int


@dataclass(slots=True, frozen=True)
class ProjectRenameChange:
    """Rename request for a project row."""

    project_id: int
    new_name: str


@dataclass(slots=True, frozen=True)
class ProjectArchiveChange:
    """Archive/unarchive request for a project row."""

    project_id: int
    archive: bool
