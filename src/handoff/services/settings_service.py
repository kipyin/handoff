"""Settings service helpers for backup import, export, and app preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from handoff.data import get_export_payload as _get_export_payload
from handoff.data import import_payload as _import_payload

DEFAULT_DEADLINE_NEAR_DAYS = 1
DEADLINE_NEAR_DAYS_MIN = 1
DEADLINE_NEAR_DAYS_MAX = 14


def _get_settings_path() -> Path:
    """Return the path to the persisted app settings file (next to the DB)."""
    from handoff.db import get_db_path

    return get_db_path().parent / "handoff_settings.json"


def _load_settings() -> dict[str, Any]:
    """Load settings from disk. Returns default dict if file missing or invalid."""
    path = _get_settings_path()
    if not path.exists():
        return {}
    try:
        with path.open(encoding="utf-8") as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_settings(settings: dict[str, Any]) -> None:
    """Write settings to disk."""
    path = _get_settings_path()
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8") as f:
        json.dump(settings, f, indent=2)


def get_deadline_near_days() -> int:
    """Return the number of days within which a deadline is considered at risk (for Now page)."""
    settings = _load_settings()
    val = settings.get("deadline_near_days")
    if val is None:
        return DEFAULT_DEADLINE_NEAR_DAYS
    try:
        n = int(val)
        if DEADLINE_NEAR_DAYS_MIN <= n <= DEADLINE_NEAR_DAYS_MAX:
            return n
    except (TypeError, ValueError):
        pass
    return DEFAULT_DEADLINE_NEAR_DAYS


def set_deadline_near_days(value: int) -> None:
    """Persist the deadline-at-risk window in days. Clamped to min/max."""
    n = max(DEADLINE_NEAR_DAYS_MIN, min(DEADLINE_NEAR_DAYS_MAX, int(value)))
    settings = _load_settings()
    settings["deadline_near_days"] = n
    _save_settings(settings)


def get_export_payload() -> dict[str, Any]:
    """Return the current backup/export payload."""
    return _get_export_payload()


def import_payload(payload: dict[str, Any]) -> None:
    """Replace persisted data from a validated backup payload."""
    _import_payload(payload)
