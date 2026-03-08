"""Migration 004: add activity_log table for audit trail (A7)."""

from __future__ import annotations

from sqlalchemy.engine import Connection

version = "004_activity_log"


def migrate(conn: Connection) -> None:
    conn.exec_driver_sql(
        """
        CREATE TABLE IF NOT EXISTS activity_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            timestamp TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
            entity_type TEXT NOT NULL,
            entity_id INTEGER,
            action TEXT NOT NULL,
            details TEXT
        )
        """
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_activity_log_timestamp ON activity_log (timestamp DESC)"
    )
    conn.exec_driver_sql(
        "CREATE INDEX IF NOT EXISTS ix_activity_log_entity ON activity_log (entity_type, entity_id)"
    )
