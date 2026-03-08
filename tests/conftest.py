"""Pytest fixtures: in-memory SQLite DB and sample data for tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from handoff.models import Project, Todo, TodoStatus


@pytest.fixture
def session():
    """Yield a session backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


@pytest.fixture
def app_with_sample_data():
    """Fixture providing sample projects and todos for page tests.

    Yields (projects, todos) — model instances that tests can use when mocking
    get_projects_with_todo_summary, query_todos, etc. Reduces boilerplate.
    """
    created = datetime(2025, 1, 1, tzinfo=UTC)
    p1 = Project(id=1, name="Work", is_archived=False, created_at=created)
    p2 = Project(id=2, name="Home", is_archived=False, created_at=created)
    projects = [p1, p2]
    t1 = Todo(
        id=1,
        project_id=1,
        name="Task 1",
        status=TodoStatus.HANDOFF,
        helper="Alice",
        deadline=date.today(),
        notes="",
        created_at=created,
        completed_at=None,
        is_archived=False,
    )
    t2 = Todo(
        id=2,
        project_id=2,
        name="Task 2",
        status=TodoStatus.DONE,
        helper="Bob",
        deadline=None,
        notes="",
        created_at=created,
        completed_at=created,
        is_archived=False,
    )
    todos = [t1, t2]
    yield projects, todos


def pytest_sessionfinish(session, exitstatus):
    """Dispose of the global app engine after all tests finish."""
    from handoff.db import dispose_db

    dispose_db()
