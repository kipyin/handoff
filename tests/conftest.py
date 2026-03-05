"""Pytest fixtures: in-memory SQLite DB for tests."""

import pytest
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def session():
    """Yield a session backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    try:
        with Session(engine) as session:
            yield session
    finally:
        engine.dispose()


def pytest_sessionfinish(session, exitstatus):
    """Dispose of the global app engine after all tests finish."""
    from handoff.db import dispose_db
    dispose_db()
