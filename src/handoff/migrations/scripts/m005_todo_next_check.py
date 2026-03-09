"""Migration 005: add next_check column to todo table."""

from __future__ import annotations

from sqlalchemy.engine import Connection

version = "005_todo_next_check"


def migrate(conn: Connection) -> None:
    result = conn.exec_driver_sql("PRAGMA table_info('todo')")
    todo_columns = {row[1] for row in result}
    if not todo_columns:
        return
    if "next_check" not in todo_columns:
        conn.exec_driver_sql("ALTER TABLE todo ADD COLUMN next_check DATE NULL")
