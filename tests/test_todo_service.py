"""Tests for handoff service layer."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date
from types import SimpleNamespace

import pytest

import handoff.data as data
from handoff.models import CheckInType, Handoff, Project
from handoff.services import (
    add_check_in,
    conclude_handoff,
    create_handoff,
    delete_handoff,
    get_handoff_close_date,
    get_now_snapshot,
    list_pitchmen,
    list_pitchmen_with_open_handoffs,
    query_action_handoffs,
    query_concluded_handoffs,
    query_handoffs,
    query_now_items,
    query_risk_handoffs,
    query_upcoming_handoffs,
    reopen_handoff,
    snooze_handoff,
    update_handoff,
)


def _patch_session_context(monkeypatch, session) -> None:
    """Patch session_context in all data sub-modules to reuse the test session.

    Each sub-module imports session_context directly, so all five must be
    patched: activity (log_activity), handoffs (CRUD), io (import/export),
    projects (project CRUD), queries (queries).
    """
    import handoff.data.activity as _da
    import handoff.data.handoffs as _dh
    import handoff.data.io as _dio
    import handoff.data.projects as _dp
    import handoff.data.queries as _dq

    @contextmanager
    def _session_context():
        yield session

    for mod in (_da, _dh, _dio, _dp, _dq):
        monkeypatch.setattr(mod, "session_context", _session_context)


def _patch_date(monkeypatch, fixed_date_class) -> None:
    """Patch date.today() in sub-modules that call it directly.

    Only handoffs (conclude_handoff, reopen_handoff) and queries
    (query_now_items, query_upcoming_handoffs, query_action_handoffs,
    query_risk_handoffs) call date.today(); the other sub-modules do not.
    """
    import handoff.data.handoffs as _dh
    import handoff.data.queries as _dq

    monkeypatch.setattr(_dh, "date", fixed_date_class)
    monkeypatch.setattr(_dq, "date", fixed_date_class)


def test_service_create_handoff_with_next_check(session, monkeypatch) -> None:
    """create_handoff passes next_check through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = create_handoff(
        project_id=p.id,
        need_back="Follow up",
        next_check=date(2026, 1, 15),
        pitchman="Alice",
    )
    assert handoff.id is not None
    assert handoff.next_check == date(2026, 1, 15)
    assert handoff.pitchman == "Alice"


def test_service_query_action_handoffs(session, monkeypatch) -> None:
    """query_action_handoffs returns due open handoffs through the service boundary."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(
        project_id=p.id,
        need_back="Due",
        next_check=date(2000, 1, 1),
    )
    data.create_handoff(
        project_id=p.id,
        need_back="Later",
        next_check=date(2030, 1, 1),
    )

    results = query_action_handoffs()
    names = [r.need_back for r in results]
    assert "Due" in names
    assert "Later" not in names


def test_service_query_action_handoffs_include_archived_projects(session, monkeypatch) -> None:
    """query_action_handoffs includes archived projects when explicitly requested."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    active = Project(name="Active")
    archived = Project(name="Archived", is_archived=True)
    session.add_all([active, archived])
    session.commit()

    data.create_handoff(
        project_id=active.id,
        need_back="Active due",
        next_check=date(2026, 3, 9),
    )
    data.create_handoff(
        project_id=archived.id,
        need_back="Archived due",
        next_check=date(2026, 3, 9),
    )

    default_names = [h.need_back for h in query_action_handoffs()]
    assert "Active due" in default_names
    assert "Archived due" not in default_names

    all_names = [h.need_back for h in query_action_handoffs(include_archived_projects=True)]
    assert "Active due" in all_names
    assert "Archived due" in all_names


def test_service_add_check_in_updates_next_check(session, monkeypatch) -> None:
    """add_check_in creates a check-in and updates handoff.next_check."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = create_handoff(
        project_id=p.id,
        need_back="Follow-up needed",
        next_check=date(2026, 3, 9),
    )
    assert handoff.id is not None

    check_in = add_check_in(
        handoff.id,
        check_in_type=CheckInType.ON_TRACK,
        note="Looks good",
        next_check_date=date(2026, 3, 16),
        check_in_date=date(2026, 3, 9),
    )
    assert check_in.check_in_type == CheckInType.ON_TRACK
    refreshed = session.get(Handoff, handoff.id)
    assert refreshed is not None
    assert refreshed.next_check == date(2026, 3, 16)


def test_service_update_handoff(session, monkeypatch) -> None:
    """update_handoff persists field changes through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(project_id=p.id, need_back="Original")
    assert handoff.id is not None

    updated = update_handoff(handoff.id, need_back="Updated")
    assert updated is not None
    assert updated.need_back == "Updated"


