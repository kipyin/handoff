"""Migration 001: add completed_at and is_archived columns to todo table."""

from __future__ import annotations

from sqlalchemy.engine import Connection

version = "001_todo_completed_at_is_archived"


def migrate(conn: Connection) -> None:
    result = conn.exec_driver_sql("PRAGMA table_info('todo')")
    todo_columns = {row[1] for row in result}
    if not todo_columns:
        return
    if "completed_at" not in todo_columns:
        conn.exec_driver_sql("ALTER TABLE todo ADD COLUMN completed_at TIMESTAMP NULL")
    if "is_archived" not in todo_columns:
        conn.exec_driver_sql("ALTER TABLE todo ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0")
