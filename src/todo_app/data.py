"""Data access: create/read projects and todos, and query by project, helper, or timeframe."""

from datetime import datetime
from typing import Optional

from loguru import logger
from sqlmodel import Session, select

from todo_app.db import session_context
from todo_app.models import Project, Todo, TodoStatus


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


def get_project(project_id: int) -> Optional[Project]:
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
    deadline: Optional[datetime] = None,
    helper: Optional[str] = None,
    notes: Optional[str] = None,
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
            helper=helper or None,
            notes=notes or None,
        )
        session.add(todo)
        session.commit()
        session.refresh(todo)
        return todo


def update_todo(
    todo_id: int,
    *,
    project_id: Optional[int] = None,
    name: Optional[str] = None,
    status: Optional[TodoStatus] = None,
    deadline: Optional[datetime] = None,
    helper: Optional[str] = None,
    notes: Optional[str] = None,
) -> Optional[Todo]:
    """Update a todo by id. Only provided fields are updated."""
    with session_context() as session:
        todo = session.get(Todo, todo_id)
        if not todo:
            logger.warning("Todo {todo_id} not found for update", todo_id=todo_id)
            return None
        if project_id is not None:
            todo.project_id = project_id
        if name is not None:
            todo.name = name
        if status is not None:
            todo.status = status
        if deadline is not None:
            todo.deadline = deadline
        if helper is not None:
            todo.helper = helper
        if notes is not None:
            todo.notes = notes
        session.add(todo)
        session.commit()
        session.refresh(todo)
        logger.info(
            "Updated todo {todo_id} in project {project_id} (status={status}, helper={helper}, deadline={deadline})",
            todo_id=todo.id,
            project_id=todo.project_id,
            status=todo.status.value,
            helper=todo.helper,
            deadline=todo.deadline,
        )
        return todo


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
        stmt = (
            select(Todo)
            .where(Todo.helper.ilike(f"%{helper_name}%"))
            .order_by(Todo.deadline.asc().nulls_last(), Todo.created_at.asc())
        )
        todos = list(session.exec(stmt).all())
        # Load project for display
        for t in todos:
            t.project = session.get(Project, t.project_id)
        logger.info(
            "Fetched {count} todos for helper {helper}",
            count=len(todos),
            helper=helper_name,
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
        return sorted({h.strip() for h in helpers if h and h.strip()})
