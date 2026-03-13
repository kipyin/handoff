"""Database engine and session for SQLite + SQLModel."""

import os
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from loguru import logger
from platformdirs import user_data_dir
from sqlalchemy.engine import Engine
from sqlmodel import Session, SQLModel, create_engine


def _get_default_db_path() -> Path:
    """Return the default path for the SQLite DB in the user data directory.

    This keeps the database outside the application bundle so updates to the
    executable or zip do not overwrite user data.

    Returns:
        Path to the default todo.db file.

    """
    # Example on Windows: C:\Users\<user>\AppData\Roaming\handoff\todo.db
    data_dir = Path(user_data_dir("handoff", "handoff"))
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir / "todo.db"


def _resolve_db_path() -> Path:
    """Resolve the database path, allowing an override via environment variable.

    Returns:
        Path to the SQLite database (from HANDOFF_DB_PATH or default).

    """
    override = os.environ.get("HANDOFF_DB_PATH")
    if override:
        path = Path(override).expanduser().resolve()
        path.parent.mkdir(parents=True, exist_ok=True)
        return path
    return _get_default_db_path()


class DatabaseInitializationError(RuntimeError):
    """Raised when the database engine or schema cannot be initialized."""


_DB_PATH: Path | None = None
_DATABASE_URL: str | None = None
_ENGINE: Engine | None = None


def _ensure_db_config() -> tuple[Path, str]:
    """Resolve and cache the current database path and URL."""
    global _DB_PATH, _DATABASE_URL
    if _DB_PATH is None or _DATABASE_URL is None:
        _DB_PATH = _resolve_db_path()
        _DATABASE_URL = f"sqlite:///{_DB_PATH}"
    return _DB_PATH, _DATABASE_URL


def get_db_path() -> Path:
    """Return the resolved path to the SQLite database file."""
    db_path, _ = _ensure_db_config()
    return db_path


def get_database_url() -> str:
    """Return the current SQLite connection URL."""
    _, database_url = _ensure_db_config()
    return database_url


def get_engine() -> Engine:
    """Return the lazily-created application engine."""
    global _ENGINE
    if _ENGINE is not None:
        return _ENGINE

    database_url = get_database_url()
    try:
        _ENGINE = create_engine(database_url, echo=False)
    except Exception as exc:
        logger.exception("Failed to create database engine for {}", database_url)
        msg = (
            "Could not initialise the database engine. "
            "Check that the configured path is writable and valid."
        )
        raise DatabaseInitializationError(msg) from exc
    return _ENGINE


def init_db() -> None:
    """Create all tables if they do not exist.

    Runs pending migrations in order. Safe to call on every app start.

    Raises:
        DatabaseInitializationError: If the database engine or schema cannot be
            initialized.

    """
    try:
        engine = get_engine()
        # Ensure models are imported so SQLModel's metadata is populated with
        # the Project, Handoff, and CheckIn tables before create_all() runs.
        from handoff import models as _models  # noqa: F401

        SQLModel.metadata.create_all(engine)

        from handoff.migrations import run_pending_migrations

        run_pending_migrations(engine)
    except Exception as exc:
        logger.exception("Database initialization failed: {}", exc)
        msg = "Database initialisation failed. See the log file for details."
        raise DatabaseInitializationError(msg) from exc

    logger.info("Database initialized at {}", get_db_path())


@contextmanager
def session_context() -> Iterator[Session]:
    """Context manager yielding a database session.

    Preferred entrypoint for DB access; used by functions in handoff.data to ensure
    sessions are opened and closed consistently.

    Yields:
        A SQLModel Session bound to the application engine.

    """
    with Session(get_engine()) as session:
        yield session


def dispose_db() -> None:
    """Dispose of cached engine and clear resolved DB config."""
    global _ENGINE, _DB_PATH, _DATABASE_URL
    if _ENGINE is not None:
        _ENGINE.dispose()
    _ENGINE = None
    _DB_PATH = None
    _DATABASE_URL = None
