"""Query and filter helpers for handoffs."""

from __future__ import annotations

from datetime import date, datetime, time, timedelta
from typing import Any

from loguru import logger
from sqlalchemy import exists, func
from sqlalchemy.orm import selectinload
from sqlmodel import or_, select

from handoff.data_handoffs import _latest_check_in, handoff_is_open
from handoff.db import session_context
from handoff.models import CheckIn, CheckInType, Handoff, Project
from handoff.page_models import HandoffQuery


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


def _latest_check_in_type_subquery():
    """Return a correlated scalar subquery for the latest check-in type."""
    return (
        select(CheckIn.check_in_type)
        .where(CheckIn.handoff_id == Handoff.id)
        .order_by(
            CheckIn.check_in_date.desc(),
            CheckIn.created_at.desc(),
            CheckIn.id.desc(),
        )
        .limit(1)
        .correlate(Handoff)
        .scalar_subquery()
    )


def _latest_check_in_is_open_predicate():
    """Return SQL predicate for open handoffs by latest check-in semantics."""
    latest_type = _latest_check_in_type_subquery()
    return or_(latest_type.is_(None), latest_type != CheckInType.CONCLUDED)


def _latest_check_in_is_concluded_predicate():
    """Return SQL predicate for concluded handoffs by latest check-in semantics."""
    latest_type = _latest_check_in_type_subquery()
    return latest_type == CheckInType.CONCLUDED


def _last_concluded_check_in_date_subquery():
    """Return correlated scalar subquery for last concluded check-in date."""
    return (
        select(func.max(CheckIn.check_in_date))
        .where(CheckIn.handoff_id == Handoff.id, CheckIn.check_in_type == CheckInType.CONCLUDED)
        .correlate(Handoff)
        .scalar_subquery()
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
            select(func.count())
            .select_from(Handoff)
            .where(Handoff.project.has(Project.is_archived.is_(False)))
            .where(_latest_check_in_is_open_predicate())
        )
        return int(session.exec(stmt).one())


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
        close_date_expr = _last_concluded_check_in_date_subquery()

        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))

        if not include_concluded:
            stmt = stmt.where(_latest_check_in_is_open_predicate())

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

        if concluded_start is not None or concluded_end is not None:
            stmt = stmt.where(close_date_expr.isnot(None))
            if concluded_start is not None:
                stmt = stmt.where(close_date_expr >= concluded_start)
            if concluded_end is not None:
                stmt = stmt.where(close_date_expr <= concluded_end)

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
            .where(_latest_check_in_is_open_predicate())
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
        stmt = stmt.where(_latest_check_in_is_open_predicate())
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
        if not _is_risk_handoff(handoff, cutoff=cutoff)
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
            .where(_latest_check_in_is_open_predicate())
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
    return [handoff for handoff in handoffs if not _is_risk_handoff(handoff, cutoff=cutoff)]


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
            .where(_latest_check_in_is_open_predicate())
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
    return [handoff for handoff in handoffs if _is_risk_handoff(handoff, cutoff=cutoff)]


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
        close_date_expr = _last_concluded_check_in_date_subquery()
        stmt = select(Handoff).options(
            selectinload(Handoff.project), selectinload(Handoff.check_ins)
        )
        stmt = stmt.where(_latest_check_in_is_concluded_predicate())
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
        stmt = stmt.order_by(close_date_expr.desc(), Handoff.created_at.desc())
        return list(session.exec(stmt).unique().all())


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
        stmt = select(Handoff.pitchman).where(Handoff.pitchman.isnot(None))
        stmt = stmt.where(_latest_check_in_is_open_predicate())
        if not include_archived_projects:
            stmt = stmt.where(Handoff.project.has(Project.is_archived.is_(False)))
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
    from handoff.data_projects import list_projects

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
