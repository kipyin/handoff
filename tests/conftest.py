"""Pytest fixtures: in-memory SQLite DB for tests."""

import pytest
from sqlmodel import Session, SQLModel, create_engine


@pytest.fixture
def session():
    """Yield a session backed by an in-memory SQLite database."""
    engine = create_engine("sqlite:///:memory:")
    SQLModel.metadata.create_all(engine)
    with Session(engine) as session:
        yield session
