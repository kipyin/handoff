"""Typed page-facing contracts shared by UI modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from handoff.models import Handoff, Project


@dataclass(slots=True)
class NowSnapshot:
    """Page-facing contract for the Now page.

    Contains the full payload needed to render Risk, Action required,
    custom sections, Upcoming, and Concluded in the canonical order,
    plus supporting data for filters and add form.

    custom_sections is a list of (section_id, handoffs) in display order;
    section_id is used for the header label.

    section_explanations maps handoff_id to a short "why this matched"
    explanation for rulebook-driven sections (Risk, Action required,
    custom sections, Upcoming). Concluded handoffs are not included.
    """

    risk: list[Handoff]
    action: list[Handoff]
    custom_sections: list[tuple[str, list[Handoff]]]
    upcoming: list[Handoff]
    concluded: list[Handoff]
    projects: list[Project]
    pitchmen: list[str]
    section_explanations: dict[int, str]


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
