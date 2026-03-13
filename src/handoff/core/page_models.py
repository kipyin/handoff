"""Typed page-facing contracts shared by UI modules."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date

from handoff.core.models import Handoff, Project


@dataclass(slots=True)
class NowSnapshot:
    """Page-facing contract for the Now page.

    Contains the full payload needed to render the Now page sections in
    canonical order: Risk, Action required, custom sections, Upcoming,
    and Concluded. Also includes supporting data for filters and the add form.

    The risk, action, and custom_sections fields hold handoffs grouped by
    matching rulebook sections. upcoming holds fallback handoffs, and concluded
    holds concluded handoffs (which are not subject to open-item rules).
    section_explanations maps each open section to its highest-priority rule's
    match_reason for display to the user.
    """

    risk: list[Handoff]
    action: list[Handoff]
    custom_sections: list[tuple[str, list[Handoff]]]
    upcoming: list[Handoff]
    upcoming_section_id: str
    concluded: list[Handoff]
    projects: list[Project]
    pitchmen: list[str]
    section_explanations: dict[str, str]


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
