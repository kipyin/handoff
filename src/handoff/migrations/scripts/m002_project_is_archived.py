"""Migration 002: add is_archived column to project table."""

from __future__ import annotations

from sqlalchemy.engine import Connection

version = "002_project_is_archived"


def migrate(conn: Connection) -> None:
    result = conn.exec_driver_sql("PRAGMA table_info('project')")
    project_columns = {row[1] for row in result}
    if "is_archived" not in project_columns:
        conn.exec_driver_sql(
            "ALTER TABLE project ADD COLUMN is_archived BOOLEAN NOT NULL DEFAULT 0"
        )
