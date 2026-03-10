"""Data access helpers for projects, handoffs, check-ins and query workflows."""

import enum
import json
from datetime import date, datetime, time, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import exists, text
from sqlalchemy.orm import selectinload
from sqlmodel import or_, select

from handoff.backup_schema import BackupPayload
from handoff.db import session_context
from handoff.models import CheckIn, CheckInType, Handoff, Project
from handoff.page_models import HandoffQuery


def log_activity(
    entity_type: str,
    entity_id: int | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an activity log entry for the audit trail.

    Args:
        entity_type: One of "project", "handoff".
        entity_id: Id of the entity, or None for bulk operations.
        action: One of created, updated, concluded, deleted, archived, unarchived.
        details: Optional JSON-serializable dict with extra context.
    """
    try:
        with session_context() as session:
            details_str = json.dumps(details) if details else None
            session.execute(
                text(
                    "INSERT INTO activity_log (timestamp, entity_type, entity_id, action, details) "
                    "VALUES (CURRENT_TIMESTAMP, :entity_type, :entity_id, :action, :details)"
                ),
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "action": action,
                    "details": details_str,
                },
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Activity log insert failed: {}", exc)


def get_recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent activity log entries, newest first.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of dicts with timestamp, entity_type, entity_id, action, details.
    """
    with session_context() as session:
        result = session.execute(
            text(
                "SELECT timestamp, entity_type, entity_id, action, details "
                "FROM activity_log ORDER BY timestamp DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        rows = result.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        details = None
        if row[4]:
            try:
                details = json.loads(row[4])
            except (json.JSONDecodeError, TypeError):
                details = {"raw": row[4]}
        out.append(
            {
                "timestamp": row[0],
                "entity_type": row[1],
                "entity_id": row[2],
                "action": row[3],
                "details": details,
            }
        )
    return out


class _Unset(enum.Enum):
    """Sentinel distinguishing 'not provided' from None in update functions."""

    UNSET = "UNSET"


_UNSET = _Unset.UNSET


def _pitchman_to_db(pitchman: str | list[str] | None) -> str | None:
    """Coerce pitchman to a single trimmed string for DB storage.

    Args:
        pitchman: A single string, list of strings, or None.

    Returns:
        Trimmed string, or None if empty or not provided.
    """
    if pitchman is None:
        return None
    if isinstance(pitchman, list):
        for h in pitchman:
            if h and str(h).strip():
                return str(h).strip()
        return None
    cleaned = str(pitchman).strip()
    return cleaned or None


# ---------------------------------------------------------------------------
# Projects
# ---------------------------------------------------------------------------


def create_project(name: str) -> Project:
    """Create a new project.

    Args:
        name: Display name of the project.

    Returns:
        The created Project.
    """
    with session_context() as session:
        project = Project(name=name)
        session.add(project)
        session.commit()
        session.refresh(project)
        logger.info(
            "Created project {project_id}: {name}", project_id=project.id, name=project.name
        )
        log_activity("project", project.id, "created", {"name": project.name})
        return project


def list_projects(*, include_archived: bool = False) -> list[Project]:
    """Return all projects ordered by creation (newest first).

    Args:
        include_archived: When True, include archived projects.

    Returns:
        List of projects, newest first.
    """
    with session_context() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))
        return list(session.exec(stmt).all())


def get_project(project_id: int) -> Project | None:
    """Return a project by id with its handoffs loaded.

    Args:
        project_id: Id of the project.

    Returns:
        The project with handoffs eagerly loaded, or None if not found.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if project:
            _ = project.handoffs
        return project


def rename_project(project_id: int, name: str) -> Project | None:
    """Rename an existing project.

    Args:
        project_id: Id of the project to rename.
        name: New project name.

    Returns:
        Updated project, or None when not found.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for rename", project_id=project_id)
            return None
        project.name = name
        session.add(project)
        session.commit()
        session.refresh(project)
        logger.info("Renamed project {project_id} to {name}", project_id=project_id, name=name)
        log_activity("project", project_id, "updated", {"name": name})
        return project


def delete_project(project_id: int) -> bool:
    """Delete a project and its handoffs.

    Args:
        project_id: Id of the project to delete.

    Returns:
        True when deleted, otherwise False.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for delete", project_id=project_id)
            return False
        handoff_count = len(project.handoffs)
        proj_name = project.name
        session.delete(project)
        session.commit()
        logger.info(
            "Deleted project {project_id} and {handoff_count} handoffs",
            project_id=project_id,
            handoff_count=handoff_count,
        )
        log_activity(
            "project", project_id, "deleted", {"name": proj_name, "handoff_count": handoff_count}
        )
        return True


def archive_project(project_id: int) -> bool:
    """Archive a project. Handoffs are hidden via project filtering.

    Args:
        project_id: Id of the project to archive.

    Returns:
        True when archived, otherwise False.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for archive", project_id=project_id)
            return False
        project.is_archived = True
        session.add(project)
        session.commit()
        logger.info("Archived project {project_id}", project_id=project_id)
        log_activity("project", project_id, "archived", {})
        return True


def unarchive_project(project_id: int) -> bool:
    """Unarchive a project.

    Args:
        project_id: Id of the project to unarchive.

    Returns:
        True when unarchived, otherwise False.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for unarchive", project_id=project_id)
            return False
        project.is_archived = False
        session.add(project)
        session.commit()
        logger.info("Unarchived project {project_id}", project_id=project_id)
        log_activity("project", project_id, "unarchived", {})
        return True


# ---------------------------------------------------------------------------
# Handoffs
# ---------------------------------------------------------------------------


def create_handoff(
    project_id: int,
    need_back: str,
    next_check: date | None = None,
    deadline: date | None = None,
    pitchman: str | list[str] | None = None,
    notes: str | None = None,
) -> Handoff:
    """Create a new handoff in a project.

    Args:
        project_id: Id of the project.
        need_back: The deliverable/task description.
        next_check: Optional next follow-up date.
        deadline: Optional due date.
        pitchman: Optional person responsible (single string).
        notes: Optional context (links, markdown, etc.).

    Returns:
        The created Handoff.
    """
    with session_context() as session:
        handoff = Handoff(
            project_id=project_id,
            need_back=need_back,
            next_check=next_check,
            deadline=deadline,
            pitchman=_pitchman_to_db(pitchman),
            notes=notes or None,
        )
        session.add(handoff)
        session.commit()
        session.refresh(handoff)
        logger.info(
            "Created handoff {handoff_id} in project {project_id}: {need_back} "
            "(pitchman={pitchman})",
            handoff_id=handoff.id,
            project_id=handoff.project_id,
            need_back=handoff.need_back,
            pitchman=handoff.pitchman,
        )
        log_activity(
            "handoff",
            handoff.id,
            "created",
            {"need_back": handoff.need_back, "project_id": handoff.project_id},
        )
        return handoff


def update_handoff(
    handoff_id: int,
    *,
    project_id: int | None | _Unset = _UNSET,
    need_back: str | None | _Unset = _UNSET,
    next_check: date | None | _Unset = _UNSET,
    deadline: date | None | _Unset = _UNSET,
    pitchman: str | list[str] | None | _Unset = _UNSET,
    notes: str | None | _Unset = _UNSET,
) -> Handoff | None:
    """Update a handoff by id. Only provided fields are updated.

    Args:
        handoff_id: Id of the handoff to update.
        project_id: Optional new project id.
        need_back: Optional new deliverable description.
        next_check: Optional next follow-up date.
        deadline: Optional new deadline.
        pitchman: Optional new pitchman (string or list).
        notes: Optional new notes.

    Returns:
        Updated handoff, or None if not found.
    """
    with session_context() as session:
        handoff = session.get(Handoff, handoff_id)
        if not handoff:
            logger.warning("Handoff {handoff_id} not found for update", handoff_id=handoff_id)
            return None
        if project_id is not _UNSET:
            handoff.project_id = project_id
        if need_back is not _UNSET:
            handoff.need_back = need_back
        if next_check is not _UNSET:
            handoff.next_check = next_check
        if deadline is not _UNSET:
            handoff.deadline = deadline
        if pitchman is not _UNSET:
            handoff.pitchman = _pitchman_to_db(pitchman)
        if notes is not _UNSET:
            handoff.notes = notes

        session.add(handoff)
        session.commit()
        session.refresh(handoff)

        logger.info(
            "Updated handoff {handoff_id} in project {project_id} "
            "(pitchman={pitchman}, deadline={deadline})",
            handoff_id=handoff.id,
            project_id=handoff.project_id,
            pitchman=handoff.pitchman,
            deadline=handoff.deadline,
        )
        log_activity("handoff", handoff.id, "updated", {"need_back": handoff.need_back})
        return handoff


def snooze_handoff(handoff_id: int, *, to_date: date) -> Handoff | None:
    """Update a handoff's next_check date. Does not change deadline.

    Args:
        handoff_id: Id of the handoff to snooze.
        to_date: New next follow-up date.

    Returns:
        Updated handoff, or None if not found.
    """
    return update_handoff(handoff_id, next_check=to_date)


def delete_handoff(handoff_id: int) -> bool:
    """Delete a handoff by id.

    Args:
        handoff_id: Id of the handoff to delete.

    Returns:
        True when deleted, otherwise False.
    """
    with session_context() as session:
        handoff = session.get(Handoff, handoff_id)
        if not handoff:
            logger.warning("Handoff {handoff_id} not found for delete", handoff_id=handoff_id)
            return False
        need_back = handoff.need_back
        project_id = handoff.project_id
        session.delete(handoff)
        session.commit()
        logger.info(
            "Deleted handoff {handoff_id} ({need_back}) from project {project_id}",
            handoff_id=handoff_id,
            need_back=need_back,
            project_id=project_id,
        )
        log_activity(
            "handoff", handoff_id, "deleted", {"need_back": need_back, "project_id": project_id}
        )
        return True


# ---------------------------------------------------------------------------
# Check-ins
# ---------------------------------------------------------------------------


def create_check_in(
    handoff_id: int,
    check_in_type: CheckInType,
    check_in_date: date,
    note: str | None = None,
    next_check_date: date | None = None,
) -> CheckIn:
    """Insert a check-in entry for a handoff.

    Args:
        handoff_id: Id of the handoff.
        check_in_type: Type of check-in (on_track, delayed, concluded).
        check_in_date: Date of the check-in.
        note: Optional note/reason.
        next_check_date: Optional next check date to set on the handoff when
            check_in_type is not concluded.

    Returns:
        The created CheckIn.
    """
    with session_context() as session:
        handoff = session.get(Handoff, handoff_id)
        if handoff is None:
            msg = f"Handoff {handoff_id} not found for check-in"
            logger.warning(msg)
            raise ValueError(msg)

        check_in = CheckIn(
            handoff_id=handoff_id,
            check_in_type=check_in_type,
            check_in_date=check_in_date,
            note=note or None,
        )
        session.add(check_in)
        if check_in_type != CheckInType.CONCLUDED and next_check_date is not None:
            handoff.next_check = next_check_date
            session.add(handoff)
        session.commit()
        session.refresh(check_in)
        logger.info(
            "Created {check_in_type} check-in for handoff {handoff_id}",
            check_in_type=check_in_type.value,
            handoff_id=handoff_id,
        )
        log_activity(
            "handoff",
            handoff_id,
            "check_in",
            {
                "check_in_type": check_in_type.value,
                "check_in_date": str(check_in_date),
                "next_check_date": str(next_check_date) if next_check_date else None,
            },
        )
        return check_in


def conclude_handoff(handoff_id: int, note: str | None = None) -> CheckIn:
    """Add a concluded check-in to a handoff, closing it.

    Args:
        handoff_id: Id of the handoff to conclude.
        note: Optional conclusion note.

    Returns:
        The created concluded CheckIn.
    """
    today = date.today()
    check_in = create_check_in(
        handoff_id=handoff_id,
        check_in_type=CheckInType.CONCLUDED,
        check_in_date=today,
        note=note,
    )
    log_activity("handoff", handoff_id, "concluded", {"note": note})
    return check_in


def _latest_check_in(handoff: Handoff) -> CheckIn | None:
    """Return the latest check-in on a handoff trail, or None."""
    if not handoff.check_ins:
        return None
    return max(
        handoff.check_ins,
        key=lambda ci: (ci.check_in_date, ci.created_at, ci.id or 0),
    )


def handoff_is_open(handoff: Handoff) -> bool:
    """Return True when the latest check-in is not concluded."""
    latest = _latest_check_in(handoff)
    return latest is None or latest.check_in_type != CheckInType.CONCLUDED


def handoff_is_closed(handoff: Handoff) -> bool:
    """Return True when the latest check-in is concluded."""
    latest = _latest_check_in(handoff)
    return latest is not None and latest.check_in_type == CheckInType.CONCLUDED


def get_handoff_close_date(handoff: Handoff) -> date | None:
    """Return the date of the most recent concluded check-in, if any."""
    concluded = [ci for ci in handoff.check_ins if ci.check_in_type == CheckInType.CONCLUDED]
    if not concluded:
        return None
    return max(ci.check_in_date for ci in concluded)


def reopen_handoff(
    handoff_id: int,
    *,
    note: str | None = None,
    next_check_date: date | None = None,
) -> CheckIn:
    """Reopen a concluded handoff by appending a new on-track check-in.

    Reopen is only valid when the latest check-in is concluded. Existing
    check-ins are never mutated or deleted.
    """
    with session_context() as session:
        handoff = session.get(Handoff, handoff_id)
        if handoff is None:
            msg = f"Handoff {handoff_id} not found for reopen"
            logger.warning(msg)
            raise ValueError(msg)

        latest = _latest_check_in(handoff)
        if latest is None or latest.check_in_type != CheckInType.CONCLUDED:
            msg = f"Handoff {handoff_id} cannot be reopened unless latest check-in is concluded"
            logger.info(msg)
            raise ValueError(msg)

        today = date.today()
        handoff.next_check = next_check_date or today
        session.add(handoff)

        check_in = CheckIn(
            handoff_id=handoff_id,
            check_in_type=CheckInType.ON_TRACK,
            check_in_date=today,
            note=note or None,
        )
        session.add(check_in)
        session.commit()
        session.refresh(check_in)

        logger.info("Reopened handoff {handoff_id}", handoff_id=handoff_id)
        log_activity(
            "handoff",
            handoff_id,
            "reopened",
            {
                "next_check_date": str(handoff.next_check),
                "note": note or None,
            },
        )
        return check_in


def _last_check_in_is_delayed(handoff: Handoff) -> bool:
    """Return True when the latest check-in type is delayed."""
    latest = _latest_check_in(handoff)
    return latest is not None and latest.check_in_type == CheckInType.DELAYED


def _is_risk_handoff(handoff: Handoff, *, cutoff: date) -> bool:
    """Return True when deadline is near/overdue and latest check-in is delayed."""
    return (
        handoff.deadline is not None
        and handoff.deadline <= cutoff
        and _last_check_in_is_delayed(handoff)
    )


def _check_in_note_subquery(search_value: str):
    """Return a correlated subquery matching check-in notes for a handoff."""
    return (
        select(CheckIn.id)
        .where(CheckIn.handoff_id == Handoff.id, CheckIn.note.ilike(search_value))
        .correlate(Handoff)
    )


def _apply_handoff_filters(
    stmt,
    *,
    project_ids: list[int] | None,
    pitchman_names: list[str] | None,
    search_text: str | None,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
):
    """Apply reusable handoff filters used across section queries."""
    if project_ids:
        stmt = stmt.where(Handoff.project_id.in_(project_ids))
    if pitchman_names:
        canonical = [n.strip() for n in pitchman_names if n.strip()]
        if canonical:
            stmt = stmt.where(Handoff.pitchman.in_(canonical))

    normalized_search = (search_text or "").strip()
    if normalized_search:
        like_expr = f"%{normalized_search}%"
        stmt = stmt.where(
            or_(
                Handoff.need_back.ilike(like_expr),
                Handoff.notes.ilike(like_expr),
                Handoff.pitchman.ilike(like_expr),
                Handoff.project.has(Project.name.ilike(like_expr)),
                exists(_check_in_note_subquery(like_expr)),
            )
        )

    if next_check_min is not None:
        stmt = stmt.where(Handoff.next_check.isnot(None), Handoff.next_check >= next_check_min)
    if next_check_max is not None:
        stmt = stmt.where(Handoff.next_check.isnot(None), Handoff.next_check <= next_check_max)
    if deadline_min is not None:
        stmt = stmt.where(Handoff.deadline.isnot(None), Handoff.deadline >= deadline_min)
    if deadline_max is not None:
        stmt = stmt.where(Handoff.deadline.isnot(None), Handoff.deadline <= deadline_max)
    return stmt


def count_open_handoffs() -> int:
    """Return the number of open handoffs in non-archived projects."""
    with session_context() as session:
        stmt = (
            select(Handoff)
            .options(selectinload(Handoff.check_ins))
            .where(Handoff.project.has(Project.is_archived.is_(False)))
        )
        handoffs = list(session.exec(stmt).unique().all())
        return sum(1 for handoff in handoffs if handoff_is_open(handoff))


# ---------------------------------------------------------------------------
# Queries
# ---------------------------------------------------------------------------


def _to_start_of_day(value: date | datetime) -> datetime:
    """Promote a bare date to start-of-day datetime; pass datetimes through."""
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.min)


def _to_end_of_day(value: date | datetime) -> datetime:
    """Promote a bare date to end-of-day datetime; pass datetimes through."""
    if isinstance(value, datetime):
        return value
    return datetime.combine(value, time.max)


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
    """Return handoffs matching optional unified filters.

    Args:
        query: Optional typed query contract.
        project_ids: Optional project ids to include.
        pitchman_name: Optional pitchman substring filter.
        pitchman_names: Optional exact pitchman names to include.
        start: Optional inclusive deadline lower bound.
        end: Optional inclusive deadline upper bound.
        concluded_start: Optional inclusive conclude-date lower bound.
        concluded_end: Optional inclusive conclude-date upper bound.
        search_text: Optional free-text search against need_back/notes/pitchman.
        include_concluded: When True, include concluded handoffs.
        include_archived_projects: When True, include handoffs in archived projects.

    Returns:
        Matching handoffs ordered by deadline then created_at.
    """
    if query is not None:
        project_ids = list(query.project_ids)
        pitchman_names = list(query.pitchman_names)
        start = query.deadline_start
        end = query.deadline_end
        search_text = query.search_text
        include_concluded = query.include_concluded
        include_archived_projects = query.include_archived_projects

    with session_context() as session:
        stmt = select(Handoff).options(
            selectinload(Handoff.project),
            selectinload(Handoff.check_ins),
        )

        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))

        if project_ids:
            stmt = stmt.where(Handoff.project_id.in_(project_ids))

        pitchman_stripped = (pitchman_name or "").strip()
        if pitchman_stripped:
            stmt = stmt.where(Handoff.pitchman.ilike(f"%{pitchman_stripped}%"))
        if pitchman_names:
            canonical = [n.strip() for n in pitchman_names if n.strip()]
            if canonical:
                stmt = stmt.where(Handoff.pitchman.in_(canonical))

        if start is not None:
            stmt = stmt.where(Handoff.deadline.isnot(None)).where(Handoff.deadline >= start)
        if end is not None:
            stmt = stmt.where(Handoff.deadline.isnot(None)).where(Handoff.deadline <= end)

        normalized_search = (search_text or "").strip()
        if normalized_search:
            like_expr = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Handoff.need_back.ilike(like_expr),
                    Handoff.notes.ilike(like_expr),
                    Handoff.pitchman.ilike(like_expr),
                    Handoff.project.has(Project.name.ilike(like_expr)),
                    exists(_check_in_note_subquery(like_expr)),
                )
            )

        stmt = stmt.order_by(Handoff.deadline.asc().nulls_last(), Handoff.created_at.asc())
        handoffs = list(session.exec(stmt).unique().all())

        if not include_concluded:
            handoffs = [handoff for handoff in handoffs if handoff_is_open(handoff)]

        if concluded_start is not None or concluded_end is not None:
            filtered: list[Handoff] = []
            for handoff in handoffs:
                close_date = get_handoff_close_date(handoff)
                if close_date is None:
                    continue
                if concluded_start is not None and close_date < concluded_start:
                    continue
                if concluded_end is not None and close_date > concluded_end:
                    continue
                filtered.append(handoff)
            handoffs = filtered

        filters_applied = any(
            [
                project_ids,
                bool(pitchman_stripped),
                pitchman_names,
                start is not None,
                end is not None,
                concluded_start is not None,
                concluded_end is not None,
                normalized_search,
            ]
        )
        if filters_applied:
            parts = []
            if project_ids:
                parts.append(f"project_ids={project_ids}")
            if pitchman_stripped:
                parts.append(f"pitchman={pitchman_stripped!r}")
            if pitchman_names:
                parts.append(f"pitchmen={pitchman_names!r}")
            if start is not None:
                parts.append(f"start={start!s}")
            if end is not None:
                parts.append(f"end={end!s}")
            if normalized_search:
                parts.append(f"search={normalized_search!r}")
            logger.info(
                "query_handoffs filters: {filters} -> {count} handoffs",
                filters=", ".join(parts),
                count=len(handoffs),
            )

        return handoffs


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

    A handoff needs attention if:
    - Next check is today or earlier (or null), and/or
    - Deadline is within deadline_near_days or past due.

    Returns:
        List of (handoff, at_risk) tuples. at_risk is True when deadline is
        near or past. Sorted with at_risk items first, then by next_check,
        deadline, created_at.
    """
    today = date.today()
    cutoff = today + timedelta(days=deadline_near_days)

    with session_context() as session:
        stmt = (
            select(Handoff)
            .options(selectinload(Handoff.project), selectinload(Handoff.check_ins))
            .where(Handoff.project.has(Project.is_archived.is_(False)))
        )
        if project_ids:
            stmt = stmt.where(Handoff.project_id.in_(project_ids))
        if pitchman_names:
            canonical = [n.strip() for n in pitchman_names if n.strip()]
            if canonical:
                stmt = stmt.where(Handoff.pitchman.in_(canonical))
        normalized_search = (search_text or "").strip()
        if normalized_search:
            like_expr = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Handoff.need_back.ilike(like_expr),
                    Handoff.notes.ilike(like_expr),
                    Handoff.pitchman.ilike(like_expr),
                    Handoff.project.has(Project.name.ilike(like_expr)),
                )
            )
        if next_check_min is not None:
            stmt = stmt.where(
                Handoff.next_check.isnot(None),
                Handoff.next_check >= next_check_min,
            )
        if next_check_max is not None:
            stmt = stmt.where(
                (Handoff.next_check.is_(None)) | (Handoff.next_check <= next_check_max)
            )
        if deadline_min is not None:
            stmt = stmt.where(
                Handoff.deadline.isnot(None),
                Handoff.deadline >= deadline_min,
            )
        if deadline_max is not None:
            stmt = stmt.where(
                Handoff.deadline.isnot(None),
                Handoff.deadline <= deadline_max,
            )

        next_check_due = (Handoff.next_check <= today) | (Handoff.next_check.is_(None))
        deadline_at_risk = (Handoff.deadline.isnot(None)) & (Handoff.deadline <= cutoff)
        stmt = stmt.where(next_check_due | deadline_at_risk)

        handoffs = list(session.exec(stmt).unique().all())
        handoffs = [handoff for handoff in handoffs if handoff_is_open(handoff)]

    result: list[tuple[Handoff, bool]] = []
    for h in handoffs:
        at_risk = bool(h.deadline and h.deadline <= cutoff)
        result.append((h, at_risk))

    def _sort_key(item: tuple[Handoff, bool]) -> tuple[int, date | None, date | None, datetime]:
        h, risk = item
        risk_order = 0 if risk else 1
        nc = h.next_check or date.max
        dl = h.deadline or date.max
        return (risk_order, nc, dl, h.created_at)

    result.sort(key=_sort_key)
    return result


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
    """Return open handoffs that are not in Risk or Action sections.

    A handoff is upcoming when it is open and neither:
    - Action: next_check is due (<= today), nor
    - Risk: deadline is near and the last check-in is delayed.
    Handoffs without a next_check are included when they are not Risk/Action.
    Sorted by next_check then deadline.

    Args:
        project_ids: Optional filter by project ids.
        pitchman_names: Optional filter by pitchman names.
        search_text: Optional search in need_back, notes, pitchman, project name.
        deadline_near_days: Cutoff for "at risk" (deadline > today + N is safe).
        limit: Maximum number of results.
        next_check_min: Optional minimum next_check date.
        next_check_max: Optional maximum next_check date.
        deadline_min: Optional minimum deadline.
        deadline_max: Optional maximum deadline.
        include_archived_projects: When True, include archived projects.

    Returns:
        List of Handoff models with project loaded, ordered by next_check.
    """
    today = date.today()
    cutoff = today + timedelta(days=deadline_near_days)
    with session_context() as session:
        stmt = select(Handoff).options(
            selectinload(Handoff.project), selectinload(Handoff.check_ins)
        )
        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))
        stmt = _apply_handoff_filters(
            stmt,
            project_ids=project_ids,
            pitchman_names=pitchman_names,
            search_text=search_text,
            next_check_min=next_check_min,
            next_check_max=next_check_max,
            deadline_min=deadline_min,
            deadline_max=deadline_max,
        )
        stmt = stmt.order_by(
            Handoff.next_check.asc().nulls_last(),
            Handoff.deadline.asc().nulls_last(),
            Handoff.created_at.asc(),
        )
        handoffs = list(session.exec(stmt).unique().all())

    filtered = [
        handoff
        for handoff in handoffs
        if handoff_is_open(handoff)
        and not _is_risk_handoff(handoff, cutoff=cutoff)
        and not (handoff.next_check is not None and handoff.next_check <= today)
    ]
    return filtered[:limit]


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
    """Return open handoffs with a due check-in (next_check <= today), excluding Risk."""
    today = date.today()
    cutoff = today + timedelta(days=deadline_near_days)
    with session_context() as session:
        stmt = (
            select(Handoff)
            .options(selectinload(Handoff.project), selectinload(Handoff.check_ins))
            .where(Handoff.next_check.isnot(None))
            .where(Handoff.next_check <= today)
        )
        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))
        stmt = _apply_handoff_filters(
            stmt,
            project_ids=project_ids,
            pitchman_names=pitchman_names,
            search_text=search_text,
            next_check_min=next_check_min,
            next_check_max=next_check_max,
            deadline_min=deadline_min,
            deadline_max=deadline_max,
        )
        stmt = stmt.order_by(
            Handoff.next_check.asc().nulls_last(),
            Handoff.deadline.asc().nulls_last(),
            Handoff.created_at.asc(),
        )
        handoffs = list(session.exec(stmt).unique().all())
    return [
        handoff
        for handoff in handoffs
        if handoff_is_open(handoff) and not _is_risk_handoff(handoff, cutoff=cutoff)
    ]


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
    """Return open handoffs near deadline where the latest check-in is delayed."""
    cutoff = date.today() + timedelta(days=deadline_near_days)
    with session_context() as session:
        stmt = (
            select(Handoff)
            .options(selectinload(Handoff.project), selectinload(Handoff.check_ins))
            .where(Handoff.deadline.isnot(None))
            .where(Handoff.deadline <= cutoff)
        )
        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))
        stmt = _apply_handoff_filters(
            stmt,
            project_ids=project_ids,
            pitchman_names=pitchman_names,
            search_text=search_text,
            next_check_min=next_check_min,
            next_check_max=next_check_max,
            deadline_min=deadline_min,
            deadline_max=deadline_max,
        )
        stmt = stmt.order_by(
            Handoff.deadline.asc().nulls_last(),
            Handoff.next_check.asc().nulls_last(),
            Handoff.created_at.asc(),
        )
        handoffs = list(session.exec(stmt).unique().all())
    return [
        handoff
        for handoff in handoffs
        if handoff_is_open(handoff) and _is_risk_handoff(handoff, cutoff=cutoff)
    ]


