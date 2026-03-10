"""Tests for data access helpers."""

import importlib
from contextlib import contextmanager
from datetime import date, datetime
from pathlib import Path

import pytest
from sqlmodel import select

import handoff.data as data
from handoff.models import CheckIn, CheckInType, Handoff, Project


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


def test_update_handoff_allows_clearing_fields(session, monkeypatch) -> None:
    """Update supports clearing deadline/pitchman/notes via explicit None-like values."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Alpha")
    session.add(project)
    session.commit()
    session.refresh(project)

    handoff = Handoff(
        project_id=project.id,
        need_back="Draft summary",
        deadline=datetime(2026, 1, 1, 12, 0),
        pitchman="Alice",
        notes="first",
    )
    session.add(handoff)
    session.commit()
    session.refresh(handoff)

    updated = data.update_handoff(handoff.id, deadline=None, pitchman=" ", notes=None)
    assert updated is not None
    assert updated.deadline is None
    assert updated.pitchman is None
    assert updated.notes is None


def test_delete_project_deletes_project_and_children(session, monkeypatch) -> None:
    """Deleting a project also removes its child handoffs."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Delete Me")
    session.add(project)
    session.commit()
    session.refresh(project)

    handoff = Handoff(project_id=project.id, need_back="child")
    session.add(handoff)
    session.commit()
    session.refresh(handoff)

    deleted = data.delete_project(project.id)
    assert deleted is True
    assert session.get(Project, project.id) is None
    assert session.get(Handoff, handoff.id) is None


def test_archive_and_unarchive_project(session, monkeypatch) -> None:
    """Archiving a project marks it; unarchiving clears the flag."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Archive Me")
    session.add(project)
    session.commit()
    session.refresh(project)

    archived = data.archive_project(project.id)
    assert archived is True
    session.refresh(project)
    assert project.is_archived is True

    unarchived = data.unarchive_project(project.id)
    assert unarchived is True
    session.refresh(project)
    assert project.is_archived is False


def test_get_export_payload_includes_projects_and_handoffs(session, monkeypatch) -> None:
    """Export payload returns serializable project, handoff, and check-in records."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Export")
    session.add(project)
    session.commit()
    session.refresh(project)

    handoff = Handoff(project_id=project.id, need_back="Export handoff")
    session.add(handoff)
    session.commit()
    session.refresh(handoff)

    ci = CheckIn(
        handoff_id=handoff.id,
        check_in_date=date(2026, 3, 1),
        check_in_type=CheckInType.CONCLUDED,
    )
    session.add(ci)
    session.commit()

    payload = data.get_export_payload()
    assert "projects" in payload
    assert "handoffs" in payload
    assert "check_ins" in payload
    assert len(payload["projects"]) == 1
    assert len(payload["handoffs"]) == 1
    assert len(payload["check_ins"]) == 1


def test_list_pitchmen_canonicalization(session, monkeypatch) -> None:
    """Verify that list_pitchmen handles case-insensitivity and trimming."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    session.add(Handoff(project_id=p.id, need_back="t1", pitchman="  Alice  "))
    session.add(Handoff(project_id=p.id, need_back="t2", pitchman="alice"))
    session.add(Handoff(project_id=p.id, need_back="t3", pitchman="BOB"))
    session.add(Handoff(project_id=p.id, need_back="t4", pitchman=None))
    session.commit()

    pitchmen = data.list_pitchmen()
    assert pitchmen == ["Alice", "BOB"]


def test_list_pitchmen_with_open_handoffs(session, monkeypatch) -> None:
    """list_pitchmen_with_open_handoffs returns only pitchmen with open handoffs."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    h1 = Handoff(project_id=p.id, need_back="t1", pitchman="Alice")
    h2 = Handoff(project_id=p.id, need_back="t2", pitchman="Bob")
    h3 = Handoff(project_id=p.id, need_back="t3", pitchman="Carol")
    session.add_all([h1, h2, h3])
    session.commit()
    session.refresh(h2)

    # Bob's handoff is concluded
    ci = CheckIn(
        handoff_id=h2.id,
        check_in_date=date(2026, 1, 1),
        check_in_type=CheckInType.CONCLUDED,
    )
    session.add(ci)
    session.commit()

    pitchmen = data.list_pitchmen_with_open_handoffs()
    assert "Alice" in pitchmen
    assert "Carol" in pitchmen
    assert "Bob" not in pitchmen


