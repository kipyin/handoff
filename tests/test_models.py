"""Tests for Project and Todo models."""

from datetime import datetime

from sqlmodel import Session

from todo_app.models import Project, Todo, TodoStatus


def test_create_project(session: Session) -> None:
    """Creating a project persists it and sets id and created_at."""
    p = Project(name="Engagement A")
    session.add(p)
    session.commit()
    session.refresh(p)
    assert p.id is not None
    assert p.name == "Engagement A"
    assert isinstance(p.created_at, datetime)


def test_create_todo(session: Session) -> None:
    """Creating a todo with project_id and optional fields works."""
    p = Project(name="Proj")
    session.add(p)
    session.commit()
    session.refresh(p)
    assert p.id is not None
    t = Todo(project_id=p.id, name="Call client", status=TodoStatus.DELEGATED, helper="Alice")
    session.add(t)
    session.commit()
    session.refresh(t)
    assert t.id is not None
    assert t.project_id == p.id
    assert t.helper == "Alice"
    assert t.status == TodoStatus.DELEGATED
