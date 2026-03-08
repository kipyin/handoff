"""Data access helpers for projects/todos and common query workflows."""

import enum
from datetime import UTC, date, datetime, time, timedelta
from typing import Any

from loguru import logger
from sqlalchemy.orm import selectinload
from sqlmodel import or_, select

from handoff.backup_schema import BackupPayload
from handoff.db import session_context
from handoff.models import Project, Todo, TodoStatus
from handoff.page_models import TodoQuery


class _Unset(enum.Enum):
    """Sentinel distinguishing 'not provided' from None in update functions."""

    UNSET = "UNSET"


_UNSET = _Unset.UNSET


def _helper_to_db(helper: str | list[str] | None) -> str | None:
    """Coerce helper to a single trimmed string for DB storage.

    Args:
        helper: A single string, list of strings, or None.

    Returns:
        Trimmed string, or None if empty or not provided.

    """
    if helper is None:
        return None
    if isinstance(helper, list):
        for h in helper:
            if h and str(h).strip():
                return str(h).strip()
        return None
    cleaned = str(helper).strip()
    return cleaned or None


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
        return project


def list_projects(*, include_archived: bool = False) -> list[Project]:
    """Return all projects ordered by creation (newest first).

    Args:
        include_archived: When True, include archived projects; otherwise only
            active projects are returned.

    Returns:
        List of projects, newest first.

    """
    with session_context() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))
        return list(session.exec(stmt).all())


