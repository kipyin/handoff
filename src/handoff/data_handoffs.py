"""Handoff and check-in data access helpers."""

from __future__ import annotations

import enum
from datetime import date

from loguru import logger
from sqlmodel import select

from handoff.data_activity import log_activity
from handoff.db import session_context
from handoff.models import CheckIn, CheckInType, Handoff


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

        latest = session.exec(
            select(CheckIn)
            .where(CheckIn.handoff_id == handoff_id)
            .order_by(
                CheckIn.check_in_date.desc(),
                CheckIn.created_at.desc(),
                CheckIn.id.desc(),
            )
            .limit(1)
        ).first()
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
