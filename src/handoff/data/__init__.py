"""Data access helpers for projects, handoffs, check-ins and query workflows.

This package re-exports the public API from focused sub-modules so that existing
``from handoff.data import ...`` call sites continue to work without change.
"""

from handoff.data.activity import get_recent_activity, log_activity
from handoff.data.handoffs import (
    CheckInType,
    conclude_handoff,
    create_check_in,
    create_handoff,
    delete_handoff,
    get_handoff_close_date,
    handoff_is_closed,
    handoff_is_open,
    reopen_handoff,
    update_handoff,
)
from handoff.data.io import get_export_payload, import_payload
from handoff.data.projects import (
    archive_project,
    create_project,
    delete_project,
    get_project,
    list_projects,
    rename_project,
    unarchive_project,
)
from handoff.data.queries import (
    count_open_handoffs,
    get_projects_with_handoff_summary,
    list_pitchmen,
    list_pitchmen_with_open_handoffs,
    query_action_handoffs,
    query_concluded_handoffs,
    query_handoffs,
    query_now_items,
    query_open_handoffs_for_now,
    query_risk_handoffs,
    query_upcoming_handoffs,
)

__all__ = [
    "CheckInType",
    "archive_project",
    "conclude_handoff",
    "count_open_handoffs",
    "create_check_in",
    "create_handoff",
    "create_project",
    "delete_handoff",
    "delete_project",
    "get_export_payload",
    "get_handoff_close_date",
    "get_project",
    "get_projects_with_handoff_summary",
    "get_recent_activity",
    "handoff_is_closed",
    "handoff_is_open",
    "import_payload",
    "list_pitchmen",
    "list_pitchmen_with_open_handoffs",
    "list_projects",
    "log_activity",
    "query_action_handoffs",
    "query_concluded_handoffs",
    "query_handoffs",
    "query_now_items",
    "query_open_handoffs_for_now",
    "query_risk_handoffs",
    "query_upcoming_handoffs",
    "rename_project",
    "reopen_handoff",
    "unarchive_project",
    "update_handoff",
]
