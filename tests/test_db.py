"""Tests for DB initialisation and lightweight migrations."""

from __future__ import annotations

import importlib
import sqlite3
from pathlib import Path

import pytest


def _reload_db_module(db_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Reload handoff.db with TODO_APP_DB_PATH pointed at db_path."""
    monkeypatch.setenv("TODO_APP_DB_PATH", str(db_path))
    import handoff.db as db  # type: ignore[import-not-found]

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

    sqlite_path = _get_sqlite_path(db.DATABASE_URL)
    todo_columns = _fetch_columns(sqlite_path, "todo")
    project_columns = _fetch_columns(sqlite_path, "project")
    # Sanity-check core columns plus the migration columns.
    assert {"id", "project_id", "name"}.issubset(todo_columns)
    assert "completed_at" in todo_columns
    assert "is_archived" in todo_columns
    assert "is_archived" in project_columns


def test_init_db_adds_completed_at_to_existing_schema(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """init_db applies the completed_at migration for an older todo schema."""
    db_path = tmp_path / "todo.db"
    db = _reload_db_module(db_path, monkeypatch)

    sqlite_path = _get_sqlite_path(db.DATABASE_URL)
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
    assert "is_archived" in project_columns
