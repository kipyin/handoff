"""Settings service helpers for backup import, export, and app preferences."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from handoff.data import get_export_payload as _get_export_payload
from handoff.data import import_payload as _import_payload
from handoff.rulebook import (
    DEFAULT_RISK_RULE_ID,
    DeadlineWithinDaysCondition,
    RulebookSettings,
    RuleDefinition,
    build_default_rulebook_settings,
)

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


def _deadline_near_days_from_dict(settings: dict[str, Any]) -> int:
    """Extract deadline_near_days from a settings dict with validation."""
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


def get_deadline_near_days() -> int:
    """Return the number of days within which a deadline is considered at risk (for Now page)."""
    return _deadline_near_days_from_dict(_load_settings())


def set_deadline_near_days(value: int) -> None:
    """Persist the deadline-at-risk window in days. Clamped to min/max."""
    n = max(DEADLINE_NEAR_DAYS_MIN, min(DEADLINE_NEAR_DAYS_MAX, int(value)))
    settings = _load_settings()
    settings["deadline_near_days"] = n
    _save_settings(settings)


def _risk_rule_deadline_days(settings: RulebookSettings) -> int | None:
    """Extract the Risk rule's deadline-within-days value if present."""
    for rule in settings.rules:
        if rule.rule_id != DEFAULT_RISK_RULE_ID:
            continue
        for cond in rule.conditions:
            if isinstance(cond, DeadlineWithinDaysCondition):
                return cond.days
        break
    return None


def _sync_risk_rule_deadline(
    settings: RulebookSettings, deadline_near_days: int
) -> RulebookSettings:
    """Synchronize the Risk rule's deadline condition with the given value.

    Updates the built-in Risk rule's deadline-within-days condition to match
    deadline_near_days, preserving all other rules unchanged.

    Args:
        settings: The rulebook settings to synchronize.
        deadline_near_days: The value to use for the Risk rule's deadline condition.

    Returns:
        A new RulebookSettings with the Risk rule's deadline condition updated.
    """
    deadline_near = deadline_near_days
    new_rules: list[RuleDefinition] = []
    for rule in settings.rules:
        if rule.rule_id != DEFAULT_RISK_RULE_ID:
            new_rules.append(rule)
            continue
        new_conditions: list = []
        for cond in rule.conditions:
            if isinstance(cond, DeadlineWithinDaysCondition):
                new_conditions.append(DeadlineWithinDaysCondition(days=deadline_near))
            else:
                new_conditions.append(cond)
        new_rules.append(
            RuleDefinition(
                rule_id=rule.rule_id,
                name=rule.name,
                section_id=rule.section_id,
                priority=rule.priority,
                enabled=rule.enabled,
                match_reason=rule.match_reason,
                conditions=tuple(new_conditions),
            )
        )
    return RulebookSettings(
        version=settings.version,
        rules=tuple(new_rules),
        first_match_wins=settings.first_match_wins,
        open_items_fallback_section=settings.open_items_fallback_section,
        concluded_section=settings.concluded_section,
    )


def get_rulebook_settings() -> RulebookSettings:
    """Return global rulebook settings from disk. Fall back to defaults if invalid/missing."""
    settings = _load_settings()
    deadline_near = _deadline_near_days_from_dict(settings)
    rulebook_payload = settings.get(RULEBOOK_SETTINGS_KEY)
    if rulebook_payload is None:
        return build_default_rulebook_settings(deadline_near_days=deadline_near)
    if not isinstance(rulebook_payload, dict):
        return build_default_rulebook_settings(deadline_near_days=deadline_near)
    try:
        parsed = RulebookSettings.from_dict(rulebook_payload)
        if not parsed.rules:
            return build_default_rulebook_settings(deadline_near_days=deadline_near)
        return _sync_risk_rule_deadline(parsed, deadline_near)
    except (ValueError, KeyError, TypeError):
        return build_default_rulebook_settings(deadline_near_days=deadline_near)


def save_rulebook_settings(rulebook_settings: RulebookSettings) -> None:
    """Persist the global rulebook to settings JSON. Preserves other settings keys.

    When the built-in Risk rule has a deadline-within-days condition, its value
    is used to update the global deadline_near_days setting so user edits persist.
    """
    data = _load_settings()
    risk_days = _risk_rule_deadline_days(rulebook_settings)
    if risk_days is not None:
        n = max(DEADLINE_NEAR_DAYS_MIN, min(DEADLINE_NEAR_DAYS_MAX, int(risk_days)))
        data["deadline_near_days"] = n
    deadline_near = _deadline_near_days_from_dict(data)
    synced = _sync_risk_rule_deadline(rulebook_settings, deadline_near)
    data[RULEBOOK_SETTINGS_KEY] = synced.to_dict()
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


def log_application_action(action: str, **details: Any) -> None:
    import handoff.bootstrap.logging as _logging

    _logging.log_application_action(action, **details)