def test_service_snooze_handoff_updates_next_check(session, monkeypatch) -> None:
    """snooze_handoff updates only next_check through service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(
        project_id=p.id,
        need_back="Snooze me",
        next_check=date(2026, 3, 9),
    )
    assert handoff.id is not None

    updated = snooze_handoff(handoff.id, to_date=date(2026, 3, 15))
    assert updated is not None
    assert updated.next_check == date(2026, 3, 15)
    assert updated.need_back == "Snooze me"


def test_service_delete_handoff(session, monkeypatch) -> None:
    """delete_handoff removes the handoff through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(project_id=p.id, need_back="To delete")
    assert handoff.id is not None

    result = delete_handoff(handoff.id)
    assert result is True
    assert session.get(Handoff, handoff.id) is None


def test_service_query_handoffs(session, monkeypatch) -> None:
    """query_handoffs returns matching handoffs through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h1 = data.create_handoff(project_id=p.id, need_back="Alpha")
    h2 = data.create_handoff(project_id=p.id, need_back="Beta")
    assert h1.id is not None
    assert h2.id is not None

    results = query_handoffs(project_ids=[p.id])
    names = [r.need_back for r in results]
    assert "Alpha" in names
    assert "Beta" in names


def test_service_list_pitchmen(session, monkeypatch) -> None:
    """list_pitchmen returns all distinct pitchman names."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(project_id=p.id, need_back="A", pitchman="Alice")
    data.create_handoff(project_id=p.id, need_back="B", pitchman="Bob")

    names = list_pitchmen()
    assert "Alice" in names
    assert "Bob" in names


def test_service_list_pitchmen_with_open_handoffs(session, monkeypatch) -> None:
    """list_pitchmen_with_open_handoffs returns only pitchmen with open handoffs."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(project_id=p.id, need_back="Open", pitchman="Alice")

    names = list_pitchmen_with_open_handoffs()
    assert "Alice" in names


def test_service_query_now_items(session, monkeypatch) -> None:
    """query_now_items returns due open handoffs through the service boundary."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(project_id=p.id, need_back="Due", next_check=date(2000, 1, 1))
    data.create_handoff(project_id=p.id, need_back="Later", next_check=date(2030, 1, 1))

    results = query_now_items()
    names = [h.need_back for h, _ in results]
    assert "Due" in names
    assert "Later" not in names


def test_service_reopen_handoff_conclude_then_open_again(session, monkeypatch) -> None:
    """Service reopen flow appends check-in and returns item to open queries."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = create_handoff(
        project_id=p.id,
        need_back="Conclude then reopen",
        next_check=date(2026, 3, 9),
    )
    assert handoff.id is not None

    concluded = conclude_handoff(handoff.id, note="done")
    assert concluded.check_in_type == CheckInType.CONCLUDED

    reopened = reopen_handoff(
        handoff.id,
        note="reopen: waiting on revised doc",
        next_check_date=date(2026, 3, 9),
    )
    assert reopened.check_in_type == CheckInType.ON_TRACK
    assert reopened.check_in_date == date(2026, 3, 9)

    action_names = [h.need_back for h in query_action_handoffs()]
    concluded_names = [h.need_back for h in query_concluded_handoffs()]
    assert "Conclude then reopen" in action_names
    assert "Conclude then reopen" not in concluded_names


def test_service_reopen_handoff_rejects_open_item(session, monkeypatch) -> None:
    """Service reopen rejects handoffs whose latest check-in is not concluded."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = create_handoff(project_id=p.id, need_back="Already open")
    assert handoff.id is not None

    with pytest.raises(ValueError, match="latest check-in is concluded"):
        reopen_handoff(handoff.id)


