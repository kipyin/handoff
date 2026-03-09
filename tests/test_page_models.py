"""Tests for page_models typed contracts."""

from __future__ import annotations

from handoff.models import TodoStatus
from handoff.page_models import TodoQuery


def test_todo_query_defaults() -> None:
    """TodoQuery has sensible defaults for empty query."""
    q = TodoQuery()
    assert q.search_text == ""
    assert q.statuses == ()
    assert q.project_ids == ()
    assert q.helper_names == ()
    assert q.deadline_start is None
    assert q.deadline_end is None
    assert q.include_archived is False


def test_todo_query_with_values() -> None:
    """TodoQuery accepts filter values."""
    q = TodoQuery(
        search_text="foo",
        statuses=(TodoStatus.HANDOFF, TodoStatus.DONE),
        project_ids=(1, 2),
        helper_names=("Alice",),
        include_archived=True,
    )
    assert q.search_text == "foo"
    assert q.statuses == (TodoStatus.HANDOFF, TodoStatus.DONE)
    assert q.project_ids == (1, 2)
    assert q.helper_names == ("Alice",)
    assert q.include_archived is True
