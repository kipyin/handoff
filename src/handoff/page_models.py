"""Typed page-facing contracts shared by UI modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date


@dataclass(slots=True, frozen=True)
class HandoffQuery:
    """Interface-neutral query contract for listing handoffs."""

    search_text: str = ""
    project_ids: tuple[int, ...] = ()
    pitchman_names: tuple[str, ...] = ()
    deadline_start: date | None = None
    deadline_end: date | None = None
    include_concluded: bool = False
    include_archived_projects: bool = False


@dataclass(slots=True, frozen=True)
class ProjectSummaryRow:
    """Stable display shape for the projects page."""

    project_id: int
    name: str
    is_archived: bool
    open: int
    concluded: int


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
