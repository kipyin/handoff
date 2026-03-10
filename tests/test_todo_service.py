"""Tests for handoff service layer."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import handoff.data as data
from handoff.models import CheckInType, Handoff, Project
from handoff.services import (
    add_check_in,
    create_handoff,
    list_pitchmen_with_open_handoffs,
    query_action_handoffs,
    query_concluded_handoffs,
    query_risk_handoffs,
    query_upcoming_handoffs,
    snooze_handoff,
)


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


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

    monkeypatch.setattr(data, "date", FixedDate)

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

    monkeypatch.setattr(data, "date", FixedDate)

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


def test_service_snooze_handoff(session, monkeypatch) -> None:
    """snooze_handoff updates next_check through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    handoff = data.create_handoff(
        project_id=p.id,
        need_back="Snooze me",
        next_check=date(2025, 1, 1),
    )
    assert handoff.id is not None

    updated = snooze_handoff(handoff.id, to_date=date(2026, 1, 15))
    assert updated is not None
    assert updated.next_check == date(2026, 1, 15)


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


def test_service_query_risk_handoffs_include_archived_projects(session, monkeypatch) -> None:
    """query_risk_handoffs forwards include_archived_projects to data layer."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr(data, "date", FixedDate)

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


def test_service_query_upcoming_and_pitchmen_include_archived(session, monkeypatch) -> None:
    """Upcoming and pitchman service wrappers include archived when requested."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr(data, "date", FixedDate)

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
