"""Migration 003: migrate legacy status labels (delegated -> handoff, DELEGATED -> HANDOFF)."""

from __future__ import annotations

from sqlalchemy.engine import Connection

version = "003_legacy_status_labels"


def migrate(conn: Connection) -> None:
    result = conn.exec_driver_sql("PRAGMA table_info('todo')")
    todo_columns = {row[1] for row in result}
    if not todo_columns or "status" not in todo_columns:
        return
    conn.exec_driver_sql("UPDATE todo SET status = 'handoff' WHERE status = 'delegated'")
    conn.exec_driver_sql("UPDATE todo SET status = 'HANDOFF' WHERE status = 'DELEGATED'")