def query_concluded_handoffs(
    *,
    project_ids: list[int] | None = None,
    pitchman_names: list[str] | None = None,
    search_text: str | None = None,
    include_archived_projects: bool = True,
) -> list[Handoff]:
    """Return handoffs whose latest check-in is concluded.

    Args:
        project_ids: Optional filter by project ids.
        pitchman_names: Optional filter by pitchman names.
        search_text: Optional search in need_back, notes, pitchman, project name.
        include_archived_projects: When True, include handoffs in archived projects.

    Returns:
        Concluded handoffs ordered by close date descending.
    """
    with session_context() as session:
        stmt = select(Handoff).options(
            selectinload(Handoff.project), selectinload(Handoff.check_ins)
        )
        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))
        if project_ids:
            stmt = stmt.where(Handoff.project_id.in_(project_ids))
        if pitchman_names:
            canonical = [n.strip() for n in pitchman_names if n.strip()]
            if canonical:
                stmt = stmt.where(Handoff.pitchman.in_(canonical))
        normalized_search = (search_text or "").strip()
        if normalized_search:
            like_expr = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Handoff.need_back.ilike(like_expr),
                    Handoff.notes.ilike(like_expr),
                    Handoff.pitchman.ilike(like_expr),
                    Handoff.project.has(Project.name.ilike(like_expr)),
                    exists(_check_in_note_subquery(like_expr)),
                )
            )
        handoffs = list(session.exec(stmt).unique().all())

    handoffs = [handoff for handoff in handoffs if handoff_is_closed(handoff)]
    handoffs.sort(
        key=lambda h: get_handoff_close_date(h) or date.min,
        reverse=True,
    )
    return handoffs


