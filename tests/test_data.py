"""Tests for data access helpers."""

import importlib
from contextlib import contextmanager
from datetime import UTC, date, datetime
from pathlib import Path

import pytest
from sqlmodel import select

import handoff.data as data
from handoff.models import Project, Todo, TodoStatus


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


def test_update_todo_allows_clearing_fields(session, monkeypatch) -> None:
    """Update supports clearing deadline/helper/notes via explicit None-like values."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Alpha")
    session.add(project)
    session.commit()
    session.refresh(project)

    todo = Todo(
        project_id=project.id,
        name="Draft summary",
        status=TodoStatus.DELEGATED,
        deadline=datetime(2026, 1, 1, 12, 0),
        helper="Alice",
        notes="first",
    )
    session.add(todo)
    session.commit()
    session.refresh(todo)

    updated = data.update_todo(todo.id, deadline=None, helper=" ", notes=None)
    assert updated is not None
    assert updated.deadline is None
    assert updated.helper is None
    assert updated.notes is None


def test_delete_project_deletes_project_and_children(session, monkeypatch) -> None:
    """Deleting a project also removes its child todos."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Delete Me")
    session.add(project)
    session.commit()
    session.refresh(project)

    todo = Todo(project_id=project.id, name="child")
    session.add(todo)
    session.commit()
    session.refresh(todo)

    deleted = data.delete_project(project.id)
    assert deleted is True
    assert session.get(Project, project.id) is None
    assert session.get(Todo, todo.id) is None


def test_archive_and_unarchive_project(session, monkeypatch) -> None:
    """Archiving a project marks it and its todos; unarchiving clears the flag."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Archive Me")
    session.add(project)
    session.commit()
    session.refresh(project)

    todo1 = Todo(project_id=project.id, name="t1")
    todo2 = Todo(project_id=project.id, name="t2")
    session.add(todo1)
    session.add(todo2)
    session.commit()

    archived = data.archive_project(project.id)
    assert archived is True
    session.refresh(project)
    assert project.is_archived is True
    todos = session.exec(select(Todo).where(Todo.project_id == project.id)).all()
    assert {t.is_archived for t in todos} == {True}

    unarchived = data.unarchive_project(project.id)
    assert unarchived is True
    session.refresh(project)
    assert project.is_archived is False


def test_get_export_payload_includes_projects_and_todos(session, monkeypatch) -> None:
    """Export payload returns serializable project and todo records."""
    _patch_session_context(monkeypatch, session)
    project = Project(name="Export")
    session.add(project)
    session.commit()
    session.refresh(project)

    todo = Todo(project_id=project.id, name="Export todo", status=TodoStatus.DONE)
    session.add(todo)
    session.commit()

    payload = data.get_export_payload()
    assert "projects" in payload
    assert "todos" in payload
    assert len(payload["projects"]) == 1
    assert len(payload["todos"]) == 1
    assert payload["todos"][0]["status"] == TodoStatus.DONE.value


def test_list_helpers_canonicalization(session, monkeypatch) -> None:
    """Verify that list_helpers handles case-insensitivity and trimming."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    # Add todos with variations of the same name
    session.add(Todo(project_id=p.id, name="t1", helper="  Alice  "))
    session.add(Todo(project_id=p.id, name="t2", helper="alice"))
    session.add(Todo(project_id=p.id, name="t3", helper="BOB"))
    session.add(Todo(project_id=p.id, name="t4", helper=None))
    session.commit()

    helpers = data.list_helpers()
    # Should be sorted, trimmed, and unique by case (keeping first encountered casing)
    assert helpers == ["Alice", "BOB"]


def test_query_todos_filters(session, monkeypatch) -> None:
    """Verify query_todos with multiple filter combinations."""
    _patch_session_context(monkeypatch, session)
    p1 = Project(name="P1")
    p2 = Project(name="P2")
    session.add_all([p1, p2])
    session.commit()

    t1 = Todo(project_id=p1.id, name="Apple", status=TodoStatus.DONE, helper="Alice")
    t2 = Todo(project_id=p2.id, name="Banana", status=TodoStatus.DELEGATED, helper="Bob")
    session.add_all([t1, t2])
    session.commit()

    # Filter by status
    results = data.query_todos(statuses=[TodoStatus.DONE])
    assert len(results) == 1
    assert results[0].name == "Apple"

    # Filter by search text (case-insensitive)
    results = data.query_todos(search_text="nan")
    assert len(results) == 1
    assert results[0].name == "Banana"

    # Filter by project
    results = data.query_todos(project_ids=[p1.id])
    assert len(results) == 1
    assert results[0].name == "Apple"


