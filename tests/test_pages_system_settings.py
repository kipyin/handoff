"""Tests for System Settings page helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handoff.models import CheckInType
from handoff.pages.system_settings import (
    _collect_edited_rule,
    _format_condition,
    _handoffs_csv_text,
    _next_unique_custom_rule_id,
    _render_data_import_section,
    _slugify_section_id,
)
from handoff.rulebook import (
    DeadlineWithinDaysCondition,
    LatestCheckInTypeIsCondition,
    NextCheckDueCondition,
    RuleDefinition,
    RulebookSettings,
)


def _patch_streamlit(monkeypatch, uploaded) -> MagicMock:
    """Replace the Streamlit module in the System Settings page with a mock."""
    st_mock = MagicMock()
    st_mock.file_uploader.return_value = uploaded
    st_mock.checkbox.return_value = False
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)
    return st_mock


def test_render_data_import_section_rejects_non_utf8(monkeypatch) -> None:
    """Invalid byte content shows a clear UTF-8 error."""
    uploaded = SimpleNamespace(getvalue=lambda: b"\xff")
    st_mock = _patch_streamlit(monkeypatch, uploaded)

    _render_data_import_section()

    st_mock.error.assert_called_once_with(
        "Could not read the file as UTF-8 text. Please upload a JSON backup."
    )


def test_render_data_import_section_rejects_invalid_json(monkeypatch) -> None:
    """Malformed JSON shows a clean parse error."""
    uploaded = SimpleNamespace(getvalue=lambda: b"{not json")
    st_mock = _patch_streamlit(monkeypatch, uploaded)

    _render_data_import_section()

    st_mock.error.assert_called_once_with("Invalid JSON file. Please upload a Handoff JSON backup.")


def test_render_data_import_section_rejects_invalid_backup_shape(monkeypatch) -> None:
    """Unexpected JSON structure shows a clean validation error."""
    uploaded = SimpleNamespace(getvalue=lambda: json.dumps({"projects": []}).encode("utf-8"))
    st_mock = _patch_streamlit(monkeypatch, uploaded)

    _render_data_import_section()

    st_mock.error.assert_called_once_with(
        "Invalid backup file. Expected a Handoff backup with 'projects' and 'handoffs' lists."
    )


# Tests for _slugify_section_id
class TestSlugifySectionId:
    """Tests for section ID slugification logic."""

    def test_basic_section_name(self) -> None:
        """Normal section names are lowercased and spaces replaced with underscores."""
        assert _slugify_section_id("My Section") == "my_section"

    def test_hyphens_replaced_with_underscores(self) -> None:
        """Hyphens are converted to underscores."""
        assert _slugify_section_id("My-Section") == "my_section"

    def test_reserved_upcoming_is_prefixed(self) -> None:
        """The reserved 'upcoming' section ID is prefixed with 'custom_'."""
        assert _slugify_section_id("upcoming") == "custom_upcoming"

    def test_reserved_upcoming_case_insensitive(self) -> None:
        """Reserved check is case-insensitive."""
        assert _slugify_section_id("Upcoming") == "custom_upcoming"
        assert _slugify_section_id("UPCOMING") == "custom_upcoming"

    def test_empty_name_defaults(self) -> None:
        """Empty names default to 'custom_section'."""
        assert _slugify_section_id("") == "custom_section"
        assert _slugify_section_id("   ") == "custom_section"

    def test_whitespace_stripped(self) -> None:
        """Leading and trailing whitespace is stripped."""
        assert _slugify_section_id("  my section  ") == "my_section"

    def test_complex_names(self) -> None:
        """Complex names with mixed punctuation are handled."""
        assert _slugify_section_id("High Priority - Urgent") == "high_priority___urgent"


# Tests for _next_unique_custom_rule_id
class TestNextUniqueCustomRuleId:
    """Tests for unique rule ID generation."""

    def test_first_custom_rule_uses_base_id(self) -> None:
        """First custom rule for a section uses the base pattern."""
        settings = RulebookSettings(
            version=1,
            rules=(),
            first_match_wins=True,
            open_items_fallback_section="upcoming",
            concluded_section="concluded",
        )
        rule_id = _next_unique_custom_rule_id(settings, "blocked")
        assert rule_id == "custom_blocked"

    def test_collision_detection_increments(self) -> None:
        """Duplicate base ID increments to _2, _3, etc."""
        existing_rule = RuleDefinition(
            rule_id="custom_blocked",
            name="Blocked",
            section_id="blocked",
            priority=10,
            enabled=True,
            match_reason="",
            conditions=(LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),),
        )
        settings = RulebookSettings(
            version=1,
            rules=(existing_rule,),
            first_match_wins=True,
            open_items_fallback_section="upcoming",
            concluded_section="concluded",
        )
        rule_id = _next_unique_custom_rule_id(settings, "blocked")
        assert rule_id == "custom_blocked_2"

    def test_multiple_collisions_skip_to_available(self) -> None:
        """Multiple duplicates are skipped until an available ID is found."""
        rules = [
            RuleDefinition(
                rule_id="custom_blocked",
                name="Blocked",
                section_id="blocked",
                priority=10,
                enabled=True,
                match_reason="",
                conditions=(LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),),
            ),
            RuleDefinition(
                rule_id="custom_blocked_2",
                name="Blocked 2",
                section_id="blocked",
                priority=11,
                enabled=True,
                match_reason="",
                conditions=(LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),),
            ),
        ]
        settings = RulebookSettings(
            version=1,
            rules=tuple(rules),
            first_match_wins=True,
            open_items_fallback_section="upcoming",
            concluded_section="concluded",
        )
        rule_id = _next_unique_custom_rule_id(settings, "blocked")
        assert rule_id == "custom_blocked_3"


# Tests for _format_condition
class TestFormatCondition:
    """Tests for condition formatting."""

    def test_deadline_within_days_format(self) -> None:
        """DeadlineWithinDaysCondition formats with days."""
        condition = DeadlineWithinDaysCondition(days=3)
        assert _format_condition(condition) == "Deadline within 3 day(s)"

    def test_deadline_zero_days(self) -> None:
        """Zero days is still formatted correctly."""
        condition = DeadlineWithinDaysCondition(days=0)
        assert _format_condition(condition) == "Deadline within 0 day(s)"

    def test_latest_check_in_type_format(self) -> None:
        """LatestCheckInTypeIsCondition formats the check-in type."""
        condition = LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED)
        assert _format_condition(condition) == "Latest check-in is delayed"

    def test_latest_check_in_on_track_format(self) -> None:
        """ON_TRACK check-in type is formatted with underscores replaced."""
        condition = LatestCheckInTypeIsCondition(check_in_type=CheckInType.ON_TRACK)
        assert _format_condition(condition) == "Latest check-in is on track"

    def test_next_check_due_without_missing(self) -> None:
        """NextCheckDueCondition without missing next check is formatted correctly."""
        condition = NextCheckDueCondition(include_missing_next_check=False)
        assert _format_condition(condition) == "Next check due"

    def test_next_check_due_with_missing(self) -> None:
        """NextCheckDueCondition with missing next check includes that in format."""
        condition = NextCheckDueCondition(include_missing_next_check=True)
        assert _format_condition(condition) == "Next check due or missing"


# Tests for _handoffs_csv_text
class TestHandoffsCSVText:
    """Tests for CSV export formatting."""

    def test_empty_payload_returns_header_only(self) -> None:
        """Empty handoff list returns just the CSV header."""
        payload = {"handoffs": []}
        csv_text = _handoffs_csv_text(payload)
        assert "id,project_id,need_back,pitchman" in csv_text
        lines = csv_text.strip().split("\n")
        assert len(lines) == 1  # Header only

    def test_payload_without_handoffs_key(self) -> None:
        """Missing 'handoffs' key returns header only."""
        payload = {}
        csv_text = _handoffs_csv_text(payload)
        assert "id,project_id,need_back,pitchman" in csv_text

    def test_single_handoff_exports(self) -> None:
        """Single handoff is exported with all columns."""
        payload = {
            "handoffs": [
                {
                    "id": 1,
                    "project_id": 1,
                    "need_back": "Review PR",
                    "pitchman": "Alice",
                    "next_check": "2026-03-15",
                    "deadline": None,
                    "notes": "Test",
                    "created_at": "2026-03-13",
                }
            ]
        }
        csv_text = _handoffs_csv_text(payload)
        assert "1,1,Review PR,Alice" in csv_text

    def test_missing_columns_filled_with_none(self) -> None:
        """Missing columns in handoff data are filled with None."""
        payload = {
            "handoffs": [
                {
                    "id": 1,
                    "project_id": 1,
                    "need_back": "Review",
                    "pitchman": "Alice",
                }
            ]
        }
        csv_text = _handoffs_csv_text(payload)
        # Check that the CSV has all expected columns (some as None/empty)
        lines = csv_text.strip().split("\n")
        assert len(lines) == 2  # Header + one row


# Tests for _collect_edited_rule
class TestCollectEditedRule:
    """Tests for rule editing and condition collection."""

    def test_deadline_condition_within_bounds(self, monkeypatch) -> None:
        """Deadline condition days are clamped within bounds."""
        st_mock = MagicMock()
        st_mock.session_state = {
            "settings_rule_0_cond_0_days": "10",
        }
        monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)

        rule = RuleDefinition(
            rule_id="risk",
            name="Risk",
            section_id="risk",
            priority=1,
            enabled=True,
            match_reason="",
            conditions=(DeadlineWithinDaysCondition(days=3),),
        )
        edited = _collect_edited_rule(rule, 0, True, 1)

        assert isinstance(edited.conditions[0], DeadlineWithinDaysCondition)
        assert edited.conditions[0].days == 10
        assert edited.enabled is True
        assert edited.priority == 1

    def test_deadline_condition_exceeding_max_is_clamped(self, monkeypatch) -> None:
        """Deadline days exceeding max are clamped."""
        st_mock = MagicMock()
        st_mock.session_state = {
            "settings_rule_0_cond_0_days": "999",
        }
        monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)

        rule = RuleDefinition(
            rule_id="risk",
            name="Risk",
            section_id="risk",
            priority=1,
            enabled=True,
            match_reason="",
            conditions=(DeadlineWithinDaysCondition(days=3),),
        )
        edited = _collect_edited_rule(rule, 0, False, 5)

        assert edited.conditions[0].days <= 365  # Assuming DEADLINE_NEAR_DAYS_MAX
        assert edited.enabled is False
        assert edited.priority == 5

    def test_check_in_type_condition_preserved(self, monkeypatch) -> None:
        """LatestCheckInTypeIsCondition is preserved with selected value."""
        st_mock = MagicMock()
        st_mock.session_state = {
            "settings_rule_0_cond_0_check_in_type": "delayed",
        }
        monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)

        rule = RuleDefinition(
            rule_id="delayed",
            name="Delayed",
            section_id="delayed",
            priority=10,
            enabled=True,
            match_reason="",
            conditions=(LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),),
        )
        edited = _collect_edited_rule(rule, 0, True, 10)

        assert isinstance(edited.conditions[0], LatestCheckInTypeIsCondition)
        assert edited.conditions[0].check_in_type == CheckInType.DELAYED

    def test_next_check_due_condition_include_missing_toggled(self, monkeypatch) -> None:
        """NextCheckDueCondition include_missing_next_check can be toggled."""
        st_mock = MagicMock()
        st_mock.session_state = {
            "settings_rule_0_cond_0_include_missing": True,
        }
        monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)

        rule = RuleDefinition(
            rule_id="action",
            name="Action",
            section_id="action",
            priority=2,
            enabled=True,
            match_reason="",
            conditions=(NextCheckDueCondition(include_missing_next_check=False),),
        )
        edited = _collect_edited_rule(rule, 0, True, 2)

        assert isinstance(edited.conditions[0], NextCheckDueCondition)
        assert edited.conditions[0].include_missing_next_check is True

    def test_rule_metadata_preserved_during_edit(self, monkeypatch) -> None:
        """Rule ID, name, section_id, and match_reason are preserved."""
        st_mock = MagicMock()
        st_mock.session_state = {
            "settings_rule_0_cond_0_days": "5",
        }
        monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)

        rule = RuleDefinition(
            rule_id="custom_blocked",
            name="My Blocked Items",
            section_id="blocked",
            priority=10,
            enabled=True,
            match_reason="This is a custom reason.",
            conditions=(DeadlineWithinDaysCondition(days=3),),
        )
        edited = _collect_edited_rule(rule, 0, False, 15)

        assert edited.rule_id == "custom_blocked"
        assert edited.name == "My Blocked Items"
        assert edited.section_id == "blocked"
        assert edited.match_reason == "This is a custom reason."