# ---------------------------------------------------------------------------
# Lists
# ---------------------------------------------------------------------------


def list_pitchmen() -> list[str]:
    """Return all distinct pitchman names, sorted.

    Returns:
        Sorted list of unique non-empty pitchman names.
    """
    with session_context() as session:
        stmt = select(Handoff.pitchman).where(Handoff.pitchman.isnot(None))
        raw_values = session.exec(stmt).all()
        canonical_by_lower: dict[str, str] = {}
        for raw in raw_values:
            name = (raw or "").strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered not in canonical_by_lower:
                canonical_by_lower[lowered] = name
        return sorted(canonical_by_lower.values(), key=str.lower)


def list_pitchmen_with_open_handoffs(*, include_archived_projects: bool = False) -> list[str]:
    """Return distinct pitchman names who have at least one open handoff.

    Open handoffs are those whose latest check-in is not concluded.

    Returns:
        Sorted list of unique non-empty pitchman names.
    """
    with session_context() as session:
        handoff_stmt = (
            select(Handoff)
            .options(selectinload(Handoff.check_ins))
            .where(Handoff.pitchman.isnot(None))
        )
        if not include_archived_projects:
            handoff_stmt = handoff_stmt.where(Handoff.project.has(Project.is_archived.is_(False)))
        handoffs = list(session.exec(handoff_stmt).unique().all())
        canonical_by_lower: dict[str, str] = {}
        for handoff in handoffs:
            if not handoff_is_open(handoff):
                continue
            name = (handoff.pitchman or "").strip()
            if not name:
                continue
            lowered = name.lower()
            if lowered not in canonical_by_lower:
                canonical_by_lower[lowered] = name
        return sorted(canonical_by_lower.values(), key=str.lower)