def test_create_todo_with_list_helper(session, monkeypatch) -> None:
    """Verify _helper_to_db logic when a list is passed (from UI multiselects)."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    # UI often passes lists from multiselects; we take the first non-empty
    todo = data.create_todo(p.id, "Task", helper=["", "  Charlie  ", "Dave"])
    assert todo.helper == "Charlie"


def test_create_todo_helper_none_and_empty_list(session, monkeypatch) -> None:
    """create_todo with helper=None or helper=[] stores None (covers _helper_to_db branches)."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    t1 = data.create_todo(p.id, "No helper", helper=None)
    assert t1.helper is None
    t2 = data.create_todo(p.id, "Empty list", helper=[])
    assert t2.helper is None
    t3 = data.create_todo(p.id, "Whitespace only list", helper=["  ", ""])
    assert t3.helper is None


def test_get_project_returns_none_for_missing_id(session, monkeypatch) -> None:
    """get_project returns None when project_id does not exist."""
    _patch_session_context(monkeypatch, session)
    assert data.get_project(99999) is None


def test_delete_todo_returns_false_for_missing_id(session, monkeypatch) -> None:
    """delete_todo returns False when todo_id does not exist."""
    _patch_session_context(monkeypatch, session)
    assert data.delete_todo(99999) is False


def test_update_todo_returns_none_for_missing_id(session, monkeypatch) -> None:
    """update_todo returns None when todo_id does not exist."""
    _patch_session_context(monkeypatch, session)
    assert data.update_todo(99999, name="No-op") is None


def test_query_todos_date_range_and_include_archived(session, monkeypatch) -> None:
    """query_todos respects start/end deadline and include_archived."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()

    start_dt = datetime(2026, 1, 5)
    end_dt = datetime(2026, 1, 15)
    t_in = Todo(
        project_id=p.id,
        name="In range",
        status=TodoStatus.DELEGATED,
        deadline=datetime(2026, 1, 10),
    )
    t_out = Todo(
        project_id=p.id,
        name="Out of range",
        status=TodoStatus.DELEGATED,
        deadline=datetime(2026, 1, 20),
    )
    session.add_all([t_in, t_out])
    session.commit()

    results = data.query_todos(start=start_dt.date(), end=end_dt.date())
    assert len(results) == 1
    assert results[0].name == "In range"

    # include_archived: add an archived todo and ensure it's included when True
    t_archived = Todo(
        project_id=p.id,
        name="Archived",
        status=TodoStatus.DELEGATED,
        is_archived=True,
    )
    session.add(t_archived)
    session.commit()
    without = data.query_todos(include_archived=False)
    with_archived = data.query_todos(include_archived=True)
    assert len(with_archived) == len(without) + 1


def test_query_todos_helper_name_filter(session, monkeypatch) -> None:
    """query_todos filters by helper_name substring."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.add(Todo(project_id=p.id, name="A", status=TodoStatus.DELEGATED, helper="Alice"))
    session.add(Todo(project_id=p.id, name="B", status=TodoStatus.DELEGATED, helper="Bob"))
    session.commit()

    results = data.query_todos(helper_name="lic")
    assert len(results) == 1
    assert results[0].helper == "Alice"


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
    before_todo = models.Todo
    importlib.reload(models)

    assert models.Project is before_project
    assert models.Todo is before_todo
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


def test_delete_todo_success(session, monkeypatch) -> None:
    """delete_todo removes the todo and returns True."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    t = Todo(project_id=p.id, name="To delete")
    session.add(t)
    session.commit()
    session.refresh(t)

    assert data.delete_todo(t.id) is True
    assert session.get(Todo, t.id) is None


def test_delete_project_missing_id(session, monkeypatch) -> None:
    """delete_project returns False for a non-existent id."""
    _patch_session_context(monkeypatch, session)
    assert data.delete_project(99999) is False


def test_archive_and_unarchive_todo(session, monkeypatch) -> None:
    """archive_todo and unarchive_todo toggle the is_archived flag."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    t = Todo(project_id=p.id, name="Toggle")
    session.add(t)
    session.commit()
    session.refresh(t)

    assert data.archive_todo(t.id) is True
    session.refresh(t)
    assert t.is_archived is True

    assert data.unarchive_todo(t.id) is True
    session.refresh(t)
    assert t.is_archived is False


