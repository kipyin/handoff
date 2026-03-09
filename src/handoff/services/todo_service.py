"""Todo service boundary between UI pages and the data layer."""

from __future__ import annotations

from datetime import date, datetime

from handoff.data import create_todo as _create_todo
from handoff.data import delete_todo as _delete_todo
from handoff.data import list_helpers as _list_helpers
from handoff.data import list_helpers_with_open_handoffs as _list_helpers_with_open_handoffs
from handoff.data import query_now_items as _query_now_items
from handoff.data import query_todos as _query_todos
from handoff.data import query_upcoming_handoffs as _query_upcoming_handoffs
from handoff.data import snooze_todo as _snooze_todo
from handoff.data import update_todo as _update_todo
from handoff.models import Todo, TodoStatus
from handoff.page_models import TodoQuery


def create_todo(
    project_id: int,
    name: str,
    status: TodoStatus = TodoStatus.HANDOFF,
    next_check: date | None = None,
    deadline: date | None = None,
    helper: str | list[str] | None = None,
    notes: str | None = None,
) -> Todo:
    """Create a todo through the service boundary."""
    return _create_todo(
        project_id=project_id,
        name=name,
        status=status,
        next_check=next_check,
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


def list_helpers_with_open_handoffs() -> list[str]:
    """List helpers who have at least one open handoff. For Now page Who filter."""
    return _list_helpers_with_open_handoffs()


def query_now_items(
    *,
    project_ids: list[int] | None = None,
    helper_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 1,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
) -> list[tuple[Todo, bool]]:
    """Return open items that need attention on the Now page.

    Items need attention when next_check is due today or earlier, or deadline
    is within deadline_near_days. Returns (todo, at_risk) tuples.
    """
    return _query_now_items(
        project_ids=project_ids,
        helper_names=helper_names,
        search_text=search_text,
        deadline_near_days=deadline_near_days,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
    )


def query_upcoming_handoffs(
    *,
    project_ids: list[int] | None = None,
    helper_names: list[str] | None = None,
    search_text: str | None = None,
    deadline_near_days: int = 1,
    limit: int = 20,
    next_check_min: date | None = None,
    next_check_max: date | None = None,
    deadline_min: date | None = None,
    deadline_max: date | None = None,
) -> list[Todo]:
    """Return handoffs that are not yet action-required (upcoming).

    Items with next_check in the future and deadline not at risk.
    """
    return _query_upcoming_handoffs(
        project_ids=project_ids,
        helper_names=helper_names,
        search_text=search_text,
        deadline_near_days=deadline_near_days,
        limit=limit,
        next_check_min=next_check_min,
        next_check_max=next_check_max,
        deadline_min=deadline_min,
        deadline_max=deadline_max,
    )


def snooze_todo(todo_id: int, *, to_date: date) -> Todo | None:
    """Update a todo's next_check date. Does not change deadline."""
    return _snooze_todo(todo_id, to_date=to_date)


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