def get_project(project_id: int) -> Project | None:
    """Return a project by id with its todos loaded.

    Args:
        project_id: Id of the project.

    Returns:
        The project with todos eagerly loaded, or None if not found.

    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if project:
            # Eager load todos
            _ = project.todos
        return project


def create_todo(
    project_id: int,
    name: str,
    status: TodoStatus = TodoStatus.HANDOFF,
    next_check: date | None = None,
    deadline: date | None = None,
    helper: str | list[str] | None = None,
    notes: str | None = None,
) -> Todo:
    """Create a new todo in a project.

    Args:
        project_id: Id of the project.
        name: Todo title/name.
        status: One of handoff, done, canceled.
        next_check: Optional next follow-up date.
        deadline: Optional due date/time.
        helper: Optional assignee name (single string).
        notes: Optional text (can include links, file paths, etc.).

    Returns:
        The created Todo.

    """
    with session_context() as session:
        todo = Todo(
            project_id=project_id,
            name=name,
            status=status,
            next_check=next_check,
            deadline=deadline,
            helper=_helper_to_db(helper),
            notes=notes or None,
        )
        session.add(todo)
        session.commit()
        session.refresh(todo)
        logger.info(
            "Created todo {todo_id} in project {project_id}: {name} "
            "(status={status}, helper={helper})",
            todo_id=todo.id,
            project_id=todo.project_id,
            name=todo.name,
            status=todo.status.value,
            helper=todo.helper,
        )
        return todo


def update_todo(
    todo_id: int,
    *,
    project_id: int | None | _Unset = _UNSET,
    name: str | None | _Unset = _UNSET,
    status: TodoStatus | None | _Unset = _UNSET,
    next_check: date | None | _Unset = _UNSET,
    deadline: date | None | _Unset = _UNSET,
    helper: str | list[str] | None | _Unset = _UNSET,
    notes: str | None | _Unset = _UNSET,
) -> Todo | None:
    """Update a todo by id. Only provided fields are updated.

    Args:
        todo_id: Id of the todo to update.
        project_id: Optional new project id.
        name: Optional new name.
        status: Optional new status.
        next_check: Optional next follow-up date.
        deadline: Optional new deadline.
        helper: Optional new helper (string or list).
        notes: Optional new notes.

    Returns:
        Updated todo, or None if not found.

    """
    with session_context() as session:
        todo = session.get(Todo, todo_id)
        if not todo:
            logger.warning("Todo {todo_id} not found for update", todo_id=todo_id)
            return None
        if project_id is not _UNSET:
            todo.project_id = project_id
        if name is not _UNSET:
            todo.name = name
        previous_status = todo.status
        if status is not _UNSET:
            todo.status = status
        if next_check is not _UNSET:
            todo.next_check = next_check
        if deadline is not _UNSET:
            todo.deadline = deadline
        if helper is not _UNSET:
            todo.helper = _helper_to_db(helper)
        if notes is not _UNSET:
            todo.notes = notes
        # Track when a todo is marked as done.
        is_newly_done = previous_status != todo.status and todo.status == TodoStatus.DONE
        if is_newly_done:
            todo.completed_at = datetime.now(UTC)

        session.add(todo)
        session.commit()
        session.refresh(todo)

        completion_msg = " [MARKED DONE]" if is_newly_done else ""
        logger.info(
            "Updated todo {todo_id} in project {project_id}{completion} "
            "(status={status}, helper={helper}, deadline={deadline})",
            todo_id=todo.id,
            project_id=todo.project_id,
            completion=completion_msg,
            status=todo.status.value,
            helper=todo.helper,
            deadline=todo.deadline,
        )
        return todo


def snooze_todo(todo_id: int, *, to_date: date) -> Todo | None:
    """Update a todo's next_check date. Does not change deadline.

    Args:
        todo_id: Id of the todo to snooze.
        to_date: New next follow-up date.

    Returns:
        Updated todo, or None if not found.

    """
    return update_todo(todo_id, next_check=to_date)


def close_todo(todo_id: int) -> Todo | None:
    """Mark a todo as done and remove it from the Now page.

    Args:
        todo_id: Id of the todo to close.

    Returns:
        Updated todo, or None if not found.

    """
    return update_todo(todo_id, status=TodoStatus.DONE)


def delete_todo(todo_id: int) -> bool:
    """Delete a todo by id.

    Args:
        todo_id: Id of the todo to delete.

    Returns:
        True when deleted, otherwise False.

    """
    with session_context() as session:
        todo = session.get(Todo, todo_id)
        if not todo:
            logger.warning("Todo {todo_id} not found for delete", todo_id=todo_id)
            return False
        name = todo.name
        project_id = todo.project_id
        session.delete(todo)
        session.commit()
        logger.info(
            "Deleted todo {todo_id} ({name}) from project {project_id}",
            todo_id=todo_id,
            name=name,
            project_id=project_id,
        )
        return True


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


def query_todos(
    *,
    query: TodoQuery | None = None,
    project_ids: list[int] | None = None,
    helper_name: str | None = None,
    helper_names: list[str] | None = None,
    statuses: list[TodoStatus] | None = None,
    start: date | None = None,
    end: date | None = None,
    completed_start: date | datetime | None = None,
    completed_end: date | datetime | None = None,
    search_text: str | None = None,
    include_archived: bool = False,
) -> list[Todo]:
    """Return todos matching optional unified filters.

    Callers may either provide the individual filter arguments directly or pass a
    :class:`handoff.page_models.TodoQuery` via ``query``. When ``query`` is provided,
    its values populate the individual filters for this call.

    ``completed_start`` and ``completed_end`` accept both ``date`` and
    ``datetime``.  Bare ``date`` values are promoted to start-of-day /
    end-of-day so the comparison against ``Todo.completed_at`` (a datetime
    column) includes the full day.

    Args:
        query: Optional typed query contract for project/helper/status/search/deadline filters.
        project_ids: Optional project ids to include.
        helper_name: Optional helper substring filter.
        helper_names: Optional exact helper names to include.
        statuses: Optional statuses to include.
        start: Optional inclusive deadline lower bound.
        end: Optional inclusive deadline upper bound.
        completed_start: Optional inclusive completed_at lower bound.
        completed_end: Optional inclusive completed_at upper bound.
        search_text: Optional free-text search against name/notes/helper.
        include_archived: When True, include archived todos; otherwise exclude them.

    Returns:
        Matching todos ordered by deadline then created_at.

    """
    if query is not None:
        project_ids = list(query.project_ids)
        helper_names = list(query.helper_names)
        statuses = list(query.statuses)
        start = query.deadline_start
        end = query.deadline_end
        search_text = query.search_text
        include_archived = query.include_archived

    with session_context() as session:
        stmt = select(Todo).options(selectinload(Todo.project))
        if not include_archived:
            stmt = stmt.where(Todo.is_archived.is_(False))

        if project_ids:
            stmt = stmt.where(Todo.project_id.in_(project_ids))

        helper_stripped = (helper_name or "").strip()
        if helper_stripped:
            stmt = stmt.where(Todo.helper.ilike(f"%{helper_stripped}%"))
        if helper_names:
            canonical_helper_names = [name.strip() for name in helper_names if name.strip()]
            if canonical_helper_names:
                stmt = stmt.where(Todo.helper.in_(canonical_helper_names))

        if statuses:
            stmt = stmt.where(Todo.status.in_(statuses))

        if start is not None:
            stmt = stmt.where(Todo.deadline.isnot(None)).where(Todo.deadline >= start)
        if end is not None:
            stmt = stmt.where(Todo.deadline.isnot(None)).where(Todo.deadline <= end)

        if completed_start is not None:
            cs = _to_start_of_day(completed_start)
            stmt = stmt.where(Todo.completed_at.isnot(None)).where(Todo.completed_at >= cs)
        if completed_end is not None:
            ce = _to_end_of_day(completed_end)
            stmt = stmt.where(Todo.completed_at.isnot(None)).where(Todo.completed_at <= ce)

        normalized_search = (search_text or "").strip()
        if normalized_search:
            like_expr = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Todo.name.ilike(like_expr),
                    Todo.notes.ilike(like_expr),
                    Todo.helper.ilike(like_expr),
                    Todo.project.has(Project.name.ilike(like_expr)),
                )
            )

        stmt = stmt.order_by(Todo.deadline.asc().nulls_last(), Todo.created_at.asc())
        todos = list(session.exec(stmt).all())

        filters_applied = any(
            [
                project_ids,
                bool(helper_stripped),
                helper_names,
                statuses,
                start is not None,
                end is not None,
                completed_start is not None,
                completed_end is not None,
                normalized_search,
            ]
        )
        if filters_applied:
            parts = []
            if project_ids:
                parts.append(f"project_ids={project_ids}")
            if helper_stripped:
                parts.append(f"helper={helper_stripped!r}")
            if helper_names:
                parts.append(f"helpers={helper_names!r}")
            if statuses:
                parts.append(f"statuses={[s.value for s in statuses]}")
            if start is not None:
                parts.append(f"start={start!s}")
            if end is not None:
                parts.append(f"end={end!s}")
            if completed_start is not None:
                parts.append(f"completed_start={completed_start!s}")
            if completed_end is not None:
                parts.append(f"completed_end={completed_end!s}")
            if normalized_search:
                parts.append(f"search={normalized_search!r}")
            logger.info(
                "query_todos filters: {filters} -> {count} todos",
                filters=", ".join(parts),
                count=len(todos),
            )

        return todos


def query_now_items(
    *,
    project_ids: list[int] | None = None,
    helper_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 2,
) -> list[tuple[Todo, bool]]:
    """Return open items that need attention on the Now page.

    An item needs attention if:
    - Next check is today or earlier (or null), and/or
    - Deadline is within deadline_near_days or past due.

    Returns:
        List of (todo, at_risk) tuples. at_risk is True when deadline is near
        or past. Sorted with at_risk items first, then by next_check, deadline,
        created_at.

    """
    today = date.today()
    cutoff = today + timedelta(days=deadline_near_days)

    with session_context() as session:
        stmt = (
            select(Todo)
            .options(selectinload(Todo.project))
            .where(Todo.is_archived.is_(False))
            .where(Todo.status == TodoStatus.HANDOFF)
        )
        if project_ids:
            stmt = stmt.where(Todo.project_id.in_(project_ids))
        if helper_names:
            canonical = [n.strip() for n in helper_names if n.strip()]
            if canonical:
                stmt = stmt.where(Todo.helper.in_(canonical))
        normalized_search = (search_text or "").strip()
        if normalized_search:
            like_expr = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Todo.name.ilike(like_expr),
                    Todo.notes.ilike(like_expr),
                    Todo.helper.ilike(like_expr),
                    Todo.project.has(Project.name.ilike(like_expr)),
                )
            )

        # Next-check driven: next_check <= today OR next_check IS NULL
        next_check_due = (Todo.next_check <= today) | (Todo.next_check.is_(None))
        # Deadline driven: deadline within range or past
        deadline_at_risk = (Todo.deadline.isnot(None)) & (Todo.deadline <= cutoff)
        stmt = stmt.where(next_check_due | deadline_at_risk)

        todos = list(session.exec(stmt).all())

    result: list[tuple[Todo, bool]] = []
    for todo in todos:
        at_risk = bool(todo.deadline and todo.deadline <= cutoff)
        result.append((todo, at_risk))

    # Sort: at_risk first, then by next_check, then deadline, then created_at
    def _sort_key(item: tuple[Todo, bool]) -> tuple[int, date | None, date | None, datetime]:
        t, risk = item
        # Risk items first (0 before 1)
        risk_order = 0 if risk else 1
        nc = t.next_check or date.max
        dl = t.deadline or date.max
        return (risk_order, nc, dl, t.created_at)

    result.sort(key=_sort_key)
    return result


def list_helpers() -> list[str]:
    """Return all distinct helper names (plain string column), sorted.

    Returns:
        Sorted list of unique non-empty helper names.

    """
    with session_context() as session:
        stmt = select(Todo.helper).where(Todo.helper.isnot(None))
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
        return project


def delete_project(project_id: int) -> bool:
    """Delete a project and its todos.

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
        todo_count = len(project.todos)
        session.delete(project)
        session.commit()
        logger.info(
            "Deleted project {project_id} and {todo_count} todos",
            project_id=project_id,
            todo_count=todo_count,
        )
        return True


