"""Data access helpers for projects/todos and common query workflows."""

from datetime import datetime
from typing import Any

from loguru import logger
from sqlmodel import select

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


def list_projects() -> list[Project]:
    """Return all projects ordered by creation (newest first)."""
    with session_context() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
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
        if status is not _UNSET:
            todo.status = status
        if deadline is not _UNSET:
            todo.deadline = deadline
        if helper is not _UNSET:
            todo.helper = normalize_helper_name(helper)
        if notes is not _UNSET:
            todo.notes = notes
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
        session.delete(todo)
        session.commit()
        logger.info("Deleted todo {todo_id}", todo_id=todo_id)
        return True


def get_todos_by_project(project_id: int) -> list[Todo]:
    """Return all todos for a project, ordered by deadline (nulls last) then created_at."""
    with session_context() as session:
        stmt = (
            select(Todo)
            .where(Todo.project_id == project_id)
            .order_by(Todo.deadline.asc().nulls_last(), Todo.created_at.asc())
        )
        todos = list(session.exec(stmt).all())
        logger.info(
            "Fetched {count} todos for project {project_id}",
            count=len(todos),
            project_id=project_id,
        )
        return todos


def get_todos_by_helper(helper_name: str) -> list[Todo]:
    """Return all todos across all projects assigned to the given helper."""
    with session_context() as session:
        normalized = normalize_helper_name(helper_name) or ""
        stmt = (
            select(Todo)
            .where(Todo.helper.ilike(f"%{normalized}%"))
            .order_by(Todo.deadline.asc().nulls_last(), Todo.created_at.asc())
        )
        todos = list(session.exec(stmt).all())
        # Load project for display
        for t in todos:
            t.project = session.get(Project, t.project_id)
        logger.info(
            "Fetched {count} todos for helper {helper}",
            count=len(todos),
            helper=normalized,
        )
        return todos


def get_todos_by_timeframe(
    start: datetime,
    end: datetime,
) -> list[Todo]:
    """Return all todos whose deadline falls within [start, end] (inclusive of day)."""
    with session_context() as session:
        # Compare by date; include todos with deadline on start or end day
        stmt = (
            select(Todo)
            .where(Todo.deadline.isnot(None))
            .where(Todo.deadline >= start)
            .where(Todo.deadline <= end)
            .order_by(Todo.deadline.asc())
        )
        todos = list(session.exec(stmt).all())
        for t in todos:
            t.project = session.get(Project, t.project_id)
        logger.info(
            "Fetched {count} todos between {start} and {end}",
            count=len(todos),
            start=start,
            end=end,
        )
        return todos


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
                }
                for todo in todos
            ],
        }
