"""Additional tests for pages/system_settings.py to improve coverage.

Covers: _render_send_log_section, _render_about_section, import happy path.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from handoff.models import CheckInType
from handoff.pages.system_settings import (
    _collect_edited_rule,
    _render_about_section,
    _render_data_export_section,
    _render_data_import_section,
    _render_rulebook_section,
    _render_send_log_section,
)
from handoff.rulebook import NextCheckDueCondition, RulebookSettings, RuleDefinition
from handoff.services.settings_service import DEADLINE_NEAR_DAYS_MAX


def _patch_streamlit(monkeypatch, **st_overrides) -> MagicMock:
    st_mock = MagicMock()
    st_mock.file_uploader.return_value = None
    st_mock.checkbox.return_value = False
    st_mock.button.return_value = False
    st_mock.download_button.return_value = None
    st_mock.session_state = {}
    st_mock.columns.return_value = [MagicMock(), MagicMock()]
    for k, v in st_overrides.items():
        setattr(st_mock, k, v)
    monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)
    return st_mock


class TestRenderSendLogSection:
    def test_no_log_files(self, monkeypatch, tmp_path: Path) -> None:
        """When no log files exist, shows 'No log files found' caption."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        monkeypatch.setattr("handoff.pages.system_settings._get_logs_dir", lambda: logs_dir)
        st_mock = _patch_streamlit(monkeypatch)

        _render_send_log_section()

        st_mock.caption.assert_any_call("No log files found.")

    def test_log_files_exist_creates_download(self, monkeypatch, tmp_path: Path) -> None:
        """When log files exist, a download button with zip is rendered."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "handoff.log").write_text("log content", encoding="utf-8")
        monkeypatch.setattr("handoff.pages.system_settings._get_logs_dir", lambda: logs_dir)
        st_mock = _patch_streamlit(monkeypatch)

        _render_send_log_section()

        st_mock.download_button.assert_called_once()
        call_kwargs = st_mock.download_button.call_args
        assert "log" in call_kwargs[1].get(
            "file_name", call_kwargs[0][0] if call_kwargs[0] else ""
        ).lower() or "log" in str(call_kwargs)


class TestRenderRulebookSection:
    def test_collect_edited_rule_clamps_and_normalizes_values(self, monkeypatch) -> None:
        """Collected rule values clamp and normalize edited widget state."""
        from handoff.rulebook import DeadlineWithinDaysCondition, LatestCheckInTypeIsCondition

        # Include all three editable condition primitives in one rule.
        # Order matters for widget key construction.
        rule = RuleDefinition(
            rule_id="rule_1",
            name="Rule 1",
            section_id="risk",
            priority=10,
            enabled=True,
            conditions=(
                DeadlineWithinDaysCondition(days=3),
                LatestCheckInTypeIsCondition(check_in_type=CheckInType.ON_TRACK),
                NextCheckDueCondition(include_missing_next_check=False),
            ),
        )

        st_mock = _patch_streamlit(monkeypatch)
        st_mock.session_state = {
            "settings_rule_2_cond_0_days": DEADLINE_NEAR_DAYS_MAX + 50,
            "settings_rule_2_cond_1_check_in_type": CheckInType.DELAYED.value,
            "settings_rule_2_cond_2_include_missing": 1,
        }

        updated = _collect_edited_rule(
            rule=rule,
            rule_idx=2,
            edited_enabled=False,
            edited_priority=77,
        )

        assert updated.enabled is False
        assert updated.priority == 77
        assert updated.conditions[0].days == DEADLINE_NEAR_DAYS_MAX
        assert updated.conditions[1].check_in_type == CheckInType.DELAYED
        assert updated.conditions[2].include_missing_next_check is True

    def test_preview_renders_rules_and_caption(self, monkeypatch) -> None:
        """Rulebook section displays active rules and caption."""
        from handoff.rulebook import build_default_rulebook_settings

        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: False
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_rulebook_settings",
            build_default_rulebook_settings,
        )

        _render_rulebook_section()

        st_mock.markdown.assert_any_call("### Open-item rules")
        expander_calls = [str(c) for c in st_mock.expander.call_args_list]
        assert any("Risk" in c for c in expander_calls)
        assert any("Action" in c for c in expander_calls)
        caption_calls = [str(c) for c in st_mock.caption.call_args_list]
        assert any("Open-item" in c or "First matching" in c for c in caption_calls)

    def test_reset_button_calls_reset_and_shows_success(self, monkeypatch) -> None:
        """When Reset button is clicked, reset_rulebook_settings is called and success shown."""
        from handoff.rulebook import build_default_rulebook_settings

        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: (
            key == "settings_rulebook_reset" if key else False
        )
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_rulebook_settings",
            build_default_rulebook_settings,
        )
        reset_called = []

        def mock_reset() -> None:
            reset_called.append(True)

        monkeypatch.setattr(
            "handoff.pages.system_settings.reset_rulebook_settings",
            mock_reset,
        )

        _render_rulebook_section()

        assert reset_called == [True]
        st_mock.success.assert_called_once()
        msg = st_mock.success.call_args[0][0].lower()
        assert "reset" in msg or "default" in msg

    def test_save_button_persists_valid_rulebook(self, monkeypatch) -> None:
        """When Save is clicked with valid form state, save_rulebook_settings is called."""
        from handoff.rulebook import build_default_rulebook_settings

        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: (
            key == "settings_rulebook_save" if key else False
        )
        session_state = {
            "settings_rule_0_enabled": True,
            "settings_rule_0_priority": 10,
            "settings_rule_0_cond_0_days": 2,
            "settings_rule_0_cond_1_check_in_type": "delayed",
            "settings_rule_1_enabled": True,
            "settings_rule_1_priority": 20,
            "settings_rule_1_cond_0_include_missing": False,
        }
        st_mock.session_state = session_state
        st_mock.checkbox.side_effect = lambda *a, **kw: session_state.get(
            kw.get("key"), kw.get("value", False)
        )
        st_mock.number_input.side_effect = lambda *a, **kw: session_state.get(
            kw.get("key"), kw.get("value", 0)
        )
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_rulebook_settings",
            build_default_rulebook_settings,
        )
        save_called: list = []

        def mock_save(settings) -> None:
            save_called.append(settings)

        monkeypatch.setattr(
            "handoff.pages.system_settings.save_rulebook_settings",
            mock_save,
        )

        _render_rulebook_section()

        assert len(save_called) == 1
        from handoff.rulebook import DeadlineWithinDaysCondition

        risk_rule = save_called[0].rules[0]
        deadline_cond = next(
            c for c in risk_rule.conditions if isinstance(c, DeadlineWithinDaysCondition)
        )
        assert deadline_cond.days == 2
        assert risk_rule.enabled is True
        assert risk_rule.priority == 10
        st_mock.success.assert_called_once()

    def test_save_invalid_config_shows_error(self, monkeypatch) -> None:
        """When form state produces invalid config, error is shown."""
        from handoff.rulebook import build_default_rulebook_settings

        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: (
            key == "settings_rulebook_save" if key else False
        )
        st_mock.session_state = {
            "settings_rule_0_enabled": True,
            "settings_rule_0_priority": 10,
            "settings_rule_0_cond_0_days": "not_a_number",
            "settings_rule_0_cond_1_check_in_type": "delayed",
            "settings_rule_1_enabled": True,
            "settings_rule_1_priority": 20,
            "settings_rule_1_cond_0_include_missing": False,
        }
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_rulebook_settings",
            build_default_rulebook_settings,
        )

        _render_rulebook_section()

        st_mock.error.assert_called_once()
        assert "Invalid" in st_mock.error.call_args[0][0]

    def test_reset_clears_session_state_and_reruns(self, monkeypatch) -> None:
        """After Reset, rulebook widget keys are cleared and rerun is triggered."""
        from handoff.rulebook import build_default_rulebook_settings

        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: (
            key == "settings_rulebook_reset" if key else False
        )
        session_state = {
            "settings_rule_0_enabled": False,
            "settings_rule_0_priority": 99,
        }
        st_mock.session_state = session_state
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_rulebook_settings",
            build_default_rulebook_settings,
        )
        reset_called = []

        def mock_reset() -> None:
            reset_called.append(True)

        monkeypatch.setattr(
            "handoff.pages.system_settings.reset_rulebook_settings",
            mock_reset,
        )

        _render_rulebook_section()

        assert reset_called == [True]
        assert "settings_rule_0_enabled" not in session_state
        assert "settings_rule_0_priority" not in session_state
        st_mock.rerun.assert_called_once()

    def test_caption_uses_rulebook_sections_and_fallback(self, monkeypatch) -> None:
        """Caption reflects configured sections and fallback, not hard-coded labels."""
        settings = RulebookSettings(
            version=1,
            rules=(
                RuleDefinition(
                    rule_id="rule_two",
                    name="Two",
                    section_id="waiting_for_input",
                    priority=20,
                    conditions=(NextCheckDueCondition(),),
                ),
                RuleDefinition(
                    rule_id="rule_one",
                    name="One",
                    section_id="needs_review",
                    priority=10,
                    conditions=(NextCheckDueCondition(),),
                ),
            ),
            open_items_fallback_section="manual_triage",
        )
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: False
        monkeypatch.setattr("handoff.pages.system_settings.get_rulebook_settings", lambda: settings)

        _render_rulebook_section()

        caption_calls = [call.args[0] for call in st_mock.caption.call_args_list]
        assert any("Needs Review" in text and "Waiting For Input" in text for text in caption_calls)
        assert any("fall back to Manual Triage" in text for text in caption_calls)

    def test_rule_preview_uses_priority_then_original_order(self, monkeypatch) -> None:
        """Rules with the same priority preserve their configured order in expanders."""
        settings = RulebookSettings(
            version=1,
            rules=(
                RuleDefinition(
                    rule_id="z_rule",
                    name="First Configured",
                    section_id="risk",
                    priority=10,
                    conditions=(NextCheckDueCondition(),),
                ),
                RuleDefinition(
                    rule_id="a_rule",
                    name="Second Configured",
                    section_id="action_required",
                    priority=10,
                    conditions=(NextCheckDueCondition(),),
                ),
                RuleDefinition(
                    rule_id="b_rule",
                    name="Lower Priority",
                    section_id="upcoming",
                    priority=30,
                    conditions=(NextCheckDueCondition(),),
                ),
            ),
        )
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: False
        monkeypatch.setattr("handoff.pages.system_settings.get_rulebook_settings", lambda: settings)

        _render_rulebook_section()

        expander_calls = [call.args[0] for call in st_mock.expander.call_args_list]
        assert expander_calls == [
            "**First Configured** — Risk",
            "**Second Configured** — Action Required",
            "**Lower Priority** — Upcoming",
        ]

    def test_save_uses_original_rule_indices_when_preview_is_reordered(self, monkeypatch) -> None:
        """Save maps form values by rule index, not by expander display order."""
        settings = RulebookSettings(
            version=1,
            rules=(
                RuleDefinition(
                    rule_id="stored_first",
                    name="Stored First",
                    section_id="risk",
                    priority=50,
                    enabled=True,
                    conditions=(NextCheckDueCondition(include_missing_next_check=False),),
                ),
                RuleDefinition(
                    rule_id="stored_second",
                    name="Stored Second",
                    section_id="action_required",
                    priority=10,
                    enabled=True,
                    conditions=(NextCheckDueCondition(include_missing_next_check=True),),
                ),
            ),
        )
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: (
            key == "settings_rulebook_save" if key else False
        )
        session_state = {
            "settings_rule_0_enabled": False,
            "settings_rule_0_priority": 99,
            "settings_rule_0_cond_0_include_missing": True,
            "settings_rule_1_enabled": True,
            "settings_rule_1_priority": 5,
            "settings_rule_1_cond_0_include_missing": False,
        }
        st_mock.session_state = session_state
        st_mock.checkbox.side_effect = lambda *a, **kw: session_state.get(
            kw.get("key"), kw.get("value", False)
        )
        st_mock.number_input.side_effect = lambda *a, **kw: session_state.get(
            kw.get("key"), kw.get("value", 0)
        )
        monkeypatch.setattr("handoff.pages.system_settings.get_rulebook_settings", lambda: settings)
        saved: list[RulebookSettings] = []
        monkeypatch.setattr(
            "handoff.pages.system_settings.save_rulebook_settings",
            lambda value: saved.append(value),
        )

        _render_rulebook_section()

        assert len(saved) == 1
        persisted = saved[0]
        assert [rule.rule_id for rule in persisted.rules] == ["stored_first", "stored_second"]
        assert persisted.rules[0].enabled is False
        assert persisted.rules[0].priority == 99
        assert persisted.rules[0].conditions[0].include_missing_next_check is True
        assert persisted.rules[1].enabled is True
        assert persisted.rules[1].priority == 5
        assert persisted.rules[1].conditions[0].include_missing_next_check is False

    def test_warns_when_rule_uses_unsupported_check_in_type(self, monkeypatch) -> None:
        """Unsupported saved check-in types trigger warning and default select index."""
        from handoff.rulebook import LatestCheckInTypeIsCondition

        settings = RulebookSettings(
            version=1,
            rules=(
                RuleDefinition(
                    rule_id="rule_with_concluded",
                    name="Concluded Rule",
                    section_id="risk",
                    priority=10,
                    conditions=(LatestCheckInTypeIsCondition(check_in_type=CheckInType.CONCLUDED),),
                ),
            ),
        )
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.button.side_effect = lambda label, key=None: False
        monkeypatch.setattr("handoff.pages.system_settings.get_rulebook_settings", lambda: settings)

        _render_rulebook_section()

        st_mock.warning.assert_called_once()
        warning_text = st_mock.warning.call_args[0][0]
        assert "unsupported check-in type" in warning_text.lower()
        assert st_mock.selectbox.call_args.kwargs["index"] == 0


class TestRenderAboutSection:
    def test_renders_version_and_environment(self, monkeypatch) -> None:
        """About section shows version and environment info."""
        st_mock = _patch_streamlit(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_readme_intro", lambda: "Handoff helps you."
        )

        _render_about_section()

        st_mock.markdown.assert_any_call("### About Handoff")
        st_mock.write.assert_called_once_with("Handoff helps you.")
        # Should show Python version caption
        caption_calls = [str(c) for c in st_mock.caption.call_args_list]
        assert any("Python" in c for c in caption_calls)


class TestRenderDataExportSection:
    def test_renders_download_buttons(self, monkeypatch) -> None:
        """Export section creates JSON and CSV download buttons."""
        st_mock = _patch_streamlit(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_export_payload",
            lambda: {"projects": [], "handoffs": [], "check_ins": []},
        )

        _render_data_export_section()

        assert st_mock.download_button.call_count == 2

    def test_csv_download_uses_handoff_rows(self, monkeypatch) -> None:
        """CSV export should include current handoff rows instead of legacy todos."""
        st_mock = _patch_streamlit(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_export_payload",
            lambda: {
                "projects": [],
                "handoffs": [
                    {
                        "id": 7,
                        "project_id": 3,
                        "need_back": "Launch checklist",
                        "pitchman": "Alex",
                        "next_check": "2026-03-12",
                        "deadline": "2026-03-14",
                        "notes": "Ship after QA",
                        "created_at": "2026-03-10T09:00:00",
                    }
                ],
                "check_ins": [],
            },
        )

        _render_data_export_section()

        csv_call = None
        for call in st_mock.download_button.call_args_list:
            if call.args and call.args[0] == "Download CSV (handoffs)":
                csv_call = call
                break
        assert csv_call is not None, "CSV download button call not found"
        assert csv_call.args[0] == "Download CSV (handoffs)"
        assert csv_call.kwargs["file_name"] == "handoff_handoffs.csv"
        assert "need_back" in csv_call.kwargs["data"]
        assert "Launch checklist" in csv_call.kwargs["data"]


class TestRenderDataImportSection:
    def test_valid_import_with_confirm_and_apply(self, monkeypatch) -> None:
        """Full import happy path: valid JSON, confirm checked, apply clicked."""
        payload = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "T",
                    "status": "handoff",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }
        uploaded = SimpleNamespace(getvalue=lambda: json.dumps(payload).encode("utf-8"))
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.file_uploader.return_value = uploaded
        st_mock.checkbox.return_value = True
        st_mock.button.return_value = True

        imported = {"called": False}

        def mock_import(p):
            imported["called"] = True

        monkeypatch.setattr("handoff.pages.system_settings.import_payload", mock_import)

        _render_data_import_section()

        assert imported["called"]
        st_mock.success.assert_called_once()

    def test_import_exception_shows_error(self, monkeypatch) -> None:
        """When import_payload raises, error message is shown."""
        payload = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "T",
                    "status": "handoff",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }
        uploaded = SimpleNamespace(getvalue=lambda: json.dumps(payload).encode("utf-8"))
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.file_uploader.return_value = uploaded
        st_mock.checkbox.return_value = True
        st_mock.button.return_value = True

        monkeypatch.setattr(
            "handoff.pages.system_settings.import_payload",
            lambda p: (_ for _ in ()).throw(RuntimeError("DB broke")),
        )

        _render_data_import_section()

        st_mock.error.assert_called_once()
        assert "DB broke" in st_mock.error.call_args[0][0]

    def test_no_upload_returns_early(self, monkeypatch) -> None:
        """When nothing is uploaded, no validation runs."""
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.file_uploader.return_value = None

        _render_data_import_section()

        st_mock.error.assert_not_called()
        st_mock.info.assert_not_called()
