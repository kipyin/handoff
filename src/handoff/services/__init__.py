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
from handoff.services.todo_service import complete_todo

__all__ = [
    "complete_todo",
    "get_cycle_time_by_project",
    "get_dashboard_metrics",
    "get_deadline_adherence_trend",
    "get_exportable_metrics",
    "get_helper_load",
    "get_per_helper_throughput",
    "get_per_project_throughput",
    "get_weekly_throughput",
]
