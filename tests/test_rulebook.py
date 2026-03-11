"""Tests for typed rulebook contracts and built-in defaults."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta

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


def _latest_check_in(handoff: Handoff):
    """Return latest check-in by (check_in_date, created_at, id)."""
    if not handoff.check_ins:
        return None
    return max(
        handoff.check_ins,
        key=lambda check_in: (
            check_in.check_in_date,
            check_in.created_at,
            check_in.id or 0,
        ),
    )


def _is_open(handoff: Handoff) -> bool:
    """Mirror latest-check-in lifecycle semantics for open status."""
    latest = _latest_check_in(handoff)
    return latest is None or latest.check_in_type != CheckInType.CONCLUDED


def _matches_condition(condition, handoff: Handoff, *, today: date) -> bool:
    """Evaluate one condition against a handoff."""
    if isinstance(condition, DeadlineWithinDaysCondition):
        cutoff = today + timedelta(days=condition.days)
        return handoff.deadline is not None and handoff.deadline <= cutoff

    if isinstance(condition, LatestCheckInTypeIsCondition):
        latest = _latest_check_in(handoff)
        return latest is not None and latest.check_in_type == condition.check_in_type

    if isinstance(condition, NextCheckDueCondition):
        if handoff.next_check is None:
            return condition.include_missing_next_check
        return handoff.next_check <= today

    msg = f"Unhandled condition type: {type(condition)!r}"
    raise ValueError(msg)


def _classify_with_rulebook(
    handoffs: list[Handoff], settings: RulebookSettings, *, today: date
) -> dict[str, set[str]]:
    """Classify handoffs according to typed defaults and lifecycle fallback semantics."""
    grouped: dict[str, set[str]] = {
        BuiltInSection.RISK.value: set(),
        BuiltInSection.ACTION_REQUIRED.value: set(),
        BuiltInSection.UPCOMING.value: set(),
        BuiltInSection.CONCLUDED.value: set(),
    }

    ordered_rules = sorted(
        [rule for rule in settings.rules if rule.enabled],
        key=lambda rule: rule.priority,
    )
    for handoff in handoffs:
        if not _is_open(handoff):
            grouped[settings.concluded_section].add(handoff.need_back)
            continue

        matched = False
        for rule in ordered_rules:
            if all(
                _matches_condition(condition, handoff, today=today) for condition in rule.conditions
            ):
                grouped[rule.section_id].add(handoff.need_back)
                matched = True
                break
        if not matched:
            grouped[settings.open_items_fallback_section].add(handoff.need_back)

    return grouped


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
    try:
        RulebookSettings(
            version=1,
            rules=(settings.rules[0], duplicate_rule),
        )
    except ValueError as exc:
        assert "rule_ids must be unique" in str(exc)
    else:
        raise AssertionError("Expected duplicate rule ids to raise ValueError")


def test_rule_condition_and_match_result_validation() -> None:
    """Condition and match-result contracts reject invalid payloads."""
    try:
        DeadlineWithinDaysCondition(days=-1)
    except ValueError as exc:
        assert "days >= 0" in str(exc)
    else:
        raise AssertionError("Expected negative days to raise ValueError")

    fallback_result = RuleMatchResult(
        section_id=BuiltInSection.UPCOMING.value,
        explanation="No enabled rule matched; item falls back to Upcoming.",
        matched_rule_id=None,
        is_fallback=True,
    )
    assert fallback_result.is_fallback is True

    try:
        RuleMatchResult(
            section_id=BuiltInSection.RISK.value,
            explanation="Matched risk rule.",
            matched_rule_id=None,
            is_fallback=False,
        )
    except ValueError as exc:
        assert "require matched_rule_id" in str(exc)
    else:
        raise AssertionError("Expected non-fallback result without rule id to raise ValueError")


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
    predicted = _classify_with_rulebook(all_handoffs, settings, today=today)

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
