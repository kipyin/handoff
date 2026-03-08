"""Todo service boundary between UI pages and the data layer."""

from __future__ import annotations

from datetime import date, datetime

from handoff.data import create_todo as _create_todo
from handoff.data import delete_todo as _delete_todo
from handoff.data import list_helpers as _list_helpers
from handoff.data import query_todos as _query_todos
from handoff.data import update_todo as _update_todo
from handoff.models import Todo, TodoStatus
from handoff.page_models import TodoQuery


def create_todo(
    project_id: int,
    name: str,
    status: TodoStatus = TodoStatus.HANDOFF,
    deadline: date | None = None,
    helper: str | list[str] | None = None,
    notes: str | None = None,
) -> Todo:
    """Create a todo through the service boundary."""
    return _create_todo(
        project_id=project_id,
        name=name,
        status=status,
        deadline=deadline,
        helper=helper,
        notes=notes,
    )


def update_todo(todo_id: int, **changes) -> Todo | None:
    """Update a todo through the service boundary."""
    return _update_todo(todo_id, **changes)


def delete_todo(todo_id: int) -> bool:
    """Delete a todo through the service boundary."""
    return _delete_todo(todo_id)


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
    """Query todos through the service boundary."""
    return _query_todos(
        query=query,
        project_ids=project_ids,
        helper_name=helper_name,
        helper_names=helper_names,
        statuses=statuses,
        start=start,
        end=end,
        completed_start=completed_start,
        completed_end=completed_end,
        search_text=search_text,
        include_archived=include_archived,
    )


def list_helpers() -> list[str]:
    """List known helper names through the service boundary."""
    return _list_helpers()


def complete_todo(todo_id: int) -> Todo | None:
    """Mark a todo as done.

    Future: will also log to activity trail, check recurrence, update metrics.
    For now delegates to data.update_todo.

    Args:
        todo_id: Id of the todo to complete.

    Returns:
        Updated todo, or None if not found.

    """
    return _update_todo(todo_id, status=TodoStatus.DONE)
