"""Handoff service boundary between UI pages and the data layer."""

from __future__ import annotations

from datetime import date

from handoff.data import conclude_handoff as _conclude_handoff
from handoff.data import create_check_in as _create_check_in
from handoff.data import create_handoff as _create_handoff
from handoff.data import delete_handoff as _delete_handoff
from handoff.data import get_handoff_close_date as _get_handoff_close_date
from handoff.data import list_pitchmen as _list_pitchmen
from handoff.data import list_pitchmen_with_open_handoffs as _list_pitchmen_with_open_handoffs
from handoff.data import query_action_handoffs as _query_action_handoffs
from handoff.data import query_concluded_handoffs as _query_concluded_handoffs
from handoff.data import query_handoffs as _query_handoffs
from handoff.data import query_now_items as _query_now_items
from handoff.data import query_risk_handoffs as _query_risk_handoffs
from handoff.data import query_upcoming_handoffs as _query_upcoming_handoffs
from handoff.data import reopen_handoff as _reopen_handoff
from handoff.data import update_handoff as _update_handoff
from handoff.models import CheckIn, CheckInType, Handoff, Project
from handoff.page_models import HandoffQuery, NowSnapshot
from handoff.search_parse import parse_search_query
from handoff.services.project_service import list_projects
from handoff.services.settings_service import get_deadline_near_days


def get_now_snapshot(
    *,
    include_archived_projects: bool = False,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    projects: list[Project] | None = None,
    pitchmen: list[str] | None = None,
) -> NowSnapshot:
    """Return the full Now-page payload for rendering.

    Orchestrates section queries (Risk, Action required, Upcoming, Concluded)
    with shared filters. Section semantics and order match the current
    default behavior.

    Callers may pass pre-fetched projects and pitchmen to avoid redundant
    queries when the page has already loaded them for filters/add form.
    """
    deadline_near_days = get_deadline_near_days()
    parsed = parse_search_query(search_text or "")
    open_common = {
        "project_ids": project_ids,
        "pitchman_names": pitchman_names,
        "search_text": parsed.text_query,
        "deadline_near_days": deadline_near_days,
        "next_check_min": parsed.next_check_min,
        "next_check_max": parsed.next_check_max,
        "deadline_min": parsed.deadline_min,
        "deadline_max": parsed.deadline_max,
        "include_archived_projects": include_archived_projects,
    }
    concluded_common = {
        "project_ids": project_ids,
        "pitchman_names": pitchman_names,
        "search_text": parsed.text_query,
        "include_archived_projects": include_archived_projects,
    }
    risk = query_risk_handoffs(**open_common)
    action = query_action_handoffs(**open_common)
    upcoming = query_upcoming_handoffs(**open_common)
    concluded = query_concluded_handoffs(**concluded_common)
    if projects is None:
        projects = list_projects(include_archived=include_archived_projects)
    if pitchmen is None:
        pitchmen = list_pitchmen_with_open_handoffs(
            include_archived_projects=include_archived_projects
        )
    return NowSnapshot(
        risk=risk,
        action=action,
        upcoming=upcoming,
        concluded=concluded,
        projects=projects,
        pitchmen=pitchmen,
    )


def create_handoff(
    project_id: int,
    need_back: str,
    next_check: date | None = None,
    deadline: date | None = None,
    pitchman: str | list[str] | None = None,
    notes: str | None = None,
) -> Handoff:
    """Create a handoff through the service boundary."""
    return _create_handoff(
        project_id=project_id,
        need_back=need_back,
        next_check=next_check,
        deadline=deadline,
        pitchman=pitchman,
        notes=notes,
    )


def update_handoff(handoff_id: int, **changes) -> Handoff | None:
    """Update a handoff through the service boundary."""
    return _update_handoff(handoff_id, **changes)


def delete_handoff(handoff_id: int) -> bool:
    """Delete a handoff through the service boundary."""
    return _delete_handoff(handoff_id)


