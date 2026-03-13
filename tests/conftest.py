"""Pytest fixtures: in-memory SQLite DB and sample data for tests."""

from __future__ import annotations

from datetime import UTC, date, datetime

import pytest
from sqlmodel import Session, SQLModel, create_engine

from handoff.core.models import CheckIn, CheckInType, Handoff, Project

# Patch Streamlit ButtonGroup.indices for AppTest compatibility with segmented_control.
# See https://github.com/streamlit/streamlit/issues/11338
try:
    from streamlit.testing.v1 import element_tree

    _orig_indices = element_tree.ButtonGroup.indices.fget

    @property
    def _safe_indices(self):
        try:
            return _orig_indices(self)
        except (ValueError, TypeError):
            return [0] if self.options else []

    element_tree.ButtonGroup.indices = _safe_indices
except (ImportError, AttributeError):
    pass


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
    """Fixture providing sample projects and handoffs for page tests.

    Yields (projects, handoffs) — model instances that tests can use when mocking
    get_projects_with_handoff_summary, query_handoffs, etc. Reduces boilerplate.
    """
    created = datetime(2025, 1, 1, tzinfo=UTC)
    p1 = Project(id=1, name="Work", is_archived=False, created_at=created)
    p2 = Project(id=2, name="Home", is_archived=False, created_at=created)
    projects = [p1, p2]
    h1 = Handoff(
        id=1,
        project_id=1,
        need_back="Task 1",
        pitchman="Alice",
        deadline=date.today(),
        notes="",
        created_at=created,
    )
    h1.check_ins = []
    h2 = Handoff(
        id=2,
        project_id=2,
        need_back="Task 2",
        pitchman="Bob",
        deadline=None,
        notes="",
        created_at=created,
    )
    h2.check_ins = [
        CheckIn(
            id=1,
            handoff_id=2,
            check_in_date=created.date(),
            check_in_type=CheckInType.CONCLUDED,
            created_at=created,
        )
    ]
    handoffs = [h1, h2]
    yield projects, handoffs


def pytest_sessionfinish(session, exitstatus):
    """Dispose of the global app engine after all tests finish."""
    from handoff.db import dispose_db

    dispose_db()