# ---------------------------------------------------------------------------
# Import / Export
# ---------------------------------------------------------------------------


def import_payload(data_payload: dict[str, Any]) -> None:
    """Replace all projects, handoffs and check-ins with the contents of *data_payload*.

    Accepts both the new format (``"handoffs"`` + ``"check_ins"``) and the legacy
    format (``"todos"``). The operation runs inside a single transaction.

    Args:
        data_payload: Dict with ``"projects"`` and ``"handoffs"``/``"check_ins"`` lists.

    Raises:
        KeyError: If required keys are missing.
        ValueError: If a record cannot be parsed.
    """
    payload = BackupPayload.from_dict(data_payload)

    with session_context() as session:
        session.exec(select(CheckIn)).all()
        session.exec(select(Handoff)).all()
        session.execute(CheckIn.__table__.delete())
        session.execute(Handoff.__table__.delete())
        session.execute(Project.__table__.delete())

        for p in payload.projects:
            project = Project(
                id=p.id,
                name=p.name,
                created_at=p.created_at,
                is_archived=p.is_archived,
            )
            session.add(project)

        for h in payload.handoffs:
            handoff = Handoff(
                id=h.id,
                project_id=h.project_id,
                need_back=h.need_back,
                pitchman=h.pitchman,
                next_check=h.next_check,
                deadline=h.deadline,
                notes=h.notes,
                created_at=h.created_at,
            )
            session.add(handoff)

        for c in payload.check_ins:
            check_in = CheckIn(
                id=c.id,
                handoff_id=c.handoff_id,
                check_in_date=c.check_in_date,
                note=c.note,
                check_in_type=c.check_in_type,
                created_at=c.created_at,
            )
            session.add(check_in)

        session.commit()
        logger.info(
            "Imported {project_count} projects, {handoff_count} handoffs, "
            "{check_in_count} check-ins",
            project_count=len(payload.projects),
            handoff_count=len(payload.handoffs),
            check_in_count=len(payload.check_ins),
        )


