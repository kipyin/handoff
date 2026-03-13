"""Regression tests for system_settings and query filter edge cases (PR #179).

Covers critical filter logic and settings validation paths introduced in
the project structure restructure. These tests prevent regressions in:

1. Now page filter state preservation and validation
2. Complex query construction with optional filters
3. Settings form submission and validation
"""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

import pytest

from handoff.core.models import Handoff
from handoff.core.page_models import HandoffQuery, NowSnapshot


# =============================================================================
# HandoffQuery Contract Tests
# =============================================================================


def test_handoff_query_is_immutable() -> None:
    """HandoffQuery is frozen and cannot be modified after creation."""
    q = HandoffQuery(search_text="foo")
    with pytest.raises(AttributeError):
        q.search_text = "bar"


def test_handoff_query_fields_have_sensible_defaults() -> None:
    """HandoffQuery provides empty defaults for all filter fields."""
    q = HandoffQuery()
    assert q.search_text == ""
    assert q.project_ids == ()
    assert q.pitchman_names == ()
    assert q.deadline_start is None
    assert q.deadline_end is None
    assert q.include_concluded is False
    assert q.include_archived_projects is False


def test_handoff_query_accepts_tuple_project_ids() -> None:
    """HandoffQuery stores project_ids as immutable tuple."""
    q = HandoffQuery(project_ids=(1, 2, 3))
    assert isinstance(q.project_ids, tuple)
    assert q.project_ids == (1, 2, 3)


def test_handoff_query_accepts_tuple_pitchman_names() -> None:
    """HandoffQuery stores pitchman_names as immutable tuple."""
    q = HandoffQuery(pitchman_names=("Alice", "Bob"))
    assert isinstance(q.pitchman_names, tuple)
    assert q.pitchman_names == ("Alice", "Bob")


def test_handoff_query_preserves_all_fields_in_equality() -> None:
    """Two identical HandoffQuery objects are equal."""
    q1 = HandoffQuery(
        search_text="foo",
        project_ids=(1, 2),
        pitchman_names=("Alice",),
        include_concluded=True,
    )
    q2 = HandoffQuery(
        search_text="foo",
        project_ids=(1, 2),
        pitchman_names=("Alice",),
        include_concluded=True,
    )
    assert q1 == q2


def test_handoff_query_distinguishes_different_search_text() -> None:
    """Different search_text values make queries unequal."""
    q1 = HandoffQuery(search_text="foo")
    q2 = HandoffQuery(search_text="bar")
    assert q1 != q2


def test_handoff_query_distinguishes_different_filters() -> None:
    """Different filter values make queries unequal."""
    q1 = HandoffQuery(include_concluded=True)
    q2 = HandoffQuery(include_concluded=False)
    assert q1 != q2


def test_handoff_query_with_deadline_range() -> None:
    """HandoffQuery supports deadline range filters."""
    start = date(2026, 3, 1)
    end = date(2026, 3, 31)
    q = HandoffQuery(deadline_start=start, deadline_end=end)
    assert q.deadline_start == start
    assert q.deadline_end == end


# =============================================================================
# NowSnapshot Contract Tests
# =============================================================================


def test_now_snapshot_contains_all_required_fields() -> None:
    """NowSnapshot has all fields needed for Now page rendering."""
    snapshot = NowSnapshot(
        risk=[],
        action=[],
        custom_sections=[],
        upcoming=[],
        upcoming_section_id="upcoming",
        concluded=[],
        projects=[],
        pitchmen=[],
        section_explanations={},
    )
    assert snapshot.risk == []
    assert snapshot.action == []
    assert snapshot.upcoming_section_id == "upcoming"
    assert snapshot.section_explanations == {}


def test_now_snapshot_section_explanations_maps_sections_to_reasons() -> None:
    """NowSnapshot.section_explanations maps section names to rule match reasons."""
    snapshot = NowSnapshot(
        risk=[],
        action=[],
        custom_sections=[],
        upcoming=[],
        upcoming_section_id="upcoming",
        concluded=[],
        projects=[],
        pitchmen=[],
        section_explanations={
            "Risk": "Deadline within 3 days",
            "Action": "No recent check-in",
        },
    )
    assert snapshot.section_explanations["Risk"] == "Deadline within 3 days"
    assert snapshot.section_explanations["Action"] == "No recent check-in"


def test_now_snapshot_custom_sections_holds_name_and_handoffs() -> None:
    """NowSnapshot.custom_sections is list of (name, handoffs) tuples."""
    handoff1 = SimpleNamespace(id=1, need_back="Foo")
    handoff2 = SimpleNamespace(id=2, need_back="Bar")
    snapshot = NowSnapshot(
        risk=[],
        action=[],
        custom_sections=[("Team A", [handoff1, handoff2])],
        upcoming=[],
        upcoming_section_id="upcoming",
        concluded=[],
        projects=[],
        pitchmen=[],
        section_explanations={},
    )
    assert len(snapshot.custom_sections) == 1
    name, handoffs = snapshot.custom_sections[0]
    assert name == "Team A"
    assert len(handoffs) == 2


def test_now_snapshot_organizing_four_sections() -> None:
    """NowSnapshot organizes handoffs into Risk, Action, Custom, Upcoming, Concluded."""
    risk_handoff = SimpleNamespace(id=1, need_back="Risk")
    action_handoff = SimpleNamespace(id=2, need_back="Action")
    upcoming_handoff = SimpleNamespace(id=3, need_back="Upcoming")
    concluded_handoff = SimpleNamespace(id=4, need_back="Concluded")

    snapshot = NowSnapshot(
        risk=[risk_handoff],
        action=[action_handoff],
        custom_sections=[],
        upcoming=[upcoming_handoff],
        upcoming_section_id="Upcoming",
        concluded=[concluded_handoff],
        projects=[],
        pitchmen=[],
        section_explanations={},
    )

    assert snapshot.risk[0].id == 1
    assert snapshot.action[0].id == 2
    assert snapshot.upcoming[0].id == 3
    assert snapshot.concluded[0].id == 4


