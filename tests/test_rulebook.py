"""Tests for typed rulebook contracts and built-in defaults."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date

import pytest

import handoff.data as data
from handoff.models import CheckIn, CheckInType, Handoff, Project
from handoff.rulebook import (
    BuiltInSection,
    DeadlineWithinDaysCondition,
    LatestCheckInTypeIsCondition,
    NextCheckDueCondition,
    RulebookSettings,
    RuleConditionType,
    RuleDefinition,
    RuleMatchResult,
    build_default_rulebook_settings,
    evaluate_open_handoff,
    rule_condition_from_dict,
    rule_condition_to_dict,
)


def _patch_session_context(monkeypatch, session) -> None:
    """Patch session_context in data sub-modules to reuse the test session."""
    import handoff.data.activity as _da
    import handoff.data.handoffs as _dh
    import handoff.data.io as _dio
    import handoff.data.projects as _dp
    import handoff.data.queries as _dq

    @contextmanager
    def _session_context():
        yield session

    for mod in (_da, _dh, _dio, _dp, _dq):
        monkeypatch.setattr(mod, "session_context", _session_context)


def _patch_date(monkeypatch, fixed_date_class) -> None:
    """Patch date.today() in sub-modules that call it directly."""
    import handoff.data.handoffs as _dh
    import handoff.data.queries as _dq

    monkeypatch.setattr(_dh, "date", fixed_date_class)
    monkeypatch.setattr(_dq, "date", fixed_date_class)


def test_default_rulebook_contract_and_fallback_semantics() -> None:
    """Built-in defaults define Risk + Action rules and explicit fallback semantics."""
    settings = build_default_rulebook_settings(deadline_near_days=2)

    assert settings.version >= 1
    assert settings.first_match_wins is True
    assert settings.open_items_fallback_section == BuiltInSection.UPCOMING.value
    assert settings.concluded_section == BuiltInSection.CONCLUDED.value
    assert len(settings.rules) == 2

    risk_rule, action_rule = settings.rules
    assert risk_rule.section_id == BuiltInSection.RISK.value
    assert action_rule.section_id == BuiltInSection.ACTION_REQUIRED.value
    assert risk_rule.priority < action_rule.priority

    risk_condition_types = {condition.condition_type for condition in risk_rule.conditions}
    assert risk_condition_types == {
        RuleConditionType.DEADLINE_WITHIN_DAYS,
        RuleConditionType.LATEST_CHECK_IN_TYPE_IS,
    }
    deadline_condition = next(
        condition
        for condition in risk_rule.conditions
        if isinstance(condition, DeadlineWithinDaysCondition)
    )
    check_in_type_condition = next(
        condition
        for condition in risk_rule.conditions
        if isinstance(condition, LatestCheckInTypeIsCondition)
    )
    assert deadline_condition.days == 2
    assert check_in_type_condition.check_in_type == CheckInType.DELAYED

    assert len(action_rule.conditions) == 1
    assert isinstance(action_rule.conditions[0], NextCheckDueCondition)
    assert action_rule.conditions[0].include_missing_next_check is False


def test_rulebook_validation_and_roundtrip() -> None:
    """Rulebook contracts validate duplicate ids and support dict roundtrips."""
    settings = build_default_rulebook_settings(deadline_near_days=1)
    payload = settings.to_dict()
    reloaded = RulebookSettings.from_dict(payload)

    assert reloaded == settings

    duplicate_rule = RuleDefinition(
        rule_id=settings.rules[0].rule_id,
        name="Duplicate",
        section_id=BuiltInSection.RISK.value,
        priority=30,
        conditions=(NextCheckDueCondition(),),
    )
    with pytest.raises(ValueError, match="rule_ids must be unique"):
        RulebookSettings(
            version=1,
            rules=(settings.rules[0], duplicate_rule),
        )


def test_rule_condition_and_match_result_validation() -> None:
    """Condition and match-result contracts reject invalid payloads."""
    with pytest.raises(ValueError, match="days >= 0"):
        DeadlineWithinDaysCondition(days=-1)

    with pytest.raises(ValueError, match="CheckInType value"):
        LatestCheckInTypeIsCondition(check_in_type="delayed")  # type: ignore[arg-type]

    fallback_result = RuleMatchResult(
        section_id=BuiltInSection.UPCOMING.value,
        explanation="No enabled rule matched; item falls back to Upcoming.",
        matched_rule_id=None,
        is_fallback=True,
    )
    assert fallback_result.is_fallback is True

    with pytest.raises(ValueError, match="require matched_rule_id"):
        RuleMatchResult(
            section_id=BuiltInSection.RISK.value,
            explanation="Matched risk rule.",
            matched_rule_id=None,
            is_fallback=False,
        )

    with pytest.raises(ValueError, match="matched_rule_id must be non-empty"):
        RuleMatchResult(
            section_id=BuiltInSection.RISK.value,
            explanation="Matched risk rule.",
            matched_rule_id="   ",
            is_fallback=False,
        )

    with pytest.raises(ValueError, match="must not include matched_rule_id"):
        RuleMatchResult(
            section_id=BuiltInSection.UPCOMING.value,
            explanation="No enabled rule matched; item falls back to Upcoming.",
            matched_rule_id="risk_rule",
            is_fallback=True,
        )


def test_rule_condition_serialization_and_invalid_payloads() -> None:
    """Condition serialization roundtrips and malformed payloads fail fast."""
    roundtrip_conditions = (
        DeadlineWithinDaysCondition(days=3),
        LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),
        NextCheckDueCondition(include_missing_next_check=True),
    )
    for condition in roundtrip_conditions:
        payload = rule_condition_to_dict(condition)
        assert rule_condition_from_dict(payload) == condition

    with pytest.raises(ValueError, match="must be a dict"):
        rule_condition_from_dict(["not", "a", "dict"])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="Unknown rule condition type"):
        rule_condition_from_dict({"condition_type": "unknown_condition"})

    with pytest.raises(ValueError, match="Unsupported rule condition type"):
        rule_condition_to_dict(object())  # type: ignore[arg-type]


def test_rulebook_from_dict_validation_and_deadline_day_normalization() -> None:
    """Typed contracts reject malformed dictionaries and normalize near-day input."""
    with pytest.raises(ValueError, match="payload must be a dict"):
        RuleDefinition.from_dict(["bad"])  # type: ignore[arg-type]

    with pytest.raises(ValueError, match="conditions must be a list"):
        RuleDefinition.from_dict(
            {
                "rule_id": "r1",
                "name": "Rule 1",
                "section_id": BuiltInSection.RISK.value,
                "conditions": "not-a-list",
            }
        )

    with pytest.raises(ValueError, match=r"conditions\[0\] must be a dict"):
        RuleDefinition.from_dict(
            {
                "rule_id": "r1",
                "name": "Rule 1",
                "section_id": BuiltInSection.RISK.value,
                "conditions": ["bad-item"],
            }
        )

    with pytest.raises(ValueError, match="rules must be a list"):
        RulebookSettings.from_dict({"rules": "not-a-list"})  # type: ignore[arg-type]

    settings = build_default_rulebook_settings(deadline_near_days=-5)
    risk_rule = settings.rules[0]
    normalized_days = next(
        condition.days
        for condition in risk_rule.conditions
        if isinstance(condition, DeadlineWithinDaysCondition)
    )
    assert normalized_days == 0


def test_rule_evaluation_uses_priority_order_and_match_explanation() -> None:
    """Rule evaluation is exclusive, priority-based, and returns the rule reason."""
    handoff = Handoff(
        project_id=1,
        need_back="Needs attention",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 10),
    )
    handoff.check_ins = [
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 9),
            check_in_type=CheckInType.DELAYED,
        )
    ]
    settings = RulebookSettings(
        version=1,
        rules=(
            RuleDefinition(
                rule_id="first_priority",
                name="First priority",
                section_id="first",
                priority=10,
                match_reason="First rule wins.",
                conditions=(NextCheckDueCondition(),),
            ),
            RuleDefinition(
                rule_id="second_priority",
                name="Second priority",
                section_id="second",
                priority=20,
                match_reason="Second rule should not win.",
                conditions=(NextCheckDueCondition(),),
            ),
        ),
    )

    result = evaluate_open_handoff(handoff, settings=settings, today=date(2026, 3, 9))

    assert result == RuleMatchResult(
        section_id="first",
        explanation="First rule wins.",
        matched_rule_id="first_priority",
        is_fallback=False,
    )


def test_rule_evaluation_skips_disabled_rules_and_keeps_stable_same_priority_order() -> None:
    """Disabled rules are ignored and same-priority rules keep declaration order."""
    handoff = Handoff(
        project_id=1,
        need_back="Due now",
        next_check=date(2026, 3, 9),
    )
    settings = RulebookSettings(
        version=1,
        rules=(
            RuleDefinition(
                rule_id="disabled",
                name="Disabled",
                section_id="disabled",
                priority=5,
                enabled=False,
                match_reason="Disabled rule.",
                conditions=(NextCheckDueCondition(),),
            ),
            RuleDefinition(
                rule_id="first_same_priority",
                name="First same priority",
                section_id="first_same_priority",
                priority=10,
                match_reason="First enabled same-priority rule wins.",
                conditions=(NextCheckDueCondition(),),
            ),
            RuleDefinition(
                rule_id="second_same_priority",
                name="Second same priority",
                section_id="second_same_priority",
                priority=10,
                match_reason="Second enabled same-priority rule loses.",
                conditions=(NextCheckDueCondition(),),
            ),
        ),
    )

    result = evaluate_open_handoff(handoff, settings=settings, today=date(2026, 3, 9))

    assert result.section_id == "first_same_priority"
    assert result.matched_rule_id == "first_same_priority"
    assert result.explanation == "First enabled same-priority rule wins."


def test_rule_evaluation_falls_back_for_unmatched_open_handoffs() -> None:
    """Open handoffs without a rule match fall back to the configured section."""
    handoff = Handoff(
        project_id=1,
        need_back="Future check",
        next_check=date(2026, 3, 12),
        deadline=date(2026, 3, 20),
    )

    result = evaluate_open_handoff(handoff, today=date(2026, 3, 9))

    assert result == RuleMatchResult(
        section_id=BuiltInSection.UPCOMING.value,
        explanation="No enabled rule matched; item falls back to Upcoming.",
        matched_rule_id=None,
        is_fallback=True,
    )


def test_rule_evaluation_rejects_concluded_handoffs() -> None:
    """Concluded handoffs remain outside the open-item rule engine."""
    handoff = Handoff(
        project_id=1,
        need_back="Done",
        next_check=date(2026, 3, 9),
    )
    handoff.check_ins = [
        CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 9),
            check_in_type=CheckInType.CONCLUDED,
        )
    ]

    with pytest.raises(ValueError, match="only supports open handoffs"):
        evaluate_open_handoff(handoff, today=date(2026, 3, 9))


def test_rule_evaluation_requires_first_match_wins_setting() -> None:
    """Evaluation rejects settings that disable first-match-wins semantics."""
    handoff = Handoff(
        project_id=1,
        need_back="Task",
    )
    settings = RulebookSettings(
        version=1,
        first_match_wins=False,
        rules=(
            RuleDefinition(
                rule_id="rule",
                name="Rule",
                section_id=BuiltInSection.ACTION_REQUIRED.value,
                priority=10,
                conditions=(NextCheckDueCondition(),),
            ),
        ),
    )

    with pytest.raises(ValueError, match="first_match_wins=True"):
        evaluate_open_handoff(handoff, settings=settings, today=date(2026, 3, 9))


def test_rule_evaluation_missing_next_check_toggle_and_default_explanation() -> None:
    """Missing next_check matches only when enabled and uses default explanation fallback."""
    handoff = Handoff(
        project_id=1,
        need_back="Unscheduled check-in",
        next_check=None,
    )
    no_missing_match = RulebookSettings(
        version=1,
        rules=(
            RuleDefinition(
                rule_id="due_only",
                name="Due only",
                section_id=BuiltInSection.ACTION_REQUIRED.value,
                priority=10,
                conditions=(NextCheckDueCondition(include_missing_next_check=False),),
            ),
        ),
    )
    missing_match = RulebookSettings(
        version=1,
        rules=(
            RuleDefinition(
                rule_id="needs_schedule",
                name="Needs schedule",
                section_id=BuiltInSection.ACTION_REQUIRED.value,
                priority=10,
                match_reason="   ",
                conditions=(NextCheckDueCondition(include_missing_next_check=True),),
            ),
        ),
    )

    fallback = evaluate_open_handoff(handoff, settings=no_missing_match, today=date(2026, 3, 9))
    assert fallback == RuleMatchResult(
        section_id=BuiltInSection.UPCOMING.value,
        explanation="No enabled rule matched; item falls back to Upcoming.",
        matched_rule_id=None,
        is_fallback=True,
    )

    result = evaluate_open_handoff(handoff, settings=missing_match, today=date(2026, 3, 9))
    assert result == RuleMatchResult(
        section_id=BuiltInSection.ACTION_REQUIRED.value,
        explanation="Matched Needs schedule.",
        matched_rule_id="needs_schedule",
        is_fallback=False,
    )


def test_default_rules_mirror_current_section_semantics(session, monkeypatch) -> None:
    """Default typed rules classify handoffs like current section queries."""
    _patch_session_context(monkeypatch, session)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    _patch_date(monkeypatch, FixedDate)
    near_days = 1
    today = FixedDate.today()

    project = Project(name="Parity")
    session.add(project)
    session.commit()
    session.refresh(project)

    risk = Handoff(
        project_id=project.id,
        need_back="Risk delayed near deadline",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 10),
    )
    action = Handoff(
        project_id=project.id,
        need_back="Action due now",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 20),
    )
    upcoming_future = Handoff(
        project_id=project.id,
        need_back="Upcoming future check",
        next_check=date(2026, 3, 13),
        deadline=date(2026, 3, 20),
    )
    upcoming_no_next_check = Handoff(
        project_id=project.id,
        need_back="Upcoming no next check",
        next_check=None,
        deadline=None,
    )
    near_deadline_on_track = Handoff(
        project_id=project.id,
        need_back="Near deadline but on track",
        next_check=date(2026, 3, 13),
        deadline=date(2026, 3, 10),
    )
    concluded = Handoff(
        project_id=project.id,
        need_back="Concluded item",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 20),
    )
    due_and_risk = Handoff(
        project_id=project.id,
        need_back="Due and risk",
        next_check=date(2026, 3, 9),
        deadline=date(2026, 3, 10),
    )
    session.add_all(
        [
            risk,
            action,
            upcoming_future,
            upcoming_no_next_check,
            near_deadline_on_track,
            concluded,
            due_and_risk,
        ]
    )
    session.commit()
    for handoff in (
        risk,
        action,
        upcoming_future,
        upcoming_no_next_check,
        near_deadline_on_track,
        concluded,
        due_and_risk,
    ):
        session.refresh(handoff)

    session.add_all(
        [
            CheckIn(
                handoff_id=risk.id,
                check_in_date=today,
                check_in_type=CheckInType.DELAYED,
            ),
            CheckIn(
                handoff_id=near_deadline_on_track.id,
                check_in_date=today,
                check_in_type=CheckInType.ON_TRACK,
            ),
            CheckIn(
                handoff_id=concluded.id,
                check_in_date=today,
                check_in_type=CheckInType.CONCLUDED,
            ),
            CheckIn(
                handoff_id=due_and_risk.id,
                check_in_date=today,
                check_in_type=CheckInType.DELAYED,
            ),
        ]
    )
    session.commit()

    settings = build_default_rulebook_settings(deadline_near_days=near_days)
    all_handoffs = data.query_handoffs(include_concluded=True)
    predicted: dict[str, set[str]] = {
        BuiltInSection.RISK.value: set(),
        BuiltInSection.ACTION_REQUIRED.value: set(),
        BuiltInSection.UPCOMING.value: set(),
        BuiltInSection.CONCLUDED.value: set(),
    }
    for handoff in all_handoffs:
        if not data.handoff_is_open(handoff):
            predicted[settings.concluded_section].add(handoff.need_back)
            continue
        match = evaluate_open_handoff(handoff, settings=settings, today=today)
        predicted[match.section_id].add(handoff.need_back)

    risk_names = {
        handoff.need_back for handoff in data.query_risk_handoffs(deadline_near_days=near_days)
    }
    action_names = {
        handoff.need_back for handoff in data.query_action_handoffs(deadline_near_days=near_days)
    }
    upcoming_names = {
        handoff.need_back for handoff in data.query_upcoming_handoffs(deadline_near_days=near_days)
    }
    concluded_names = {handoff.need_back for handoff in data.query_concluded_handoffs()}

    assert predicted[BuiltInSection.RISK.value] == risk_names
    assert predicted[BuiltInSection.ACTION_REQUIRED.value] == action_names
    assert predicted[BuiltInSection.UPCOMING.value] == upcoming_names
    assert predicted[BuiltInSection.CONCLUDED.value] == concluded_names
