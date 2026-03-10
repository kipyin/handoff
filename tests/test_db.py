"""Tests for DB initialisation and lightweight migrations."""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from handoff.db import DatabaseInitializationError
from handoff.models import CheckInType


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


def _table_exists(sqlite_path: str, table: str) -> bool:
    """Return True if the table exists."""
    conn = sqlite3.connect(sqlite_path)
    try:
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        return cursor.fetchone() is not None
    finally:
        conn.close()


def test_init_db_creates_tables(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db creates handoff, check_in, project, and activity_log tables on a fresh DB."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    db.init_db()

    sqlite_path = _get_sqlite_path(db.get_database_url())
    handoff_columns = _fetch_columns(sqlite_path, "handoff")
    check_in_columns = _fetch_columns(sqlite_path, "check_in")
    project_columns = _fetch_columns(sqlite_path, "project")
    assert {"id", "project_id", "need_back"}.issubset(handoff_columns)
    assert "pitchman" in handoff_columns
    assert "next_check" in handoff_columns
    assert {"id", "handoff_id", "check_in_date", "check_in_type"}.issubset(check_in_columns)
    assert "is_archived" in project_columns
    assert _table_exists(sqlite_path, "schema_version")
    assert _table_exists(sqlite_path, "activity_log")
    assert not _table_exists(sqlite_path, "todo")


def test_init_db_migrates_from_old_todo_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db migrates an older schema with todo table to handoff + check_in."""
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
        conn.execute(
            "INSERT INTO project (id, name, created_at, is_archived) "
            "VALUES (1, 'My Project', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, helper, created_at, is_archived) "
            "VALUES (1, 1, 'Open task', 'handoff', 'Alice', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, helper, created_at, "
            "completed_at, is_archived) "
            "VALUES (2, 1, 'Done task', 'done', 'Bob', '2026-01-01 00:00:00', "
            "'2026-01-15 00:00:00', 0)"
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    assert _table_exists(sqlite_path, "handoff")
    assert _table_exists(sqlite_path, "check_in")
    assert not _table_exists(sqlite_path, "todo")

    conn = sqlite3.connect(sqlite_path)
    try:
        handoffs = conn.execute(
            "SELECT id, need_back, pitchman FROM handoff ORDER BY id"
        ).fetchall()
        check_ins = conn.execute("SELECT handoff_id, check_in_type FROM check_in").fetchall()
    finally:
        conn.close()

    assert len(handoffs) == 2
    assert handoffs[0][1] == "Open task"
    assert handoffs[0][2] == "Alice"
    assert handoffs[1][1] == "Done task"
    assert handoffs[1][2] == "Bob"

    assert len(check_ins) == 1
    assert check_ins[0][0] == 2
    assert check_ins[0][1] == "concluded"


def test_migrated_data_readable_via_data_layer(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migrated data can be read through the ORM/data layer (enum hydration)."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    conn = sqlite3.connect(str(db_path))
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
        conn.execute(
            "INSERT INTO project (id, name, created_at, is_archived) "
            "VALUES (1, 'My Project', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, helper, created_at, is_archived) "
            "VALUES (1, 1, 'Open task', 'handoff', 'Alice', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, helper, created_at, "
            "completed_at, is_archived) "
            "VALUES (2, 1, 'Done task', 'done', 'Bob', '2026-01-01 00:00:00', "
            "'2026-01-15 00:00:00', 0)"
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    from handoff.data import query_concluded_handoffs

    concluded = query_concluded_handoffs()
    assert len(concluded) == 1
    assert concluded[0].need_back == "Done task"
    assert len(concluded[0].check_ins) >= 1
    for ci in concluded[0].check_ins:
        # Ensure the enum is hydrated correctly, not stored as a raw string.
        assert isinstance(ci.check_in_type, CheckInType)
    # query_concluded_handoffs() guarantees at least one concluded check-in,
    # not that all related check-ins are concluded.
    assert any(ci.check_in_type is CheckInType.CONCLUDED for ci in concluded[0].check_ins)


def test_init_db_is_idempotent(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Running init_db twice on an already-migrated DB does not fail or corrupt."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    db.init_db()
    handoff_columns_first = _fetch_columns(_get_sqlite_path(db.get_database_url()), "handoff")

    db.init_db()
    handoff_columns_second = _fetch_columns(_get_sqlite_path(db.get_database_url()), "handoff")

    assert handoff_columns_first == handoff_columns_second
    assert "next_check" in handoff_columns_second
    assert "need_back" in handoff_columns_second
    assert "pitchman" in handoff_columns_second


def test_init_db_migrates_legacy_status(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db migrates legacy status values and converts to handoff + check_in."""
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
        conn.execute(
            "INSERT INTO project (id, name, created_at, is_archived) "
            "VALUES (1, 'P', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, created_at, is_archived) "
            "VALUES (1, 1, 'Old', 'delegated', '2026-01-01 00:00:00', 0)"
        )
        conn.execute(
            "INSERT INTO todo (id, project_id, name, status, created_at, is_archived) "
            "VALUES (2, 1, 'New', 'handoff', '2026-01-01 00:00:00', 0)"
        )
        conn.commit()
    finally:
        conn.close()

    db.init_db()

    conn = sqlite3.connect(sqlite_path)
    try:
        handoffs = conn.execute("SELECT id, need_back FROM handoff ORDER BY id").fetchall()
    finally:
        conn.close()

    assert len(handoffs) == 2
    assert handoffs[0][1] == "Old"
    assert handoffs[1][1] == "New"


def test_init_db_preserves_data_through_migration(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Migrating from older schema preserves existing project and handoff data."""
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
            "INSERT INTO project (id, name, created_at, is_archived) "
            "VALUES (1, 'My Project', '2026-01-01 00:00:00', 0)"
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
        handoffs = conn.execute(
            "SELECT id, project_id, need_back, next_check FROM handoff"
        ).fetchall()
    finally:
        conn.close()

    assert len(projects) == 1
    assert projects[0][1] == "My Project"
    assert len(handoffs) == 1
    assert handoffs[0][2] == "Existing todo"
    assert handoffs[0][3] is None
    assert handoffs[0][1] == 1


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
    """Migrations raising in run_pending_migrations raises DatabaseInitializationError."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)
    try:
        mock_conn = MagicMock()
        mock_conn.exec_driver_sql.side_effect = Exception("Migration failed")
        mock_conn.__enter__ = lambda self: self
        mock_conn.__exit__ = lambda *a: None
        mock_begin = MagicMock(return_value=mock_conn)
        with patch.object(db.get_engine(), "begin", mock_begin):
            with pytest.raises((DatabaseInitializationError, Exception)) as exc_info:
                db.init_db()
            assert type(exc_info.value).__name__ == "DatabaseInitializationError"
            assert "failed" in exc_info.value.args[0].lower()
    finally:
        db.dispose_db()