def test_query_handoffs_filters(session, monkeypatch) -> None:
    """Verify query_handoffs with multiple filter combinations."""
    _patch_session_context(monkeypatch, session)
    p1 = Project(name="P1")
    p2 = Project(name="P2")
    session.add_all([p1, p2])
    session.commit()

    h1 = Handoff(project_id=p1.id, need_back="Apple", pitchman="Alice")
    h2 = Handoff(project_id=p2.id, need_back="Banana", pitchman="Bob")
    session.add_all([h1, h2])
    session.commit()

    # Filter by search text (case-insensitive)
    results = data.query_handoffs(search_text="nan", include_concluded=True)
    assert len(results) == 1
    assert results[0].need_back == "Banana"

    # Filter by project
    results = data.query_handoffs(project_ids=[p1.id], include_concluded=True)
    assert len(results) == 1
    assert results[0].need_back == "Apple"


def test_query_handoffs_search_includes_check_in_notes(session, monkeypatch) -> None:
    """query_handoffs search text matches check-in notes."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(project_id=p.id, need_back="Unrelated title", notes="none")
    session.add(h)
    session.commit()
    session.refresh(h)

    session.add(
        CheckIn(
            handoff_id=h.id,
            check_in_date=date(2026, 3, 9),
            check_in_type=CheckInType.DELAYED,
            note="Need assumption doc X before proceeding",
        )
    )
    session.commit()

    results = data.query_handoffs(search_text="assumption doc X", include_concluded=True)
    assert len(results) == 1
    assert results[0].id == h.id


def test_create_handoff_with_list_pitchman(session, monkeypatch) -> None:
    """Verify _pitchman_to_db logic when a list is passed (from UI multiselects)."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    handoff = data.create_handoff(p.id, "Task", pitchman=["", "  Charlie  ", "Dave"])
    assert handoff.pitchman == "Charlie"


def test_create_handoff_pitchman_none_and_empty_list(session, monkeypatch) -> None:
    """create_handoff with pitchman=None or pitchman=[] stores None."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    h1 = data.create_handoff(p.id, "No pitchman", pitchman=None)
    assert h1.pitchman is None
    h2 = data.create_handoff(p.id, "Empty list", pitchman=[])
    assert h2.pitchman is None
    h3 = data.create_handoff(p.id, "Whitespace only list", pitchman=["  ", ""])
    assert h3.pitchman is None


def test_get_project_returns_none_for_missing_id(session, monkeypatch) -> None:
    """get_project returns None when project_id does not exist."""
    _patch_session_context(monkeypatch, session)
    assert data.get_project(99999) is None


def test_delete_handoff_returns_false_for_missing_id(session, monkeypatch) -> None:
    """delete_handoff returns False when handoff_id does not exist."""
    _patch_session_context(monkeypatch, session)
    assert data.delete_handoff(99999) is False


def test_update_handoff_returns_none_for_missing_id(session, monkeypatch) -> None:
    """update_handoff returns None when handoff_id does not exist."""
    _patch_session_context(monkeypatch, session)
    assert data.update_handoff(99999, need_back="No-op") is None


def test_query_handoffs_date_range(session, monkeypatch) -> None:
    """query_handoffs respects start/end deadline."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    start_dt = datetime(2026, 1, 5)
    end_dt = datetime(2026, 1, 15)
    h_in = Handoff(
        project_id=p.id,
        need_back="In range",
        deadline=datetime(2026, 1, 10),
    )
    h_out = Handoff(
        project_id=p.id,
        need_back="Out of range",
        deadline=datetime(2026, 1, 20),
    )
    session.add_all([h_in, h_out])
    session.commit()

    results = data.query_handoffs(start=start_dt.date(), end=end_dt.date(), include_concluded=True)
    assert len(results) == 1
    assert results[0].need_back == "In range"