def test_archive_todo_missing_id(session, monkeypatch) -> None:
    """archive_todo/unarchive_todo return False for missing ids."""
    _patch_session_context(monkeypatch, session)
    assert data.archive_todo(99999) is False
    assert data.unarchive_todo(99999) is False


def test_archive_project_missing_id(session, monkeypatch) -> None:
    """archive_project/unarchive_project return False for missing ids."""
    _patch_session_context(monkeypatch, session)
    assert data.archive_project(99999) is False
    assert data.unarchive_project(99999) is False


def test_update_todo_changes_project_name_status(session, monkeypatch) -> None:
    """update_todo can change project_id, name, and status."""
    _patch_session_context(monkeypatch, session)
    p1 = Project(name="P1")
    p2 = Project(name="P2")
    session.add_all([p1, p2])
    session.commit()
    session.refresh(p1)
    session.refresh(p2)

    t = Todo(project_id=p1.id, name="Original", status=TodoStatus.DELEGATED)
    session.add(t)
    session.commit()
    session.refresh(t)

    updated = data.update_todo(t.id, project_id=p2.id, name="Renamed", status=TodoStatus.DONE)
    assert updated is not None
    assert updated.project_id == p2.id
    assert updated.name == "Renamed"
    assert updated.status == TodoStatus.DONE
    assert updated.completed_at is not None


def test_get_projects_with_todo_summary(session, monkeypatch) -> None:
    """get_projects_with_todo_summary returns counts per status."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="Summarise")
    session.add(p)
    session.commit()
    session.refresh(p)

    session.add(Todo(project_id=p.id, name="A", status=TodoStatus.DELEGATED))
    session.add(Todo(project_id=p.id, name="B", status=TodoStatus.DELEGATED))
    session.add(Todo(project_id=p.id, name="C", status=TodoStatus.DONE))
    session.add(Todo(project_id=p.id, name="D", status=TodoStatus.CANCELED))
    session.commit()

    summaries = data.get_projects_with_todo_summary()
    assert len(summaries) == 1
    s = summaries[0]
    assert s["total"] == 4
    assert s["handoff"] == 2
    assert s["done"] == 1
    assert s["canceled"] == 1


def test_query_todos_completed_start_end(session, monkeypatch) -> None:
    """query_todos filters by completed_at with completed_start/completed_end."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    t1 = Todo(
        project_id=p.id,
        name="Done early",
        status=TodoStatus.DONE,
        completed_at=datetime(2026, 1, 5, tzinfo=UTC),
    )
    t2 = Todo(
        project_id=p.id,
        name="Done later",
        status=TodoStatus.DONE,
        completed_at=datetime(2026, 1, 15, tzinfo=UTC),
    )
    t3 = Todo(
        project_id=p.id,
        name="Not done",
        status=TodoStatus.DELEGATED,
    )
    session.add_all([t1, t2, t3])
    session.commit()

    results = data.query_todos(
        completed_start=date(2026, 1, 10),
        completed_end=date(2026, 1, 20),
    )
    assert len(results) == 1
    assert results[0].name == "Done later"


def test_query_todos_completed_end_date_includes_full_day(session, monkeypatch) -> None:
    """A bare date for completed_end is promoted to end-of-day, including late completions."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    t = Todo(
        project_id=p.id,
        name="Done at 11pm",
        status=TodoStatus.DONE,
        completed_at=datetime(2026, 1, 15, 23, 30, 0, tzinfo=UTC),
    )
    session.add(t)
    session.commit()

    results = data.query_todos(completed_end=date(2026, 1, 15))
    assert len(results) == 1
    assert results[0].name == "Done at 11pm"


def test_snooze_todo(session, monkeypatch) -> None:
    """snooze_todo updates next_check only, leaves deadline unchanged."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    t = Todo(
        project_id=p.id,
        name="Follow up",
        status=TodoStatus.HANDOFF,
        next_check=date(2026, 1, 1),
        deadline=date(2026, 6, 1),
    )
    session.add(t)
    session.commit()
    session.refresh(t)

    updated = data.snooze_todo(t.id, to_date=date(2026, 1, 15))
    assert updated is not None
    assert updated.next_check == date(2026, 1, 15)
    assert updated.deadline == date(2026, 6, 1)