def archive_project(project_id: int, *, archive_todos: bool = True) -> bool:
    """Archive a project and, optionally, its todos.

    Args:
        project_id: Id of the project to archive.
        archive_todos: When True, mark all child todos as archived as well.

    Returns:
        True when archived, otherwise False.

    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for archive", project_id=project_id)
            return False

        project.is_archived = True
        if archive_todos:
            todo_stmt = select(Todo).where(Todo.project_id == project_id)
            for todo in session.exec(todo_stmt).all():
                todo.is_archived = True
                session.add(todo)

        session.add(project)
        session.commit()
        logger.info(
            "Archived project {project_id} (archive_todos={archive_todos})",
            project_id=project_id,
            archive_todos=archive_todos,
        )
        return True


def unarchive_project(project_id: int) -> bool:
    """Unarchive a project (todos remain archived or active as-is).

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
        return True


def archive_todo(todo_id: int) -> bool:
    """Archive a single todo.

    Args:
        todo_id: Id of the todo to archive.

    Returns:
        True when archived, otherwise False.

    """
    with session_context() as session:
        todo = session.get(Todo, todo_id)
        if not todo:
            logger.warning("Todo {todo_id} not found for archive", todo_id=todo_id)
            return False
        todo.is_archived = True
        session.add(todo)
        session.commit()
        logger.info("Archived todo {todo_id}", todo_id=todo_id)
        return True


