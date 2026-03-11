"""Typed rulebook contracts and built-in defaults for Now-page sections.

This module only defines contracts and built-in defaults for open-item
sectioning. It does not switch current query paths to a rule engine.

Rulebook semantics in this release:
- Rules apply only to open handoffs.
- Rules are exclusive and first-match-wins by priority.
- Unmatched open handoffs fall back to the Upcoming section.
- Concluded remains lifecycle-driven and outside open-rule matching.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import StrEnum
from typing import Any

from handoff.models import CheckInType

DEFAULT_RULEBOOK_VERSION = 1
DEFAULT_RISK_RULE_ID = "default_risk_deadline_near_and_delayed"
DEFAULT_ACTION_RULE_ID = "default_action_next_check_due"


class BuiltInSection(StrEnum):
    """Canonical built-in section ids."""

    RISK = "risk"
    ACTION_REQUIRED = "action_required"
    UPCOMING = "upcoming"
    CONCLUDED = "concluded"


class RuleConditionType(StrEnum):
    """Supported condition primitives for open-item rules."""

    DEADLINE_WITHIN_DAYS = "deadline_within_days"
    LATEST_CHECK_IN_TYPE_IS = "latest_check_in_type_is"
    NEXT_CHECK_DUE = "next_check_due"


@dataclass(slots=True, frozen=True)
class DeadlineWithinDaysCondition:
    """Match when deadline is present and within ``days`` from today."""

    days: int

    def __post_init__(self) -> None:
        if self.days < 0:
            msg = "deadline-within-days condition requires days >= 0"
            raise ValueError(msg)

    @property
    def condition_type(self) -> RuleConditionType:
        return RuleConditionType.DEADLINE_WITHIN_DAYS


@dataclass(slots=True, frozen=True)
class LatestCheckInTypeIsCondition:
    """Match when the latest check-in has the configured type."""

    check_in_type: CheckInType

    def __post_init__(self) -> None:
        if not isinstance(self.check_in_type, CheckInType):
            msg = "latest-check-in-type-is condition requires a CheckInType value"
            raise ValueError(msg)

    @property
    def condition_type(self) -> RuleConditionType:
        return RuleConditionType.LATEST_CHECK_IN_TYPE_IS


@dataclass(slots=True, frozen=True)
class NextCheckDueCondition:
    """Match when ``next_check`` is due now or overdue.

    ``include_missing_next_check`` defaults to False so missing dates do not
    become action-required by default.
    """

    include_missing_next_check: bool = False

    @property
    def condition_type(self) -> RuleConditionType:
        return RuleConditionType.NEXT_CHECK_DUE


type RuleCondition = (
    DeadlineWithinDaysCondition | LatestCheckInTypeIsCondition | NextCheckDueCondition
)


def rule_condition_to_dict(condition: RuleCondition) -> dict[str, Any]:
    """Serialize a rule condition to a JSON-compatible dictionary."""
    if isinstance(condition, DeadlineWithinDaysCondition):
        return {
            "condition_type": condition.condition_type.value,
            "days": condition.days,
        }
    if isinstance(condition, LatestCheckInTypeIsCondition):
        return {
            "condition_type": condition.condition_type.value,
            "check_in_type": condition.check_in_type.value,
        }
    if isinstance(condition, NextCheckDueCondition):
        return {
            "condition_type": condition.condition_type.value,
            "include_missing_next_check": condition.include_missing_next_check,
        }
    msg = f"Unsupported rule condition type: {type(condition)!r}"
    raise ValueError(msg)


def rule_condition_from_dict(payload: dict[str, Any]) -> RuleCondition:
    """Deserialize a rule condition from dictionary form."""
    raw_type = payload.get("condition_type")
    try:
        condition_type = RuleConditionType(str(raw_type))
    except ValueError as exc:
        msg = f"Unknown rule condition type: {raw_type!r}"
        raise ValueError(msg) from exc

    if condition_type == RuleConditionType.DEADLINE_WITHIN_DAYS:
        return DeadlineWithinDaysCondition(days=int(payload["days"]))
    if condition_type == RuleConditionType.LATEST_CHECK_IN_TYPE_IS:
        return LatestCheckInTypeIsCondition(
            check_in_type=CheckInType(str(payload["check_in_type"]))
        )
    if condition_type == RuleConditionType.NEXT_CHECK_DUE:
        return NextCheckDueCondition(
            include_missing_next_check=bool(payload.get("include_missing_next_check", False))
        )
    msg = f"Unsupported rule condition type: {condition_type!r}"
    raise ValueError(msg)


@dataclass(slots=True, frozen=True)
class RuleDefinition:
    """Typed rule definition for one open-item section."""

    rule_id: str
    name: str
    section_id: str
    priority: int
    conditions: tuple[RuleCondition, ...]
    enabled: bool = True
    match_reason: str = ""

    def __post_init__(self) -> None:
        if not self.rule_id.strip():
            raise ValueError("rule_id must be non-empty")
        if not self.name.strip():
            raise ValueError("name must be non-empty")
        if not self.section_id.strip():
            raise ValueError("section_id must be non-empty")
        if not self.conditions:
            raise ValueError("rules must define at least one condition")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "rule_id": self.rule_id,
            "name": self.name,
            "section_id": self.section_id,
            "priority": self.priority,
            "enabled": self.enabled,
            "match_reason": self.match_reason,
            "conditions": [rule_condition_to_dict(condition) for condition in self.conditions],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RuleDefinition:
        """Deserialize from dictionary form."""
        conditions_payload = payload.get("conditions")
        if not isinstance(conditions_payload, list):
            raise ValueError("conditions must be a list")
        return cls(
            rule_id=str(payload["rule_id"]),
            name=str(payload["name"]),
            section_id=str(payload["section_id"]),
            priority=int(payload.get("priority", 0)),
            enabled=bool(payload.get("enabled", True)),
            match_reason=str(payload.get("match_reason", "")),
            conditions=tuple(rule_condition_from_dict(item) for item in conditions_payload),
        )


@dataclass(slots=True, frozen=True)
class RulebookSettings:
    """Typed top-level rulebook settings contract."""

    version: int
    rules: tuple[RuleDefinition, ...]
    first_match_wins: bool = True
    open_items_fallback_section: str = BuiltInSection.UPCOMING.value
    concluded_section: str = BuiltInSection.CONCLUDED.value

    def __post_init__(self) -> None:
        if self.version < 1:
            raise ValueError("version must be >= 1")
        if not self.open_items_fallback_section.strip():
            raise ValueError("open_items_fallback_section must be non-empty")
        if not self.concluded_section.strip():
            raise ValueError("concluded_section must be non-empty")
        rule_ids = [rule.rule_id for rule in self.rules]
        if len(rule_ids) != len(set(rule_ids)):
            raise ValueError("rule_ids must be unique")

    def to_dict(self) -> dict[str, Any]:
        """Serialize to a JSON-compatible dictionary."""
        return {
            "version": self.version,
            "first_match_wins": self.first_match_wins,
            "open_items_fallback_section": self.open_items_fallback_section,
            "concluded_section": self.concluded_section,
            "rules": [rule.to_dict() for rule in self.rules],
        }

    @classmethod
    def from_dict(cls, payload: dict[str, Any]) -> RulebookSettings:
        """Deserialize from dictionary form."""
        rules_payload = payload.get("rules")
        if not isinstance(rules_payload, list):
            raise ValueError("rules must be a list")
        return cls(
            version=int(payload.get("version", DEFAULT_RULEBOOK_VERSION)),
            first_match_wins=bool(payload.get("first_match_wins", True)),
            open_items_fallback_section=str(
                payload.get("open_items_fallback_section", BuiltInSection.UPCOMING.value)
            ),
            concluded_section=str(payload.get("concluded_section", BuiltInSection.CONCLUDED.value)),
            rules=tuple(RuleDefinition.from_dict(rule_payload) for rule_payload in rules_payload),
        )


@dataclass(slots=True, frozen=True)
class RuleMatchResult:
    """Typed result contract for one handoff section match."""

    section_id: str
    explanation: str
    matched_rule_id: str | None = None
    is_fallback: bool = False

    def __post_init__(self) -> None:
        if not self.section_id.strip():
            raise ValueError("section_id must be non-empty")
        if not self.explanation.strip():
            raise ValueError("explanation must be non-empty")
        if self.is_fallback and self.matched_rule_id is not None:
            raise ValueError("fallback match results must not include matched_rule_id")
        if not self.is_fallback and self.matched_rule_id is None:
            raise ValueError("non-fallback match results require matched_rule_id")


def build_default_rulebook_settings(*, deadline_near_days: int = 1) -> RulebookSettings:
    """Return built-in default rulebook definitions.

    Defaults mirror current open-item semantics:
    - Risk: deadline within N days and latest check-in is delayed.
    - Action required: next_check is due now or overdue (and not matched by Risk).
    - Upcoming: fallback for unmatched open handoffs.
    - Concluded: lifecycle-driven and outside open-rule matching.
    """
    normalized_near_days = max(0, int(deadline_near_days))
    risk_rule = RuleDefinition(
        rule_id=DEFAULT_RISK_RULE_ID,
        name="Risk",
        section_id=BuiltInSection.RISK.value,
        priority=10,
        enabled=True,
        match_reason="Deadline is near and latest check-in is delayed.",
        conditions=(
            DeadlineWithinDaysCondition(days=normalized_near_days),
            LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),
        ),
    )
    action_rule = RuleDefinition(
        rule_id=DEFAULT_ACTION_RULE_ID,
        name="Action required",
        section_id=BuiltInSection.ACTION_REQUIRED.value,
        priority=20,
        enabled=True,
        match_reason="Next check is due now or overdue.",
        conditions=(NextCheckDueCondition(include_missing_next_check=False),),
    )
    return RulebookSettings(
        version=DEFAULT_RULEBOOK_VERSION,
        rules=(risk_rule, action_rule),
        first_match_wins=True,
        open_items_fallback_section=BuiltInSection.UPCOMING.value,
        concluded_section=BuiltInSection.CONCLUDED.value,
    )


DEFAULT_RULEBOOK_SETTINGS = build_default_rulebook_settings()


__all__ = [
    "BuiltInSection",
    "DEFAULT_ACTION_RULE_ID",
    "DEFAULT_RISK_RULE_ID",
    "DEFAULT_RULEBOOK_SETTINGS",
    "DEFAULT_RULEBOOK_VERSION",
    "DeadlineWithinDaysCondition",
    "LatestCheckInTypeIsCondition",
    "NextCheckDueCondition",
    "RuleCondition",
    "RuleConditionType",
    "RuleDefinition",
    "RuleMatchResult",
    "RulebookSettings",
    "build_default_rulebook_settings",
    "rule_condition_from_dict",
    "rule_condition_to_dict",
]
