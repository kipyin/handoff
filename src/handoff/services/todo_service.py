"""Todo use-case orchestration.

Marks todos complete and will eventually coordinate activity logging,
recurrence, and metrics. For now delegates to data.update_todo.
"""

from __future__ import annotations

from handoff.data import update_todo
from handoff.models import Todo, TodoStatus


def complete_todo(todo_id: int) -> Todo | None:
    """Mark a todo as done.

    Future: will also log to activity trail, check recurrence, update metrics.
    For now delegates to data.update_todo.

    Args:
        todo_id: Id of the todo to complete.

    Returns:
        Updated todo, or None if not found.

    """
    return update_todo(todo_id, status=TodoStatus.DONE)