def test_query_handoffs_pitchman_name_filter(session, monkeypatch) -> None:
    """query_handoffs filters by pitchman_name substring."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.add(Handoff(project_id=p.id, need_back="A", pitchman="Alice"))
    session.add(Handoff(project_id=p.id, need_back="B", pitchman="Bob"))
    session.commit()

    results = data.query_handoffs(pitchman_name="lic", include_concluded=True)
    assert len(results) == 1
    assert results[0].pitchman == "Alice"


def test_create_project(session, monkeypatch) -> None:
    """create_project stores and returns a new project."""
    _patch_session_context(monkeypatch, session)
    project = data.create_project("New Project")
    assert project.id is not None
    assert project.name == "New Project"
    assert session.get(Project, project.id) is not None


def test_activity_log_and_get_recent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """log_activity records entries; get_recent_activity returns them."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "activity_test.db"))
    import handoff.db as db_mod

    db_mod.dispose_db()
    importlib.reload(db_mod)
    db_mod.init_db()

    data.create_project("Test Project")
    activity = data.get_recent_activity(limit=5)
    assert len(activity) >= 1
    entry = activity[0]
    assert entry["entity_type"] == "project"
    assert entry["action"] == "created"
    assert entry.get("details", {}).get("name") == "Test Project"

    db_mod.dispose_db()


def test_list_projects_excludes_archived_by_default(session, monkeypatch) -> None:
    """list_projects omits archived projects unless include_archived=True."""
    _patch_session_context(monkeypatch, session)
    p1 = Project(name="Active")
    p2 = Project(name="Old", is_archived=True)
    session.add_all([p1, p2])
    session.commit()

    active = data.list_projects()
    assert len(active) == 1
    assert active[0].name == "Active"

    all_projects = data.list_projects(include_archived=True)
    assert len(all_projects) == 2


def test_list_projects_survives_models_reload(session, monkeypatch) -> None:
    """Reloading handoff.models does not poison SQLModel's registry for list_projects."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Reload safe")
    session.add(project)
    session.commit()

    import handoff.models as models

    before_project = models.Project
    before_handoff = models.Handoff
    importlib.reload(models)

    assert models.Project is before_project
    assert models.Handoff is before_handoff
    projects = data.list_projects(include_archived=True)
    assert [p.name for p in projects] == ["Reload safe"]


def test_rename_project(session, monkeypatch) -> None:
    """rename_project updates the project name."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="Before")
    session.add(p)
    session.commit()
    session.refresh(p)

    renamed = data.rename_project(p.id, "After")
    assert renamed is not None
    assert renamed.name == "After"


def test_rename_project_missing_id(session, monkeypatch) -> None:
    """rename_project returns None for a non-existent id."""
    _patch_session_context(monkeypatch, session)
    assert data.rename_project(99999, "No-op") is None


def test_delete_handoff_success(session, monkeypatch) -> None:
    """delete_handoff removes the handoff and returns True."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(project_id=p.id, need_back="To delete")
    session.add(h)
    session.commit()
    session.refresh(h)

    assert data.delete_handoff(h.id) is True
    assert session.get(Handoff, h.id) is None


def test_delete_project_missing_id(session, monkeypatch) -> None:
    """delete_project returns False for a non-existent id."""
    _patch_session_context(monkeypatch, session)
    assert data.delete_project(99999) is False


def test_archive_project_missing_id(session, monkeypatch) -> None:
    """archive_project/unarchive_project return False for missing ids."""
    _patch_session_context(monkeypatch, session)
    assert data.archive_project(99999) is False
    assert data.unarchive_project(99999) is False


def test_update_handoff_changes_project_and_need_back(session, monkeypatch) -> None:
    """update_handoff can change project_id and need_back."""
    _patch_session_context(monkeypatch, session)
    p1 = Project(name="P1")
    p2 = Project(name="P2")
    session.add_all([p1, p2])
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    h = Handoff(project_id=p1.id, need_back="Original")
    session.add(h)
    session.commit()
    session.refresh(h)

    updated = data.update_handoff(h.id, project_id=p2.id, need_back="Renamed")
    assert updated is not None
    assert updated.project_id == p2.id
    assert updated.need_back == "Renamed"


def test_get_projects_with_handoff_summary(session, monkeypatch) -> None:
    """get_projects_with_handoff_summary returns counts per open/concluded."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="Summarise")
    session.add(p)
    session.commit()
    session.refresh(p)

    h1 = Handoff(project_id=p.id, need_back="A")
    h2 = Handoff(project_id=p.id, need_back="B")
    h3 = Handoff(project_id=p.id, need_back="C")
    session.add_all([h1, h2, h3])
    session.commit()
    session.refresh(h3)

    # Conclude h3
    ci = CheckIn(
        handoff_id=h3.id,
        check_in_date=date(2026, 1, 1),
        check_in_type=CheckInType.CONCLUDED,
    )
    session.add(ci)
    session.commit()

    summaries = data.get_projects_with_handoff_summary()
    assert len(summaries) == 1
    s = summaries[0]
    assert s["total"] == 3
    assert s["open"] == 2
    assert s["concluded"] == 1


