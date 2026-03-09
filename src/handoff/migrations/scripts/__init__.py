"""Migration scripts — each module defines version and migrate(conn)."""

from handoff.migrations.scripts import (
    m001_todo_completed_at_is_archived,
    m002_project_is_archived,
    m003_legacy_status_labels,
    m004_activity_log,
    m005_todo_next_check,
)

# Ordered list of migrations; new migrations append here.
ALL = [
    m001_todo_completed_at_is_archived,
    m002_project_is_archived,
    m003_legacy_status_labels,
    m004_activity_log,
    m005_todo_next_check,
]
