"""Pytest fixtures: in-memory SQLite DB for tests."""

import pytest
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def session():
    """Yield a session backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:", connect_args={"check_same_thread": False})
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
    engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    """Dispose of the global app engine after all tests finish."""
    from handoff.db import dispose_db

    dispose_db()