def unarchive_todo(todo_id: int) -> bool:
    """Unarchive a single todo.

    Args:
        todo_id: Id of the todo to unarchive.

    Returns:
        True when unarchived, otherwise False.

    """
    with session_context() as session:
        todo = session.get(Todo, todo_id)
        if not todo:
            logger.warning("Todo {todo_id} not found for unarchive", todo_id=todo_id)
            return False
        todo.is_archived = False
        session.add(todo)
        session.commit()
        logger.info("Unarchived todo {todo_id}", todo_id=todo_id)
        return True


def import_payload(data_payload: dict[str, Any]) -> None:
    """Replace all projects and todos with the contents of *data_payload*.

    The payload must match the schema produced by :func:`get_export_payload`
    (keys ``"projects"`` and ``"todos"``).  The operation runs inside a single
    transaction: existing rows are deleted, then new rows are inserted.

    Args:
        data_payload: Dict with ``"projects"`` and ``"todos"`` lists.

    Raises:
        KeyError: If ``"projects"`` or ``"todos"`` key is missing.
        ValueError: If a record cannot be parsed.

    """
    payload = BackupPayload.from_dict(data_payload)

    with session_context() as session:
        session.exec(select(Todo)).all()  # ensure model is loaded
        session.execute(Todo.__table__.delete())
        session.execute(Project.__table__.delete())

        for p in payload.projects:
            project = Project(
                id=p.id,
                name=p.name,
                created_at=p.created_at,
                is_archived=p.is_archived,
            )
            session.add(project)

        for t in payload.todos:
            todo = Todo(
                id=t.id,
                project_id=t.project_id,
                name=t.name,
                status=t.status,
                next_check=t.next_check,
                deadline=t.deadline,
                helper=t.helper,
                notes=t.notes,
                created_at=t.created_at,
                completed_at=t.completed_at,
                is_archived=t.is_archived,
            )
            session.add(todo)

        session.commit()
        logger.info(
            "Imported {project_count} projects and {todo_count} todos",
            project_count=len(payload.projects),
            todo_count=len(payload.todos),
        )


def get_export_payload() -> dict[str, Any]:
    """Return JSON-serializable snapshot of projects and todos.

    Returns:
        Dict with "projects" and "todos" keys, each a list of serialized records.

    """
    with session_context() as session:
        projects = list(session.exec(select(Project).order_by(Project.created_at.asc())).all())
        todos = list(session.exec(select(Todo).order_by(Todo.created_at.asc())).all())
        return BackupPayload.from_models(projects, todos).to_dict()


def get_projects_with_todo_summary(*, include_archived: bool = False) -> list[dict[str, Any]]:
    """Return projects with aggregated todo status counts.

    Each item contains:

    - project: The Project instance.
    - total: Total todos in the project.
    - handoff: Count of todos with status handoff.
    - done: Count of todos with status done.
    - canceled: Count of todos with status canceled.

    Args:
        include_archived: When True, include archived projects.

    Returns:
        List of dicts with project, total, handoff, done, and canceled keys.

    """
    projects = list_projects(include_archived=include_archived)
    if not projects:
        return []

    project_ids = [p.id for p in projects]
    todos = query_todos(project_ids=project_ids, include_archived=include_archived)
    summary_by_project: dict[int, dict[str, Any]] = {
        project.id: {
            "project": project,
            "total": 0,
            "handoff": 0,
            "done": 0,
            "canceled": 0,
        }
        for project in projects
    }

    for todo in todos:
        item = summary_by_project.get(todo.project_id)
        if not item:
            continue
        item["total"] += 1
        if todo.status == TodoStatus.HANDOFF:
            item["handoff"] += 1
        elif todo.status == TodoStatus.DONE:
            item["done"] += 1
        elif todo.status == TodoStatus.CANCELED:
            item["canceled"] += 1

    return [summary_by_project[project.id] for project in projects]