def test_service_query_risk_handoffs(session, monkeypatch) -> None:
    """query_risk_handoffs returns at-risk handoffs through the service boundary."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    # At-risk: deadline within 1 day AND latest check-in is DELAYED.
    h = data.create_handoff(
        project_id=p.id,
        need_back="At risk",
        next_check=date(2000, 1, 1),
        deadline=date(2026, 3, 9),
    )
    assert h.id is not None
    data.create_check_in(
        handoff_id=h.id,
        check_in_type=CheckInType.DELAYED,
        check_in_date=date(2026, 3, 9),
    )

    results = query_risk_handoffs(deadline_near_days=1)
    names = [r.need_back for r in results]
    assert "At risk" in names


def test_service_query_risk_handoffs_include_archived_projects(session, monkeypatch) -> None:
    """query_risk_handoffs forwards include_archived_projects to data layer."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    active = Project(name="Active")
    archived = Project(name="Archived", is_archived=True)
    session.add_all([active, archived])
    session.commit()

    active_handoff = data.create_handoff(
        project_id=active.id,
        need_back="Active risk",
        deadline=date(2026, 3, 10),
    )
    archived_handoff = data.create_handoff(
        project_id=archived.id,
        need_back="Archived risk",
        deadline=date(2026, 3, 10),
    )
    data.create_check_in(
        handoff_id=active_handoff.id,
        check_in_type=CheckInType.DELAYED,
        check_in_date=date(2026, 3, 9),
    )
    data.create_check_in(
        handoff_id=archived_handoff.id,
        check_in_type=CheckInType.DELAYED,
        check_in_date=date(2026, 3, 9),
    )

    default_names = [h.need_back for h in query_risk_handoffs(deadline_near_days=1)]
    assert "Active risk" in default_names
    assert "Archived risk" not in default_names

    all_names = [
        h.need_back
        for h in query_risk_handoffs(deadline_near_days=1, include_archived_projects=True)
    ]
    assert "Active risk" in all_names
    assert "Archived risk" in all_names


def test_service_get_now_snapshot_contract(session, monkeypatch) -> None:
    """get_now_snapshot returns a NowSnapshot with all sections and supporting data."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)
    monkeypatch.setattr(
        "handoff.services.handoff_service.get_deadline_near_days",
        lambda: 1,
    )

    p = Project(name="Work")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(
        project_id=p.id,
        need_back="Action due",
        next_check=date(2026, 3, 9),
    )

    snapshot = get_now_snapshot()

    assert hasattr(snapshot, "risk")
    assert hasattr(snapshot, "action")
    assert hasattr(snapshot, "upcoming")
    assert hasattr(snapshot, "concluded")
    assert hasattr(snapshot, "projects")
    assert hasattr(snapshot, "pitchmen")
    assert isinstance(snapshot.risk, list)
    assert isinstance(snapshot.action, list)
    assert isinstance(snapshot.upcoming, list)
    assert isinstance(snapshot.concluded, list)
    assert isinstance(snapshot.projects, list)
    assert isinstance(snapshot.pitchmen, list)


def test_service_get_now_snapshot_default_section_counts(session, monkeypatch) -> None:
    """get_now_snapshot places handoffs in correct sections by default semantics."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)
    monkeypatch.setattr(
        "handoff.services.handoff_service.get_deadline_near_days",
        lambda: 1,
    )

    p = Project(name="Work")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(
        project_id=p.id,
        need_back="Due now",
        next_check=date(2026, 3, 9),
    )
    data.create_handoff(
        project_id=p.id,
        need_back="Later",
        next_check=date(2026, 4, 1),
    )
    risk_h = data.create_handoff(
        project_id=p.id,
        need_back="At risk",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 10),
    )
    data.create_check_in(
        handoff_id=risk_h.id,
        check_in_type=CheckInType.DELAYED,
        check_in_date=date(2026, 3, 9),
    )
    concluded_h = data.create_handoff(
        project_id=p.id,
        need_back="Closed",
        next_check=date(2026, 3, 9),
    )
    data.create_check_in(
        handoff_id=concluded_h.id,
        check_in_type=CheckInType.CONCLUDED,
        check_in_date=date(2026, 3, 9),
    )

    snapshot = get_now_snapshot()

    risk_names = [h.need_back for h in snapshot.risk]
    action_names = [h.need_back for h in snapshot.action]
    upcoming_names = [h.need_back for h in snapshot.upcoming]
    concluded_names = [h.need_back for h in snapshot.concluded]

    assert "At risk" in risk_names
    assert "Due now" in action_names
    assert "Later" in upcoming_names
    assert "Closed" in concluded_names
    assert len(snapshot.projects) >= 1
    assert snapshot.projects[0].name == "Work"


