"""Tests for data access helpers."""

from contextlib import contextmanager
from datetime import datetime

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
