"""Tests for Project, Handoff, and CheckIn models."""

from datetime import date, datetime

from sqlmodel import Session

from handoff.models import CheckIn, CheckInType, Handoff, Project


def test_create_project(session: Session) -> None:
    """Creating a project persists it and sets id and created_at."""
    p = Project(name="Engagement A")
    session.add(p)
    session.commit()
    session.refresh(p)
    assert p.id is not None
    assert p.name == "Engagement A"
    assert isinstance(p.created_at, datetime)


def test_create_handoff(session: Session) -> None:
    """Creating a handoff with project_id and optional fields works."""
    p = Project(name="Proj")
    session.add(p)
    session.commit()
    session.refresh(p)
    assert p.id is not None
    h = Handoff(project_id=p.id, need_back="Call client", pitchman="Alice")
    session.add(h)
    session.commit()
    session.refresh(h)
    assert h.id is not None
    assert h.project_id == p.id
    assert h.pitchman == "Alice"


def test_create_check_in(session: Session) -> None:
    """Creating a check-in linked to a handoff works."""
    p = Project(name="Proj")
    session.add(p)
    session.commit()
    session.refresh(p)
    h = Handoff(project_id=p.id, need_back="Task")
    session.add(h)
    session.commit()
    session.refresh(h)
    ci = CheckIn(
        handoff_id=h.id,
        check_in_date=date(2026, 3, 1),
        check_in_type=CheckInType.ON_TRACK,
        note="All good",
    )
    session.add(ci)
    session.commit()
    session.refresh(ci)
    assert ci.id is not None
    assert ci.handoff_id == h.id
    assert ci.check_in_type == CheckInType.ON_TRACK


def test_handoff_check_ins_relationship(session: Session) -> None:
    """Handoff.check_ins relationship loads the trail."""
    p = Project(name="Proj")
    session.add(p)
    session.commit()
    session.refresh(p)
    h = Handoff(project_id=p.id, need_back="Task")
    session.add(h)
    session.commit()
    session.refresh(h)
    ci1 = CheckIn(
        handoff_id=h.id,
        check_in_date=date(2026, 3, 1),
        check_in_type=CheckInType.ON_TRACK,
    )
    ci2 = CheckIn(
        handoff_id=h.id,
        check_in_date=date(2026, 3, 5),
        check_in_type=CheckInType.CONCLUDED,
        note="Done",
    )
    session.add_all([ci1, ci2])
    session.commit()
    session.refresh(h)
    assert len(h.check_ins) == 2
    types = [ci.check_in_type for ci in h.check_ins]
    assert CheckInType.ON_TRACK in types
    assert CheckInType.CONCLUDED in types
