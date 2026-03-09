"""Database migrations — numbered scripts applied in order on startup."""

from handoff.migrations.runner import get_applied_versions, run_pending_migrations

__all__ = ["get_applied_versions", "run_pending_migrations"]