def query_handoffs(
    *,
    query: HandoffQuery | None = None,
    project_ids: list[int] | None = None,
    pitchman_name: str | None = None,
    pitchman_names: list[str] | None = None,
    start: date | None = None,
    end: date | None = None,
    concluded_start: date | None = None,
    concluded_end: date | None = None,
    search_text: str | None = None,
    include_concluded: bool = False,
    include_archived_projects: bool = False,
) -> list[Handoff]:
    """Query handoffs through the service boundary."""
    return _query_handoffs(
        query=query,
        project_ids=project_ids,
        pitchman_name=pitchman_name,
        pitchman_names=pitchman_names,
        start=start,
        end=end,
        concluded_start=concluded_start,
        concluded_end=concluded_end,
        search_text=search_text,
        include_concluded=include_concluded,
        include_archived_projects=include_archived_projects,
    )


def list_pitchmen() -> list[str]:
    """List known pitchman names through the service boundary."""
    return _list_pitchmen()


def list_pitchmen_with_open_handoffs(*, include_archived_projects: bool = False) -> list[str]:
    """List pitchmen who have at least one open handoff."""
    return _list_pitchmen_with_open_handoffs(include_archived_projects=include_archived_projects)


def query_now_items(
    *,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 1,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
) -> list[tuple[Handoff, bool]]:
    """Return open handoffs that need attention on the Now page.

    Items need attention when next_check is due today or earlier, or deadline
    is within deadline_near_days. Returns (handoff, at_risk) tuples.
    """
    return _query_now_items(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=search_text,
        deadline_near_days=deadline_near_days,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
    )


def query_action_handoffs(
    *,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 1,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
    include_archived_projects: bool = False,
) -> list[Handoff]:
    """Return open handoffs with a due check-in (next_check <= today)."""
    return _query_action_handoffs(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=search_text,
        deadline_near_days=deadline_near_days,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
        include_archived_projects=include_archived_projects,
    )


def query_risk_handoffs(
    *,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 1,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
    include_archived_projects: bool = False,
) -> list[Handoff]:
    """Return open handoffs that are near deadline and have delayed check-ins."""
    return _query_risk_handoffs(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=search_text,
        deadline_near_days=deadline_near_days,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
        include_archived_projects=include_archived_projects,
    )


def query_upcoming_handoffs(
    *,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 1,
    limit: int = 20,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
    include_archived_projects: bool = False,
) -> list[Handoff]:
    """Return open handoffs that are not yet action-required (upcoming)."""
    return _query_upcoming_handoffs(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=search_text,
        deadline_near_days=deadline_near_days,
        limit=limit,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
        include_archived_projects=include_archived_projects,
    )


def query_concluded_handoffs(
    *,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    include_archived_projects: bool = True,
) -> list[Handoff]:
    """Return handoffs whose latest check-in is concluded."""
    return _query_concluded_handoffs(
        project_ids=project_ids,
        pitchman_names=pitchman_names,
        search_text=search_text,
        include_archived_projects=include_archived_projects,
    )


def conclude_handoff(handoff_id: int, note: str | None = None) -> CheckIn:
    """Add a concluded check-in to close the handoff.

    Args:
        handoff_id: Id of the handoff to conclude.
        note: Optional conclusion note.

    Returns:
        The created concluded CheckIn.
    """
    return _conclude_handoff(handoff_id, note=note)


def reopen_handoff(
    handoff_id: int,
    *,
    note: str | None = None,
    next_check_date: date | None = None,
) -> CheckIn:
    """Reopen a concluded handoff by appending a new on-track check-in."""
    return _reopen_handoff(
        handoff_id,
        note=note,
        next_check_date=next_check_date,
    )


def get_handoff_close_date(handoff: Handoff) -> date | None:
    """Return the date of the last concluded check-in, or None if still open."""
    return _get_handoff_close_date(handoff)


def add_check_in(
    handoff_id: int,
    check_in_type: CheckInType,
    note: str | None = None,
    next_check_date: date | None = None,
    check_in_date: date | None = None,
) -> CheckIn:
    """Add a check-in entry to a handoff and optionally move next_check.

    Args:
        handoff_id: Id of the handoff.
        check_in_type: Type of check-in.
        note: Optional note.
        next_check_date: Optional next check date for non-concluded check-ins.
        check_in_date: Optional check-in date. Defaults to today.

    Returns:
        The created CheckIn.
    """
    effective_check_in_date = check_in_date or date.today()
    return _create_check_in(
        handoff_id=handoff_id,
        check_in_type=check_in_type,
        check_in_date=effective_check_in_date,
        note=note,
        next_check_date=next_check_date,
    )