def test_close_todo(session, monkeypatch) -> None:
    """close_todo marks todo as done."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    t = Todo(
        project_id=p.id,
        name="Done item",
        status=TodoStatus.HANDOFF,
    )
    session.add(t)
    session.commit()
    session.refresh(t)

    updated = data.close_todo(t.id)
    assert updated is not None
    assert updated.status == TodoStatus.DONE
    assert updated.completed_at is not None


def test_query_now_items(session, monkeypatch) -> None:
    """query_now_items returns open items with next_check due or deadline at risk."""
    _patch_session_context(monkeypatch, session)
    p = Project(name="P")
    session.add(p)
    session.commit()
    session.refresh(p)

    # Past dates so they always qualify regardless of real today
    t1 = Todo(
        project_id=p.id,
        name="Check due",
        status=TodoStatus.HANDOFF,
        next_check=date(2000, 1, 1),
        deadline=None,
    )
    t2 = Todo(
        project_id=p.id,
        name="Deadline at risk",
        status=TodoStatus.HANDOFF,
        next_check=date(2030, 1, 1),
        deadline=date(2000, 1, 1),
    )
    t3 = Todo(
        project_id=p.id,
        name="Done",
        status=TodoStatus.DONE,
        next_check=date(2000, 1, 1),
    )
    session.add_all([t1, t2, t3])
    session.commit()

    results = data.query_now_items()
    assert len(results) == 2
    names = [r[0].name for r in results]
    assert "Check due" in names
    assert "Deadline at risk" in names
    assert "Done" not in names

    at_risk_names = [r[0].name for r in results if r[1]]
    assert "Deadline at risk" in at_risk_names
    assert "Check due" not in at_risk_names


def test_query_upcoming_handoffs(session, monkeypatch) -> None:
    """query_upcoming_handoffs returns handoffs with next_check in future and deadline not at risk."""
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

    today = date(2026, 3, 9)
    tomorrow = date(2026, 3, 10)

    t1 = Todo(
        project_id=p.id,
        name="Upcoming",
        status=TodoStatus.HANDOFF,
        next_check=tomorrow,
        deadline=None,
    )
    t2 = Todo(
        project_id=p.id,
        name="Also upcoming",
        status=TodoStatus.HANDOFF,
        next_check=date(2026, 3, 15),
        deadline=date(2026, 3, 20),
    )
    t3 = Todo(
        project_id=p.id,
        name="Due soon",
        status=TodoStatus.HANDOFF,
        next_check=tomorrow,
        deadline=tomorrow,
    )
    session.add_all([t1, t2, t3])
    session.commit()

    results = data.query_upcoming_handoffs(deadline_near_days=2)
    names = [r.name for r in results]
    assert "Upcoming" in names
    assert "Also upcoming" in names
    assert "Due soon" not in names


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
    session.add(Todo(project_id=old_project.id, name="old todo"))
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
        "todos": [
            {
                "id": 200,
                "project_id": 100,
                "name": "Imported todo",
                "status": "handoff",
                "deadline": "2026-04-01",
                "helper": "Alice",
                "notes": "some notes",
                "created_at": "2026-03-01T00:00:00",
                "completed_at": None,
                "is_archived": False,
            },
        ],
    }
    data.import_payload(payload)

    projects = list(session.exec(select(Project)).all())
    todos = list(session.exec(select(Todo)).all())
    assert len(projects) == 1
    assert projects[0].name == "Imported"
    assert len(todos) == 1
    assert todos[0].name == "Imported todo"
    assert todos[0].helper == "Alice"


def test_import_payload_empty(session, monkeypatch) -> None:
    """import_payload with empty lists clears all data."""
    _patch_session_context(monkeypatch, session)

    p = Project(name="Will be gone")
    session.add(p)
    session.commit()
    session.refresh(p)
    session.add(Todo(project_id=p.id, name="Also gone"))
    session.commit()

    data.import_payload({"projects": [], "todos": []})

    assert list(session.exec(select(Project)).all()) == []
    assert list(session.exec(select(Todo)).all()) == []


def test_import_payload_missing_key_raises(session, monkeypatch) -> None:
    """import_payload raises KeyError when required keys are missing."""
    _patch_session_context(monkeypatch, session)
    import pytest

    with pytest.raises(KeyError):
        data.import_payload({"projects": []})

    with pytest.raises(KeyError):
        data.import_payload({"todos": []})
