"""Typed page-facing contracts shared by UI modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from .models import TodoStatus


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
