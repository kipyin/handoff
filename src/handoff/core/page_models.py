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

    Attributes:
        risk: Handoffs matching the Risk rule.
        action: Handoffs matching the Action required rule.
        custom_sections: Tuples of (section_id, handoffs) for user-defined sections
            in display order.
        upcoming: Handoffs in the fallback section (usually "Upcoming").
        upcoming_section_id: Section id for the fallback section; used to look up
            its explanation in section_explanations.
        concluded: Concluded handoffs.
        projects: Available projects for filtering and context.
        pitchmen: Unique pitchman names for filtering.
        section_explanations: Map from section_id to the rule match reason for
            rulebook-driven sections (Risk, Action required, custom sections,
            Upcoming). Concluded section has no entry.
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
