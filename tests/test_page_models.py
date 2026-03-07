"""Tests for page_models typed contracts."""

from __future__ import annotations

from datetime import date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from handoff.models import Project, Todo, TodoStatus
from handoff.page_models import TodoRow, _require_todo_id


@pytest.fixture
def db_session():
    """Yield a session with real Project+Todo tables."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def test_require_todo_id_returns_value() -> None:
    assert _require_todo_id(42) == 42


def test_require_todo_id_raises_on_none() -> None:
    with pytest.raises(ValueError, match="persisted todos with ids"):
        _require_todo_id(None)


def test_todo_row_from_todo_with_project(db_session: Session) -> None:
    project = Project(name="Work")
    db_session.add(project)
    db_session.flush()
    todo = Todo(
        project_id=project.id,
        name="Write tests",
        status=TodoStatus.HANDOFF,
        helper="  Alice  ",
        deadline=date(2026, 4, 1),
        notes="Important",
        created_at=datetime(2026, 3, 1),
    )
    db_session.add(todo)
    db_session.flush()
    db_session.refresh(todo)

    row = TodoRow.from_todo(todo)
    assert row.todo_id == todo.id
    assert row.project_name == "Work"
    assert row.helper == "Alice"
    assert row.deadline == date(2026, 4, 1)
    assert row.notes == "Important"


def test_todo_row_from_todo_null_fields(db_session: Session) -> None:
    project = Project(name="Home")
    db_session.add(project)
    db_session.flush()
    todo = Todo(
        project_id=project.id,
        name="Minimal",
        status=TodoStatus.DONE,
        helper=None,
        deadline=None,
        notes=None,
        created_at=datetime(2026, 1, 1),
    )
    db_session.add(todo)
    db_session.flush()
    db_session.refresh(todo)

    row = TodoRow.from_todo(todo)
    assert row.helper == ""
    assert row.notes == ""
    assert row.deadline is None


def test_todo_row_from_todo_no_project(db_session: Session) -> None:
    project = Project(name="Temp")
    db_session.add(project)
    db_session.flush()
    todo = Todo(
        project_id=project.id,
        name="Orphan",
        status=TodoStatus.CANCELED,
        created_at=datetime(2026, 1, 1),
    )
    db_session.add(todo)
    db_session.flush()
    db_session.refresh(todo)
    # Force project to None to simulate detached state
    todo.project = None
    row = TodoRow.from_todo(todo)
    assert row.project_name == ""


def test_todo_row_from_todo_raises_on_none_id(db_session: Session) -> None:
    project = Project(name="X")
    db_session.add(project)
    db_session.flush()
    todo = Todo(
        id=None,
        project_id=project.id,
        name="No ID",
        status=TodoStatus.HANDOFF,
        created_at=datetime(2026, 1, 1),
    )
    todo.project = project
    with pytest.raises(ValueError, match="persisted todos with ids"):
        TodoRow.from_todo(todo)