def get_export_payload() -> dict[str, Any]:
    """Return JSON-serializable snapshot of projects, handoffs, and check-ins.

    Returns:
        Dict with "projects", "handoffs", and "check_ins" keys.
    """
    with session_context() as session:
        projects = list(session.exec(select(Project).order_by(Project.created_at.asc())).all())
        handoffs = list(session.exec(select(Handoff).order_by(Handoff.created_at.asc())).all())
        check_ins = list(session.exec(select(CheckIn).order_by(CheckIn.created_at.asc())).all())
        return BackupPayload.from_models(projects, handoffs, check_ins).to_dict()


def get_projects_with_handoff_summary(*, include_archived: bool = False) -> list[dict[str, Any]]:
    """Return projects with aggregated handoff counts (open vs concluded).

    Each item contains:

    - project: The Project instance.
    - total: Total handoffs in the project.
    - open: Count of open handoffs (latest check-in is not concluded).
    - concluded: Count of concluded handoffs.

    Args:
        include_archived: When True, include archived projects.

    Returns:
        List of dicts with project, total, open, and concluded keys.
    """
    projects = list_projects(include_archived=include_archived)
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    all_handoffs = query_handoffs(
        project_ids=project_ids,
        include_concluded=True,
        include_archived_projects=include_archived,
    )
    summary_by_project: dict[int, dict[str, Any]] = {
        project.id: {
            "project": project,
            "total": 0,
            "open": 0,
            "concluded": 0,
        }
        for project in projects
    }

    for h in all_handoffs:
        item = summary_by_project.get(h.project_id)
        if not item:
            continue
        item["total"] += 1
        if handoff_is_open(h):
            item["open"] += 1
        else:
            item["concluded"] += 1

    return [summary_by_project[project.id] for project in projects]