def test_snooze_handoff(session, monkeypatch) -> None:
    """snooze_handoff updates next_check only, leaves deadline unchanged."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(
        project_id=p.id,
        need_back="Follow up",
        next_check=date(2026, 1, 1),
        deadline=date(2026, 6, 1),
    )
    session.add(h)
    session.commit()
    session.refresh(h)

    updated = data.snooze_handoff(h.id, to_date=date(2026, 1, 15))
    assert updated is not None
    assert updated.next_check == date(2026, 1, 15)
    assert updated.deadline == date(2026, 6, 1)


def test_conclude_handoff(session, monkeypatch) -> None:
    """conclude_handoff adds a concluded check-in."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(project_id=p.id, need_back="Done item")
    session.add(h)
    session.commit()
    session.refresh(h)

    ci = data.conclude_handoff(h.id, note="All done")
    assert ci is not None
    assert ci.check_in_type == CheckInType.CONCLUDED
    assert ci.handoff_id == h.id

    session.refresh(h)
    assert not data.handoff_is_open(h)
    assert data.get_handoff_close_date(h) is not None


def test_query_now_items(session, monkeypatch) -> None:
    """query_now_items returns open handoffs with next_check due or deadline at risk."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h1 = Handoff(
        project_id=p.id,
        need_back="Check due",
        next_check=date(2000, 1, 1),
        deadline=None,
    )
    h2 = Handoff(
        project_id=p.id,
        need_back="Deadline at risk",
        next_check=date(2030, 1, 1),
        deadline=date(2000, 1, 1),
    )
    h3 = Handoff(
        project_id=p.id,
        need_back="Concluded",
        next_check=date(2000, 1, 1),
    )
    session.add_all([h1, h2, h3])
    session.commit()
    session.refresh(h3)

    # Conclude h3
    ci = CheckIn(
        handoff_id=h3.id,
        check_in_date=date(2026, 1, 1),
        check_in_type=CheckInType.CONCLUDED,
    )
    session.add(ci)
    session.commit()

    results = data.query_now_items()
    assert len(results) == 2
    names = [r[0].need_back for r in results]
    assert "Check due" in names
    assert "Deadline at risk" in names
    assert "Concluded" not in names

    at_risk_names = [r[0].need_back for r in results if r[1]]
    assert "Deadline at risk" in at_risk_names
    assert "Check due" not in at_risk_names


def test_query_action_handoffs(session, monkeypatch) -> None:
    """query_action_handoffs returns due open handoffs, excluding Risk."""
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

    h_due = Handoff(project_id=p.id, need_back="Due", next_check=date(2026, 3, 9))
    h_due_risk = Handoff(
        project_id=p.id,
        need_back="Due but risk",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 10),
    )
    h_future = Handoff(project_id=p.id, need_back="Future", next_check=date(2026, 3, 10))
    h_concluded = Handoff(project_id=p.id, need_back="Done", next_check=date(2026, 3, 8))
    session.add_all([h_due, h_due_risk, h_future, h_concluded])
    session.commit()
    session.refresh(h_concluded)
    session.refresh(h_due_risk)

    session.add_all(
        [
            CheckIn(
                handoff_id=h_concluded.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.CONCLUDED,
            ),
            CheckIn(
                handoff_id=h_due_risk.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.DELAYED,
            ),
        ]
    )
    session.commit()

    results = data.query_action_handoffs(deadline_near_days=1)
    names = [h.need_back for h in results]
    assert "Due" in names
    assert "Due but risk" not in names
    assert "Future" not in names
    assert "Done" not in names


def test_query_action_handoffs_search_includes_check_in_notes(session, monkeypatch) -> None:
    """query_action_handoffs search text matches check-in notes."""
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

    h_match = Handoff(project_id=p.id, need_back="Follow up A", next_check=date(2026, 3, 9))
    h_other = Handoff(project_id=p.id, need_back="Follow up B", next_check=date(2026, 3, 9))
    session.add_all([h_match, h_other])
    session.commit()
    session.refresh(h_match)
    session.refresh(h_other)

    session.add_all(
        [
            CheckIn(
                handoff_id=h_match.id,
                check_in_date=date(2026, 3, 8),
                check_in_type=CheckInType.ON_TRACK,
                note="Customer waiting on assumption doc X",
            ),
            CheckIn(
                handoff_id=h_other.id,
                check_in_date=date(2026, 3, 8),
                check_in_type=CheckInType.ON_TRACK,
                note="No blockers",
            ),
        ]
    )
    session.commit()

    results = data.query_action_handoffs(search_text="assumption doc X")
    assert [h.id for h in results] == [h_match.id]


def test_query_risk_handoffs(session, monkeypatch) -> None:
    """query_risk_handoffs requires near deadline and latest check-in delayed."""
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

    h_risk = Handoff(project_id=p.id, need_back="Risk", deadline=date(2026, 3, 10))
    h_near_no_delay = Handoff(
        project_id=p.id,
        need_back="Near but on-track",
        deadline=date(2026, 3, 10),
    )
    h_old_delayed_now_on_track = Handoff(
        project_id=p.id,
        need_back="Old delayed but now on-track",
        deadline=date(2026, 3, 10),
    )
    h_delayed_far = Handoff(
        project_id=p.id,
        need_back="Delayed but far",
        deadline=date(2026, 3, 20),
    )
    h_due_after_tomorrow = Handoff(
        project_id=p.id,
        need_back="Delayed but not tomorrow",
        deadline=date(2026, 3, 11),
    )
    session.add_all(
        [h_risk, h_near_no_delay, h_old_delayed_now_on_track, h_delayed_far, h_due_after_tomorrow]
    )
    session.commit()
    session.refresh(h_risk)
    session.refresh(h_old_delayed_now_on_track)
    session.refresh(h_delayed_far)
    session.refresh(h_due_after_tomorrow)

    session.add_all(
        [
            CheckIn(
                handoff_id=h_risk.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.DELAYED,
            ),
            CheckIn(
                handoff_id=h_delayed_far.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.DELAYED,
            ),
            CheckIn(
                handoff_id=h_due_after_tomorrow.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.DELAYED,
            ),
            CheckIn(
                handoff_id=h_old_delayed_now_on_track.id,
                check_in_date=date(2026, 3, 8),
                check_in_type=CheckInType.DELAYED,
            ),
            CheckIn(
                handoff_id=h_old_delayed_now_on_track.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.ON_TRACK,
            ),
        ]
    )
    session.commit()

    results = data.query_risk_handoffs(deadline_near_days=1)
    names = [h.need_back for h in results]
    assert "Risk" in names
    assert "Near but on-track" not in names
    assert "Old delayed but now on-track" not in names
    assert "Delayed but far" not in names
    assert "Delayed but not tomorrow" not in names


def test_query_upcoming_handoffs(session, monkeypatch) -> None:
    """query_upcoming_handoffs returns open handoffs not in Risk/Action."""
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

    tomorrow = date(2026, 3, 10)

    h1 = Handoff(
        project_id=p.id,
        need_back="Upcoming",
        next_check=tomorrow,
        deadline=None,
    )
    h2 = Handoff(
        project_id=p.id,
        need_back="Also upcoming",
        next_check=date(2026, 3, 15),
        deadline=date(2026, 3, 20),
    )
    h3 = Handoff(
        project_id=p.id,
        need_back="Near deadline but not delayed",
        next_check=tomorrow,
        deadline=tomorrow,
    )
    h4 = Handoff(
        project_id=p.id,
        need_back="Risk item",
        next_check=tomorrow,
        deadline=tomorrow,
    )
    h5 = Handoff(
        project_id=p.id,
        need_back="Action item",
        next_check=date(2026, 3, 8),
        deadline=date(2026, 3, 20),
    )
    h6 = Handoff(
        project_id=p.id,
        need_back="No next check still upcoming",
        next_check=None,
        deadline=None,
    )
    session.add_all([h1, h2, h3, h4, h5, h6])
    session.commit()
    session.refresh(h4)

    delayed = CheckIn(
        handoff_id=h4.id,
        check_in_date=date(2026, 3, 9),
        check_in_type=CheckInType.DELAYED,
        note="Blocked",
    )
    session.add(delayed)
    session.commit()

    results = data.query_upcoming_handoffs(deadline_near_days=2)
    names = [r.need_back for r in results]
    assert "Upcoming" in names
    assert "Also upcoming" in names
    assert "Near deadline but not delayed" in names
    assert "No next check still upcoming" in names
    assert "Risk item" not in names
    assert "Action item" not in names


# ---------------------------------------------------------------------------
# import_payload tests
# ---------------------------------------------------------------------------


def test_import_payload_replaces_existing_data(session, monkeypatch) -> None:
    """import_payload wipes existing rows and inserts from the payload."""
    _patch_session_context(monkeypatch, session)

    old_project = Project(name="Old")
    session.add(old_project)
    session.commit()
    session.refresh(old_project)
    session.add(Handoff(project_id=old_project.id, need_back="old handoff"))
    session.commit()

    payload = {
        "projects": [
            {
                "id": 100,
                "name": "Imported",
                "created_at": "2026-03-01T00:00:00",
                "is_archived": False,
            },
        ],
        "handoffs": [
            {
                "id": 200,
                "project_id": 100,
                "need_back": "Imported handoff",
                "deadline": "2026-04-01",
                "pitchman": "Alice",
                "notes": "some notes",
                "created_at": "2026-03-01T00:00:00",
            },
        ],
        "check_ins": [],
    }
    data.import_payload(payload)

    projects = list(session.exec(select(Project)).all())
    handoffs = list(session.exec(select(Handoff)).all())
    assert len(projects) == 1
    assert projects[0].name == "Imported"
    assert len(handoffs) == 1
    assert handoffs[0].need_back == "Imported handoff"
    assert handoffs[0].pitchman == "Alice"


def test_import_payload_empty(session, monkeypatch) -> None:
    """import_payload with empty lists clears all data."""
    _patch_session_context(monkeypatch, session)

    p = Project(name="Will be gone")
    session.add(p)
    session.commit()
    session.refresh(p)
    session.add(Handoff(project_id=p.id, need_back="Also gone"))
    session.commit()

    data.import_payload({"projects": [], "handoffs": [], "check_ins": []})

    assert list(session.exec(select(Project)).all()) == []
    assert list(session.exec(select(Handoff)).all()) == []


def test_import_payload_missing_key_raises(session, monkeypatch) -> None:
    """import_payload raises KeyError when required keys are missing."""
    _patch_session_context(monkeypatch, session)

    with pytest.raises(KeyError):
        data.import_payload({"projects": []})


def test_import_payload_legacy_format(session, monkeypatch) -> None:
    """import_payload accepts legacy 'todos' format and converts to handoffs."""
    _patch_session_context(monkeypatch, session)

    payload = {
        "projects": [
            {
                "id": 1,
                "name": "Legacy",
                "created_at": "2026-01-01T00:00:00",
            },
        ],
        "todos": [
            {
                "id": 10,
                "project_id": 1,
                "name": "Old task",
                "status": "done",
                "helper": "Alice",
                "notes": "Done!",
                "created_at": "2026-01-01T00:00:00",
                "completed_at": "2026-01-15T00:00:00",
            },
            {
                "id": 11,
                "project_id": 1,
                "name": "Open task",
                "status": "handoff",
                "helper": "Bob",
                "created_at": "2026-01-01T00:00:00",
            },
        ],
    }
    data.import_payload(payload)

    handoffs = list(session.exec(select(Handoff)).all())
    check_ins = list(session.exec(select(CheckIn)).all())
    assert len(handoffs) == 2
    assert len(check_ins) == 1
    assert check_ins[0].check_in_type == CheckInType.CONCLUDED


def test_create_check_in(session, monkeypatch) -> None:
    """create_check_in inserts a record and can update handoff.next_check."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(project_id=p.id, need_back="Task")
    session.add(h)
    session.commit()
    session.refresh(h)

    ci = data.create_check_in(
        handoff_id=h.id,
        check_in_type=CheckInType.ON_TRACK,
        check_in_date=date(2026, 3, 1),
        note="All good",
        next_check_date=date(2026, 3, 8),
    )
    assert ci.id is not None
    assert ci.check_in_type == CheckInType.ON_TRACK
    assert ci.handoff_id == h.id
    raw_check_in_type = session.connection().exec_driver_sql(
        "SELECT check_in_type FROM check_in WHERE id = ?",
        (ci.id,),
    ).scalar_one()
    assert raw_check_in_type.lower() == "on_track"
    refreshed = session.get(Handoff, h.id)
    assert refreshed is not None
    assert refreshed.next_check == date(2026, 3, 8)


