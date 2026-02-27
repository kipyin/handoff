"""Data access helpers for projects/todos and common query workflows."""

from datetime import UTC, datetime
from typing import Any

from loguru import logger
from sqlmodel import or_, select

from todo_app.db import session_context
from todo_app.models import Project, Todo, TodoStatus

_UNSET = object()


def normalize_helper_name(helper: str | None) -> str | None:
    """Return a normalized helper value.

    Args:
        helper: Raw helper text from UI.

    Returns:
        A stripped helper string or None when empty.
    """
    if helper is None:
        return None
    cleaned = helper.strip()
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
    """
    with session_context() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))
        return list(session.exec(stmt).all())


def get_project(project_id: int) -> Project | None:
    """Return a project by id with its todos loaded."""
    with session_context() as session:
        project = session.get(Project, project_id)
        if project:
            # Eager load todos
            _ = project.todos
        return project


def create_todo(
    project_id: int,
    name: str,
    status: TodoStatus = TodoStatus.DELEGATED,
    deadline: datetime | None = None,
    helper: str | None = None,
    notes: str | None = None,
) -> Todo:
    """Create a new todo in a project.

    Args:
        project_id: Id of the project.
        name: Todo title/name.
        status: One of delegated, done, canceled.
        deadline: Optional due date/time.
        helper: Optional assignee/helper name.
        notes: Optional text (can include links, file paths, etc.).

    Returns:
        The created Todo.
    """
    with session_context() as session:
        todo = Todo(
            project_id=project_id,
            name=name,
            status=status,
            deadline=deadline,
            helper=normalize_helper_name(helper),
            notes=notes or None,
        )
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo


def update_todo(
    todo_id: int,
    *,
    project_id: int | None | object = _UNSET,
    name: str | None | object = _UNSET,
    status: TodoStatus | None | object = _UNSET,
    deadline: datetime | None | object = _UNSET,
    helper: str | None | object = _UNSET,
    notes: str | None | object = _UNSET,
) -> Todo | None:
    """Update a todo by id. Only provided fields are updated."""
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
        if deadline is not _UNSET:
            todo.deadline = deadline
        if helper is not _UNSET:
            todo.helper = normalize_helper_name(helper)
        if notes is not _UNSET:
            todo.notes = notes
        # Track when a todo is marked as done.
        if previous_status != todo.status and todo.status == TodoStatus.DONE:
            todo.completed_at = datetime.now(UTC)

        session.add(todo)
        session.commit()
        session.refresh(todo)
        logger.info(
            "Updated todo {todo_id} in project {project_id} "
            "(status={status}, helper={helper}, deadline={deadline})",
            todo_id=todo.id,
            project_id=todo.project_id,
            status=todo.status.value,
            helper=todo.helper,
            deadline=todo.deadline,
        )
        return todo


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
        session.delete(todo)
        session.commit()
        logger.info("Deleted todo {todo_id} name={name!r}", todo_id=todo_id, name=name)
        return True


def query_todos(
    *,
    project_ids: list[int] | None = None,
    helper_name: str | None = None,
    statuses: list[TodoStatus] | None = None,
    start: datetime | None = None,
    end: datetime | None = None,
    search_text: str | None = None,
    include_archived: bool = False,
) -> list[Todo]:
    """Return todos matching optional unified filters.

    Args:
        project_ids: Optional project ids to include.
        helper_name: Optional helper substring filter.
        statuses: Optional statuses to include.
        start: Optional inclusive deadline lower bound.
        end: Optional inclusive deadline upper bound.
        search_text: Optional free-text search against name/notes/helper.

    Returns:
        Matching todos ordered by deadline then created_at.
    """
    with session_context() as session:
        stmt = select(Todo)
        if not include_archived:
            stmt = stmt.where(Todo.is_archived.is_(False))

        if project_ids:
            stmt = stmt.where(Todo.project_id.in_(project_ids))

        normalized_helper = normalize_helper_name(helper_name)
        if normalized_helper:
            stmt = stmt.where(Todo.helper.ilike(f"%{normalized_helper}%"))

        if statuses:
            stmt = stmt.where(Todo.status.in_(statuses))

        if start is not None:
            stmt = stmt.where(Todo.deadline.isnot(None)).where(Todo.deadline >= start)
        if end is not None:
            stmt = stmt.where(Todo.deadline.isnot(None)).where(Todo.deadline <= end)

        normalized_search = (search_text or "").strip()
        if normalized_search:
            like_expr = f"%{normalized_search}%"
            stmt = stmt.where(
                or_(
                    Todo.name.ilike(like_expr),
                    Todo.notes.ilike(like_expr),
                    Todo.helper.ilike(like_expr),
                )
            )

        stmt = stmt.order_by(Todo.deadline.asc().nulls_last(), Todo.created_at.asc())
        todos = list(session.exec(stmt).all())
        for todo in todos:
            todo.project = session.get(Project, todo.project_id)

        filters_applied = any(
            [
                project_ids,
                normalized_helper,
                statuses,
                start is not None,
                end is not None,
                normalized_search,
            ]
        )
        if filters_applied:
            parts = []
            if project_ids:
                parts.append(f"project_ids={project_ids}")
            if normalized_helper:
                parts.append(f"helper={normalized_helper!r}")
            if statuses:
                parts.append(f"statuses={[s.value for s in statuses]}")
            if start is not None:
                parts.append(f"start={start.date()!s}")
            if end is not None:
                parts.append(f"end={end.date()!s}")
            if normalized_search:
                parts.append(f"search={normalized_search!r}")
            logger.info(
                "query_todos filters: {filters} -> {count} todos",
                filters=", ".join(parts),
                count=len(todos),
            )

        return todos


def get_todos_by_project(project_id: int) -> list[Todo]:
    """Return all todos for a project, ordered by deadline (nulls last) then created_at."""
    return query_todos(project_ids=[project_id])


def get_todos_by_helper(helper_name: str) -> list[Todo]:
    """Return all todos across all projects assigned to the given helper."""
    return query_todos(helper_name=helper_name)


def get_todos_by_timeframe(
    start: datetime,
    end: datetime,
) -> list[Todo]:
    """Return all todos whose deadline falls within [start, end] (inclusive of day)."""
    return query_todos(start=start, end=end)


def list_helpers() -> list[str]:
    """Return all distinct helper names, sorted alphabetically."""
    with session_context() as session:
        stmt = select(Todo.helper).where(Todo.helper.isnot(None))
        helpers = session.exec(stmt).all()
        canonical_by_lower: dict[str, str] = {}
        for helper in helpers:
            normalized = normalize_helper_name(helper)
            if not normalized:
                continue
            lowered = normalized.lower()
            if lowered not in canonical_by_lower:
                canonical_by_lower[lowered] = normalized
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

        todo_stmt = select(Todo).where(Todo.project_id == project_id)
        todos = list(session.exec(todo_stmt).all())
        for todo in todos:
            session.delete(todo)
        session.delete(project)
        session.commit()
        logger.info(
            "Deleted project {project_id} and {todo_count} todos",
            project_id=project_id,
            todo_count=len(todos),
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


def get_export_payload() -> dict[str, Any]:
    """Return JSON-serializable snapshot of projects and todos."""
    with session_context() as session:
        projects = list(session.exec(select(Project).order_by(Project.created_at.asc())).all())
        todos = list(session.exec(select(Todo).order_by(Todo.created_at.asc())).all())
        return {
            "projects": [
                {
                    "id": project.id,
                    "name": project.name,
                    "created_at": project.created_at.isoformat(),
                    "is_archived": project.is_archived,
                }
                for project in projects
            ],
            "todos": [
                {
                    "id": todo.id,
                    "project_id": todo.project_id,
                    "name": todo.name,
                    "status": todo.status.value,
                    "deadline": todo.deadline.isoformat() if todo.deadline else None,
                    "helper": todo.helper,
                    "notes": todo.notes,
                    "created_at": todo.created_at.isoformat(),
                    "completed_at": todo.completed_at.isoformat() if todo.completed_at else None,
                    "is_archived": todo.is_archived,
                }
                for todo in todos
            ],
        }


def get_projects_with_todo_summary(*, include_archived: bool = False) -> list[dict[str, Any]]:
    """Return projects with aggregated todo status counts.

    Each item contains:

    - ``project``: The :class:`Project` instance.
    - ``total``: Total todos in the project.
    - ``delegated``: Todos with status ``delegated``.
    - ``done``: Todos with status ``done``.
    - ``canceled``: Todos with status ``canceled``.
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
            "delegated": 0,
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
        if todo.status == TodoStatus.DELEGATED:
            item["delegated"] += 1
        elif todo.status == TodoStatus.DONE:
            item["done"] += 1
        elif todo.status == TodoStatus.CANCELED:
            item["canceled"] += 1

    return [summary_by_project[project.id] for project in projects]
