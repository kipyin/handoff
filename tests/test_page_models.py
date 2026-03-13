"""Tests for page_models typed contracts."""

from __future__ import annotations

from handoff.core.page_models import HandoffQuery


def test_handoff_query_defaults() -> None:
    """HandoffQuery has sensible defaults for empty query."""
    q = HandoffQuery()
    assert q.search_text == ""
    assert q.project_ids == ()
    assert q.pitchman_names == ()
    assert q.deadline_start is None
    assert q.deadline_end is None
    assert q.include_concluded is False
    assert q.include_archived_projects is False


def test_handoff_query_with_values() -> None:
    """HandoffQuery accepts filter values."""
    q = HandoffQuery(
        search_text="foo",
        project_ids=(1, 2),
        pitchman_names=("Alice",),
        include_concluded=True,
        include_archived_projects=True,
    )
    assert q.search_text == "foo"
    assert q.project_ids == (1, 2)
    assert q.pitchman_names == ("Alice",)
    assert q.include_concluded is True
    assert q.include_archived_projects is True
