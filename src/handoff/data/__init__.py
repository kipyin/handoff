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
    query_open_handoffs_for_now,
    query_risk_handoffs,
    query_upcoming_handoffs,
)

__all__ = [
    "_UNSET",
    # models re-exported for convenience
    "CheckInType",
    # handoffs
    "_Unset",
    "_apply_handoff_filters",
    "_check_in_note_subquery",
    "_is_risk_handoff",
    # queries
    "_last_check_in_is_delayed",
    "_last_concluded_check_in_date_subquery",
    "_latest_check_in",
    "_latest_check_in_is_concluded_predicate",
    "_latest_check_in_is_open_predicate",
    "_latest_check_in_type_subquery",
    "_pitchman_to_db",
    "_to_end_of_day",
    "_to_start_of_day",
    "archive_project",
    "conclude_handoff",
    "count_open_handoffs",
    # check-ins
    "create_check_in",
    "create_handoff",
    # projects
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
    # import/export
    "import_payload",
    "list_pitchmen",
    "list_pitchmen_with_open_handoffs",
    "list_projects",
    # activity
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
