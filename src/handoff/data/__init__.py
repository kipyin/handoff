"""Data access helpers for projects, handoffs, check-ins and query workflows.

This package re-exports the public API from focused sub-modules so that existing
``from handoff.data import ...`` call sites continue to work without change.
"""

from handoff.data.activity import get_recent_activity, log_activity
from handoff.data.handoffs import (
    _UNSET,
    CheckInType,
    _latest_check_in,
    _pitchman_to_db,
    _Unset,
    conclude_handoff,
    create_check_in,
    create_handoff,
    delete_handoff,
    get_handoff_close_date,
    handoff_is_closed,
    handoff_is_open,
    reopen_handoff,
    snooze_handoff,
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
    _apply_handoff_filters,
    _check_in_note_subquery,
    _is_risk_handoff,
    _last_check_in_is_delayed,
    _last_concluded_check_in_date_subquery,
    _latest_check_in_is_concluded_predicate,
    _latest_check_in_is_open_predicate,
    _latest_check_in_type_subquery,
    _to_end_of_day,
    _to_start_of_day,
    count_open_handoffs,
    get_projects_with_handoff_summary,
    list_pitchmen,
    list_pitchmen_with_open_handoffs,
    query_action_handoffs,
    query_concluded_handoffs,
    query_handoffs,
    query_now_items,
    query_risk_handoffs,
    query_upcoming_handoffs,
)

__all__ = [
    # activity
    "log_activity",
    "get_recent_activity",
    # models re-exported for convenience
    "CheckInType",
    # projects
    "create_project",
    "list_projects",
    "get_project",
    "rename_project",
    "delete_project",
    "archive_project",
    "unarchive_project",
    # handoffs
    "_Unset",
    "_UNSET",
    "_pitchman_to_db",
    "create_handoff",
    "update_handoff",
    "snooze_handoff",
    "delete_handoff",
    # check-ins
    "create_check_in",
    "conclude_handoff",
    "_latest_check_in",
    "handoff_is_open",
    "handoff_is_closed",
    "get_handoff_close_date",
    "reopen_handoff",
    # queries
    "_last_check_in_is_delayed",
    "_is_risk_handoff",
    "_check_in_note_subquery",
    "_latest_check_in_type_subquery",
    "_latest_check_in_is_open_predicate",
    "_latest_check_in_is_concluded_predicate",
    "_last_concluded_check_in_date_subquery",
    "_apply_handoff_filters",
    "count_open_handoffs",
    "_to_start_of_day",
    "_to_end_of_day",
    "query_handoffs",
    "query_now_items",
    "query_upcoming_handoffs",
    "query_action_handoffs",
    "query_risk_handoffs",
    "query_concluded_handoffs",
    "list_pitchmen",
    "list_pitchmen_with_open_handoffs",
    "get_projects_with_handoff_summary",
    # import/export
    "import_payload",
    "get_export_payload",
]