def test_service_get_now_snapshot_forwards_parsed_filters(monkeypatch) -> None:
    """Snapshot query fan-out uses parsed search/date filters for risk/action/upcoming sections."""
    parsed = SimpleNamespace(
        text_query="release gate",
        next_check_min=date(2026, 3, 1),
        next_check_max=date(2026, 3, 31),
        deadline_min=date(2026, 3, 5),
        deadline_max=date(2026, 4, 5),
    )
    monkeypatch.setattr("handoff.services.handoff_service.parse_search_query", lambda _: parsed)
    monkeypatch.setattr("handoff.services.handoff_service.get_deadline_near_days", lambda: 3)

    risk_calls: list[dict[str, object]] = []
    action_calls: list[dict[str, object]] = []
    upcoming_calls: list[dict[str, object]] = []
    concluded_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.services.handoff_service.query_risk_handoffs",
        lambda **kwargs: risk_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        "handoff.services.handoff_service.query_action_handoffs",
        lambda **kwargs: action_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        "handoff.services.handoff_service.query_upcoming_handoffs",
        lambda **kwargs: upcoming_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        "handoff.services.handoff_service.query_concluded_handoffs",
        lambda **kwargs: concluded_calls.append(kwargs) or [],
    )

    list_projects_calls: list[dict[str, object]] = []
    list_pitchmen_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.services.handoff_service.list_projects",
        lambda **kwargs: list_projects_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        "handoff.services.handoff_service.list_pitchmen_with_open_handoffs",
        lambda **kwargs: list_pitchmen_calls.append(kwargs) or [],
    )

    get_now_snapshot(
        include_archived_projects=True,
        project_ids=[7],
        pitchman_names=["Alice"],
        search_text="@this_week release gate",
    )

    open_expected = {
        "project_ids": [7],
        "pitchman_names": ["Alice"],
        "search_text": "release gate",
        "deadline_near_days": 3,
        "next_check_min": date(2026, 3, 1),
        "next_check_max": date(2026, 3, 31),
        "deadline_min": date(2026, 3, 5),
        "deadline_max": date(2026, 4, 5),
        "include_archived_projects": True,
    }
    concluded_expected = {
        "project_ids": [7],
        "pitchman_names": ["Alice"],
        "search_text": "release gate",
        "include_archived_projects": True,
    }
    assert risk_calls == [open_expected]
    assert action_calls == [open_expected]
    assert upcoming_calls == [open_expected]
    assert concluded_calls == [concluded_expected]
    assert list_projects_calls == [{"include_archived": True}]
    assert list_pitchmen_calls == [{"include_archived_projects": True}]


def test_service_get_now_snapshot_uses_prefetched_supporting_data(monkeypatch) -> None:
    """Prefetched projects/pitchmen bypass extra list queries in snapshot service."""
    parsed = SimpleNamespace(
        text_query="",
        next_check_min=None,
        next_check_max=None,
        deadline_min=None,
        deadline_max=None,
    )
    monkeypatch.setattr("handoff.services.handoff_service.parse_search_query", lambda _: parsed)
    monkeypatch.setattr("handoff.services.handoff_service.get_deadline_near_days", lambda: 1)
    monkeypatch.setattr("handoff.services.handoff_service.query_risk_handoffs", lambda **_: [])
    monkeypatch.setattr("handoff.services.handoff_service.query_action_handoffs", lambda **_: [])
    monkeypatch.setattr("handoff.services.handoff_service.query_upcoming_handoffs", lambda **_: [])
    monkeypatch.setattr("handoff.services.handoff_service.query_concluded_handoffs", lambda **_: [])
    monkeypatch.setattr(
        "handoff.services.handoff_service.list_projects",
        lambda **_: pytest.fail("list_projects should not be called when projects are pre-fetched"),
    )
    monkeypatch.setattr(
        "handoff.services.handoff_service.list_pitchmen_with_open_handoffs",
        lambda **_: pytest.fail("list_pitchmen_with_open_handoffs should not be called"),
    )

    prefetched_projects = [Project(name="Prefetched")]
    prefetched_pitchmen = ["Alice", "Bob"]

    snapshot = get_now_snapshot(projects=prefetched_projects, pitchmen=prefetched_pitchmen)

    assert snapshot.projects is prefetched_projects
    assert snapshot.pitchmen is prefetched_pitchmen


