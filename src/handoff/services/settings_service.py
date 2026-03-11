"""Settings service helpers for backup import, export, and app preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from handoff.data import get_export_payload as _get_export_payload
from handoff.data import import_payload as _import_payload
from handoff.rulebook import RulebookSettings, build_default_rulebook_settings

DEFAULT_DEADLINE_NEAR_DAYS = 1
DEADLINE_NEAR_DAYS_MIN = 1
DEADLINE_NEAR_DAYS_MAX = 14

RULEBOOK_SETTINGS_KEY = "rulebook"


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


def get_rulebook_settings() -> RulebookSettings:
    """Return global rulebook settings from disk. Fall back to defaults if invalid/missing."""
    settings = _load_settings()
    rulebook_payload = settings.get(RULEBOOK_SETTINGS_KEY)
    if rulebook_payload is None:
        return build_default_rulebook_settings(deadline_near_days=get_deadline_near_days())
    if not isinstance(rulebook_payload, dict):
        return build_default_rulebook_settings(deadline_near_days=get_deadline_near_days())
    try:
        parsed = RulebookSettings.from_dict(rulebook_payload)
        if not parsed.rules:
            return build_default_rulebook_settings(deadline_near_days=get_deadline_near_days())
        return parsed
    except (ValueError, KeyError, TypeError):
        return build_default_rulebook_settings(deadline_near_days=get_deadline_near_days())


def save_rulebook_settings(settings: RulebookSettings) -> None:
    """Persist the global rulebook to settings JSON. Preserves other settings keys."""
    data = _load_settings()
    data[RULEBOOK_SETTINGS_KEY] = settings.to_dict()
    _save_settings(data)


def reset_rulebook_settings() -> None:
    """Reset the rulebook to built-in defaults and persist."""
    defaults = build_default_rulebook_settings(deadline_near_days=get_deadline_near_days())
    save_rulebook_settings(defaults)


def get_export_payload() -> dict[str, Any]:
    """Return the current backup/export payload."""
    return _get_export_payload()


def import_payload(payload: dict[str, Any]) -> None:
    """Replace persisted data from a validated backup payload."""
    _import_payload(payload)
