"""Activity log helpers."""

from __future__ import annotations

import json
from typing import Any

from loguru import logger
from sqlalchemy import text

from handoff.db import session_context


def log_activity(
    entity_type: str,
    entity_id: int | None,
    action: str,
    details: dict[str, Any] | None = None,
) -> None:
    """Record an activity log entry for the audit trail.

    Args:
        entity_type: One of "project", "handoff".
        entity_id: Id of the entity, or None for bulk operations.
        action: One of created, updated, concluded, deleted, archived, unarchived.
        details: Optional JSON-serializable dict with extra context.
    """
    try:
        with session_context() as session:
            details_str = json.dumps(details) if details else None
            session.execute(
                text(
                    "INSERT INTO activity_log (timestamp, entity_type, entity_id, action, details) "
                    "VALUES (CURRENT_TIMESTAMP, :entity_type, :entity_id, :action, :details)"
                ),
                {
                    "entity_type": entity_type,
                    "entity_id": entity_id,
                    "action": action,
                    "details": details_str,
                },
            )
            session.commit()
    except Exception as exc:  # noqa: BLE001
        logger.warning("Activity log insert failed: {}", exc)


def get_recent_activity(limit: int = 20) -> list[dict[str, Any]]:
    """Return recent activity log entries, newest first.

    Args:
        limit: Maximum number of entries to return.

    Returns:
        List of dicts with timestamp, entity_type, entity_id, action, details.
    """
    with session_context() as session:
        result = session.execute(
            text(
                "SELECT timestamp, entity_type, entity_id, action, details "
                "FROM activity_log ORDER BY timestamp DESC LIMIT :limit"
            ),
            {"limit": limit},
        )
        rows = result.fetchall()
    out: list[dict[str, Any]] = []
    for row in rows:
        details = None
        if row[4]:
            try:
                details = json.loads(row[4])
            except (json.JSONDecodeError, TypeError):
                details = {"raw": row[4]}
        out.append(
            {
                "timestamp": row[0],
                "entity_type": row[1],
                "entity_id": row[2],
                "action": row[3],
                "details": details,
            }
        )
    return out
