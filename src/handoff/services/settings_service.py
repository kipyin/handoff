"""Settings service helpers for backup import and export."""

from __future__ import annotations

from typing import Any

from handoff.data import get_export_payload as _get_export_payload
from handoff.data import import_payload as _import_payload


def get_export_payload() -> dict[str, Any]:
    """Return the current backup/export payload."""
    return _get_export_payload()


def import_payload(payload: dict[str, Any]) -> None:
    """Replace persisted data from a validated backup payload."""
    _import_payload(payload)
