"""Service layer: orchestration and business logic between pages and data.

Architecture: pages/ (UI) → services/ (orchestration) → data.py (persistence)
"""

from handoff.services.dashboard_service import (
    get_cycle_time_by_project,
    get_dashboard_metrics,
    get_deadline_adherence_trend,
    get_exportable_metrics,
    get_helper_load,
    get_per_helper_throughput,
    get_per_project_throughput,
    get_weekly_throughput,
)
from handoff.services.project_service import (
    archive_project,
    create_project,
    delete_project,
    get_projects_with_todo_summary,
    list_projects,
    rename_project,
    unarchive_project,
)
from handoff.services.settings_service import get_export_payload, import_payload
from handoff.services.todo_service import (
    complete_todo,
    create_todo,
    delete_todo,
    list_helpers,
    query_todos,
    update_todo,
)

__all__ = [
    "archive_project",
    "complete_todo",
    "create_project",
    "create_todo",
    "delete_project",
    "delete_todo",
    "get_cycle_time_by_project",
    "get_dashboard_metrics",
    "get_deadline_adherence_trend",
    "get_exportable_metrics",
    "get_export_payload",
    "get_helper_load",
    "get_projects_with_todo_summary",
    "get_per_helper_throughput",
    "get_per_project_throughput",
    "get_weekly_throughput",
    "import_payload",
    "list_helpers",
    "list_projects",
    "query_todos",
    "rename_project",
    "unarchive_project",
    "update_todo",
]