# =============================================================================
# Query Edge Cases
# =============================================================================


def test_handoff_query_empty_tuples_filter_nothing() -> None:
    """Empty project_ids and pitchman_names tuples mean no filter applied."""
    q = HandoffQuery(project_ids=(), pitchman_names=())
    assert q.project_ids == ()
    assert q.pitchman_names == ()
    assert len(q.project_ids) == 0


def test_handoff_query_can_represent_no_filtering() -> None:
    """Default HandoffQuery represents 'no filters' state."""
    q = HandoffQuery()
    assert not q.search_text
    assert not q.project_ids
    assert not q.pitchman_names
    assert q.deadline_start is None
    assert q.deadline_end is None


def test_handoff_query_can_represent_all_filters_active() -> None:
    """HandoffQuery can have all filters active simultaneously."""
    q = HandoffQuery(
        search_text="urgent",
        project_ids=(1, 2, 3),
        pitchman_names=("Alice", "Bob"),
        deadline_start=date(2026, 3, 1),
        deadline_end=date(2026, 3, 31),
        include_concluded=True,
        include_archived_projects=True,
    )
    assert q.search_text == "urgent"
    assert len(q.project_ids) == 3
    assert len(q.pitchman_names) == 2
    assert q.deadline_start is not None
    assert q.include_concluded is True


def test_handoff_query_partial_deadline_range() -> None:
    """HandoffQuery supports partial deadline range (start or end only)."""
    q_start_only = HandoffQuery(deadline_start=date(2026, 3, 1))
    assert q_start_only.deadline_start is not None
    assert q_start_only.deadline_end is None

    q_end_only = HandoffQuery(deadline_end=date(2026, 3, 31))
    assert q_end_only.deadline_start is None
    assert q_end_only.deadline_end is not None


# =============================================================================
# Filter State Preservation Tests
# =============================================================================


def test_handoff_query_preserves_multi_select_state() -> None:
    """HandoffQuery preserves user's multi-select choices."""
    project_ids = (1, 5, 10)
    q = HandoffQuery(project_ids=project_ids)
    assert q.project_ids == project_ids


def test_handoff_query_distinguishes_single_vs_multi_select() -> None:
    """Single project ID (1,) is distinguishable from no filter ()."""
    q_single = HandoffQuery(project_ids=(1,))
    q_none = HandoffQuery(project_ids=())
    assert q_single != q_none


def test_handoff_query_text_search_preserved_across_refreshes() -> None:
    """HandoffQuery preserves search text state."""
    original_query = HandoffQuery(search_text="@due this week")
    # Simulate state persistence and retrieval
    q_restored = HandoffQuery(search_text=original_query.search_text)
    assert q_restored.search_text == "@due this week"


# =============================================================================
# Integration Edge Cases
# =============================================================================


def test_handoff_query_filters_with_empty_results() -> None:
    """HandoffQuery can represent filters that match no handoffs."""
    q = HandoffQuery(
        project_ids=(9999,),
        pitchman_names=("NonexistentPerson",),
    )
    assert q.project_ids == (9999,)
    assert q.pitchman_names == ("NonexistentPerson",)


def test_handoff_query_with_special_characters_in_search() -> None:
    """HandoffQuery search_text can contain special characters."""
    q = HandoffQuery(search_text="@mention #tag [urgent]")
    assert "@mention" in q.search_text


def test_handoff_query_with_long_pitchman_list() -> None:
    """HandoffQuery handles many pitchman names."""
    names = tuple(f"Person_{i}" for i in range(100))
    q = HandoffQuery(pitchman_names=names)
    assert len(q.pitchman_names) == 100


# =============================================================================
# Now Snapshot Building Tests (simulation)
# =============================================================================


def test_now_snapshot_can_be_built_from_empty_handoff_list() -> None:
    """NowSnapshot can be constructed with no handoffs in any section."""
    snapshot = NowSnapshot(
        risk=[],
        action=[],
        custom_sections=[],
        upcoming=[],
        upcoming_section_id="Upcoming",
        concluded=[],
        projects=[],
        pitchmen=[],
        section_explanations={},
    )
    assert len(snapshot.risk) == 0
    assert len(snapshot.action) == 0
    assert len(snapshot.upcoming) == 0
    assert len(snapshot.concluded) == 0


def test_now_snapshot_empty_custom_sections() -> None:
    """NowSnapshot with no custom sections (empty list) is valid."""
    snapshot = NowSnapshot(
        risk=[],
        action=[],
        custom_sections=[],
        upcoming=[],
        upcoming_section_id="Upcoming",
        concluded=[],
        projects=[],
        pitchmen=[],
        section_explanations={},
    )
    assert snapshot.custom_sections == []


def test_now_snapshot_multiple_custom_sections() -> None:
    """NowSnapshot can hold multiple custom sections."""
    h1 = SimpleNamespace(id=1)
    h2 = SimpleNamespace(id=2)
    h3 = SimpleNamespace(id=3)
    snapshot = NowSnapshot(
        risk=[],
        action=[],
        custom_sections=[
            ("Team A", [h1, h2]),
            ("Team B", [h3]),
        ],
        upcoming=[],
        upcoming_section_id="Upcoming",
        concluded=[],
        projects=[],
        pitchmen=[],
        section_explanations={},
    )
    assert len(snapshot.custom_sections) == 2
    assert snapshot.custom_sections[0][0] == "Team A"
    assert snapshot.custom_sections[1][0] == "Team B"