def test_create_check_in_concluded_does_not_update_next_check(session, monkeypatch) -> None:
    """Concluded check-ins must not change handoff.next_check."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(project_id=p.id, need_back="Task", next_check=date(2026, 3, 8))
    session.add(h)
    session.commit()
    session.refresh(h)

    data.create_check_in(
        handoff_id=h.id,
        check_in_type=CheckInType.CONCLUDED,
        check_in_date=date(2026, 3, 9),
        next_check_date=date(2026, 3, 15),
    )
    refreshed = session.get(Handoff, h.id)
    assert refreshed is not None
    assert refreshed.next_check == date(2026, 3, 8)


def test_create_check_in_missing_handoff_raises(session, monkeypatch) -> None:
    """create_check_in raises ValueError when handoff id does not exist."""
    _patch_session_context(monkeypatch, session)
    with pytest.raises(ValueError, match="not found for check-in"):
        data.create_check_in(
            handoff_id=99999,
            check_in_type=CheckInType.ON_TRACK,
            check_in_date=date(2026, 3, 9),
        )


def test_query_concluded_handoffs_search_includes_check_in_notes(session, monkeypatch) -> None:
    """query_concluded_handoffs search text matches concluded check-in notes."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h_match = Handoff(project_id=p.id, need_back="Closed A")
    h_other = Handoff(project_id=p.id, need_back="Closed B")
    session.add_all([h_match, h_other])
    session.commit()
    session.refresh(h_match)
    session.refresh(h_other)

    session.add_all(
        [
            CheckIn(
                handoff_id=h_match.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.CONCLUDED,
                note="Wrapped after assumption doc X arrived",
            ),
            CheckIn(
                handoff_id=h_other.id,
                check_in_date=date(2026, 3, 9),
                check_in_type=CheckInType.CONCLUDED,
                note="Routine close-out",
            ),
        ]
    )
    session.commit()

    results = data.query_concluded_handoffs(search_text="assumption doc X")
    assert [h.id for h in results] == [h_match.id]


def test_handoff_is_open_and_close_date(session, monkeypatch) -> None:
    """handoff_is_open and get_handoff_close_date work correctly."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    h = Handoff(project_id=p.id, need_back="Task")
    session.add(h)
    session.commit()
    session.refresh(h)
    # Force load relationship
    _ = h.check_ins

    assert data.handoff_is_open(h) is True
    assert data.get_handoff_close_date(h) is None

    ci = CheckIn(
        handoff_id=h.id,
        check_in_date=date(2026, 3, 5),
        check_in_type=CheckInType.CONCLUDED,
    )
    session.add(ci)
    session.commit()
    session.refresh(h)

    assert data.handoff_is_open(h) is False
    assert data.get_handoff_close_date(h) == date(2026, 3, 5)
