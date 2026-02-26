"""Database engine and session for SQLite + SQLModel."""

import os
from contextlib import contextmanager
from pathlib import Path

from loguru import logger
from platformdirs import user_data_dir
from sqlmodel import Session, SQLModel, create_engine

from todo_app.models import Project, Todo


def _get_default_db_path() -> Path:
    """Return the default path for the SQLite DB in the user data directory.

    This keeps the database outside the application bundle so updates to the
    executable or zip do not overwrite user data.
    """
    # Example on Windows: C:\Users\<user>\AppData\Roaming\todo-app\todo.db
    data_dir = Path(user_data_dir("todo-app", "todo-app"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "todo.db"


def _resolve_db_path() -> Path:
    """Resolve the database path, allowing an override via environment variable."""
    override = os.environ.get("TODO_APP_DB_PATH")
    if override:
        path = Path(override).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return _get_default_db_path()


_DB_PATH = _resolve_db_path()
DATABASE_URL = f"sqlite:///{_DB_PATH}"

engine = create_engine(DATABASE_URL, echo=False)


def init_db() -> None:
    """Create all tables if they do not exist.

    Safe to call on every app start; only creates missing tables.
    """
    SQLModel.metadata.create_all(engine)

    # Lightweight migration: ensure newer columns exist on existing tables.
    with engine.connect() as conn:
        result = conn.exec_driver_sql("PRAGMA table_info('todo')")
        columns = {row[1] for row in result}  # row[1] = column name
        if "completed_at" not in columns:
            logger.info("Applying migration: adding completed_at column to todo table")
            conn.exec_driver_sql("ALTER TABLE todo ADD COLUMN completed_at TIMESTAMP NULL")

    logger.info("Database initialized at {}", _DB_PATH)


def get_session() -> Session:
    """Return a new database session (context manager preferred via session_context).

    This is primarily used by higher-level helpers in ``todo_app.data``.
    """
    return Session(engine)


@contextmanager
def session_context():
    """Context manager yielding a database session.

    Preferred entrypoint for DB access; used by functions in ``todo_app.data`` to ensure
    sessions are opened and closed consistently.
    """
    with Session(engine) as session:
        yield session