def test_service_query_upcoming_handoffs(session, monkeypatch) -> None:
    """query_upcoming_handoffs returns non-action, non-risk open handoffs.

    This includes handoffs with a future next_check and handoffs with no
    next_check when they are otherwise not in Risk/Action.
    """
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    data.create_handoff(project_id=p.id, need_back="Upcoming", next_check=date(2026, 4, 1))
    data.create_handoff(project_id=p.id, need_back="No next check", next_check=None)
    data.create_handoff(project_id=p.id, need_back="Overdue", next_check=date(2000, 1, 1))

    results = query_upcoming_handoffs()
    names = [r.need_back for r in results]
    assert "Upcoming" in names
    assert "No next check" in names
    assert "Overdue" not in names


def test_service_query_upcoming_and_pitchmen_include_archived(session, monkeypatch) -> None:
    """Upcoming and pitchman service wrappers include archived when requested."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)

    active = Project(name="Active")
    archived = Project(name="Archived", is_archived=True)
    session.add_all([active, archived])
    session.commit()

    data.create_handoff(
        project_id=active.id,
        need_back="Active upcoming",
        next_check=date(2026, 3, 10),
        pitchman="Alice",
    )
    data.create_handoff(
        project_id=archived.id,
        need_back="Archived upcoming",
        next_check=date(2026, 3, 10),
        pitchman="Bob",
    )

    default_upcoming = [h.need_back for h in query_upcoming_handoffs()]
    assert "Active upcoming" in default_upcoming
    assert "Archived upcoming" not in default_upcoming

    all_upcoming = [h.need_back for h in query_upcoming_handoffs(include_archived_projects=True)]
    assert "Active upcoming" in all_upcoming
    assert "Archived upcoming" in all_upcoming

    default_pitchmen = list_pitchmen_with_open_handoffs()
    assert "Alice" in default_pitchmen
    assert "Bob" not in default_pitchmen

    all_pitchmen = list_pitchmen_with_open_handoffs(include_archived_projects=True)
    assert "Alice" in all_pitchmen
    assert "Bob" in all_pitchmen


def test_service_query_concluded_handoffs(session, monkeypatch) -> None:
    """query_concluded_handoffs returns handoffs with a concluded check-in."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = data.create_handoff(project_id=p.id, need_back="Conclude me")
    assert h.id is not None
    data.conclude_handoff(h.id)

    results = query_concluded_handoffs()
    names = [r.need_back for r in results]
    assert "Conclude me" in names


def test_service_query_concluded_handoffs_include_archived_projects(session, monkeypatch) -> None:
    """Concluded wrapper forwards include_archived_projects and search filters."""
    _patch_session_context(monkeypatch, session)

    active = Project(name="Active")
    archived = Project(name="Archived", is_archived=True)
    session.add_all([active, archived])
    session.commit()

    active_handoff = data.create_handoff(
        project_id=active.id,
        need_back="Active done",
        pitchman="Alice",
    )
    archived_handoff = data.create_handoff(
        project_id=archived.id,
        need_back="Archived done",
        pitchman="Bob",
    )
    data.create_check_in(
        handoff_id=active_handoff.id,
        check_in_type=CheckInType.CONCLUDED,
        check_in_date=date(2026, 3, 9),
        note="release gate complete",
    )
    data.create_check_in(
        handoff_id=archived_handoff.id,
        check_in_type=CheckInType.CONCLUDED,
        check_in_date=date(2026, 3, 9),
    )

    default_names = [h.need_back for h in query_concluded_handoffs()]
    assert "Active done" in default_names
    assert "Archived done" in default_names

    active_only_names = [
        h.need_back
        for h in query_concluded_handoffs(
            include_archived_projects=False,
            search_text="release gate",
        )
    ]
    assert active_only_names == ["Active done"]


def test_service_conclude_handoff(session, monkeypatch) -> None:
    """conclude_handoff creates a concluded check-in through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = data.create_handoff(project_id=p.id, need_back="Wrap up")
    assert h.id is not None

    check_in = conclude_handoff(h.id, note="All done.")
    assert check_in.check_in_type == CheckInType.CONCLUDED
    assert check_in.note == "All done."


def test_service_get_handoff_close_date(session, monkeypatch) -> None:
    """get_handoff_close_date returns the conclusion date for a closed handoff."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = data.create_handoff(project_id=p.id, need_back="Close me")
    assert h.id is not None
    data.conclude_handoff(h.id)
    refreshed = session.get(Handoff, h.id)
    assert refreshed is not None

    close_date = get_handoff_close_date(refreshed)
    assert close_date == date.today()
