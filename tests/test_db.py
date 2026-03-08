"""Tests for DB initialisation and lightweight migrations."""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from handoff.db import DatabaseInitializationError


def _reload_db_module(db_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reload handoff.db with HANDOFF_DB_PATH pointed at db_path."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))
    import handoff.db as db  # type: ignore[import-not-found]

    db.dispose_db()  # close any existing engine before reload
    return importlib.reload(db)


def _get_sqlite_path(database_url: str) -> str:
    """Extract the filesystem path from a sqlite:/// URL."""
    prefix = "sqlite:///"
    if database_url.startswith(prefix):
        return database_url[len(prefix) :]
    return database_url


def _fetch_columns(sqlite_path: str, table: str) -> set[str]:
    """Return the set of column names for a table."""
    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute(f"PRAGMA table_info('{table}')").fetchall()
    finally:
        conn.close()
    return {row[1] for row in rows}


def test_init_db_creates_tables_and_completed_at(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db creates tables and includes the completed_at column on a fresh DB."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    db.init_db()

    sqlite_path = _get_sqlite_path(db.get_database_url())
    todo_columns = _fetch_columns(sqlite_path, "todo")
    project_columns = _fetch_columns(sqlite_path, "project")
    # Sanity-check core columns plus the migration columns.
    assert {"id", "project_id", "name"}.issubset(todo_columns)
    assert "completed_at" in todo_columns
    assert "is_archived" in todo_columns
    assert "next_check" in todo_columns
    assert "is_archived" in project_columns


def test_init_db_adds_completed_at_to_existing_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db applies the completed_at migration for an older todo schema."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    sqlite_path = _get_sqlite_path(db.get_database_url())
    # Simulate an older schema that predates the completed_at/is_archived columns.
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(
            """
            CREATE TABLE todo (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL
            )
            """,
        )
        conn.execute(
            """
            CREATE TABLE project (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL
            )
            """,
        )
        conn.commit()
    finally:
        conn.close()

    # Running init_db again should leave the existing table in place but add
    # the completed_at column via the lightweight migration.
    db.init_db()

    todo_columns = _fetch_columns(sqlite_path, "todo")
    project_columns = _fetch_columns(sqlite_path, "project")
    assert "completed_at" in todo_columns
    assert "is_archived" in todo_columns
    assert "next_check" in todo_columns
    assert "is_archived" in project_columns


def test_init_db_adds_next_check_to_existing_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db applies the next_check migration for a todo schema that lacks it."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    sqlite_path = _get_sqlite_path(db.get_database_url())
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(
            """
            CREATE TABLE todo (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'handoff',
                deadline DATE NULL,
                helper TEXT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP NULL,
                is_archived INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        conn.execute(
            """
            CREATE TABLE project (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        conn.commit()
    finally:
        conn.close()

    todo_columns_before = _fetch_columns(sqlite_path, "todo")
    assert "next_check" not in todo_columns_before

    db.init_db()

    todo_columns_after = _fetch_columns(sqlite_path, "todo")
    assert "next_check" in todo_columns_after


def test_init_db_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running init_db twice on an already-migrated DB does not fail or corrupt."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    db.init_db()
    todo_columns_first = _fetch_columns(_get_sqlite_path(db.get_database_url()), "todo")

    db.init_db()
    todo_columns_second = _fetch_columns(_get_sqlite_path(db.get_database_url()), "todo")

    assert todo_columns_first == todo_columns_second
    assert "next_check" in todo_columns_second
    assert "completed_at" in todo_columns_second
    assert "is_archived" in todo_columns_second


def test_init_db_migrates_legacy_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db migrates legacy status values: delegated→handoff, DELEGATED→HANDOFF."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    sqlite_path = _get_sqlite_path(db.get_database_url())
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(
            """
            CREATE TABLE todo (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL,
                deadline DATE NULL,
                helper TEXT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP NULL,
                is_archived INTEGER NOT NULL DEFAULT 0,
                next_check DATE NULL
            )
            """,
        )
        conn.execute(
            """
            CREATE TABLE project (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        conn.execute("INSERT INTO project (id, name, created_at, is_archived) VALUES (1, 'P', '2026-01-01 00:00:00', 0)")
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, created_at, is_archived) "
            "VALUES (1, 1, 'Old', 'delegated', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, created_at, is_archived) "
            "VALUES (2, 1, 'New', 'DELEGATED', '2026-01-01 00:00:00', 0)"
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    conn = sqlite3.connect(sqlite_path)
    try:
        rows = conn.execute("SELECT id, status FROM todo ORDER BY id").fetchall()
    finally:
        conn.close()
    status_by_id = {r[0]: r[1] for r in rows}
    assert status_by_id[1] == "handoff"
    assert status_by_id[2] == "HANDOFF"


def test_init_db_preserves_data_through_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migrating from older schema (no next_check) preserves existing project and todo data."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    sqlite_path = _get_sqlite_path(db.get_database_url())
    conn = sqlite3.connect(sqlite_path)
    try:
        conn.execute(
            """
            CREATE TABLE todo (
                id INTEGER PRIMARY KEY,
                project_id INTEGER NOT NULL,
                name TEXT NOT NULL,
                status TEXT NOT NULL DEFAULT 'handoff',
                deadline DATE NULL,
                helper TEXT NULL,
                notes TEXT NULL,
                created_at TIMESTAMP NOT NULL,
                completed_at TIMESTAMP NULL,
                is_archived INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        conn.execute(
            """
            CREATE TABLE project (
                id INTEGER PRIMARY KEY,
                name TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL,
                is_archived INTEGER NOT NULL DEFAULT 0
            )
            """,
        )
        conn.execute(
            "INSERT INTO project (id, name, created_at, is_archived) VALUES (1, 'My Project', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, created_at, is_archived) "
            "VALUES (1, 1, 'Existing todo', 'handoff', '2026-01-01 00:00:00', 0)"
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    conn = sqlite3.connect(sqlite_path)
    try:
        projects = conn.execute("SELECT id, name FROM project").fetchall()
        todos = conn.execute(
            "SELECT id, project_id, name, next_check FROM todo"
        ).fetchall()
    finally:
        conn.close()

    assert len(projects) == 1
    assert projects[0][1] == "My Project"
    assert len(todos) == 1
    assert todos[0][2] == "Existing todo"
    assert todos[0][3] is None
    assert todos[0][1] == 1


def test_init_db_raises_when_engine_creation_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When engine creation fails lazily, DatabaseInitializationError is raised."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(tmp_path / "todo.db"))
    import handoff.db as db  # noqa: F401

    db.dispose_db()
    with patch("handoff.db.create_engine", side_effect=Exception("Engine failed")):
        with pytest.raises((DatabaseInitializationError, Exception)) as exc_info:
            db.get_engine()
        assert type(exc_info.value).__name__ == "DatabaseInitializationError"
        msg = exc_info.value.args[0].lower()
        assert "engine" in msg or "initialise" in msg


def test_init_db_raises_when_migration_fails(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When migrations raise inside connect(), DatabaseInitializationError is raised."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)
    try:
        mock_conn = MagicMock()
        mock_conn.exec_driver_sql.side_effect = Exception("Migration failed")
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = lambda *a: None
        with patch.object(db.get_engine(), "connect", return_value=mock_conn):
            with pytest.raises((DatabaseInitializationError, Exception)) as exc_info:
                db.init_db()
            assert type(exc_info.value).__name__ == "DatabaseInitializationError"
            assert "failed" in exc_info.value.args[0].lower()
    finally:
        db.dispose_db()
