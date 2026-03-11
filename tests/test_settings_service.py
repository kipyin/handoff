"""Tests for settings service (export, import, deadline_near_days, rulebook)."""

from __future__ import annotations

from contextlib import contextmanager
from pathlib import Path

import pytest
from sqlmodel import select

from handoff.models import CheckInType, Handoff, Project
from handoff.rulebook import (
    BuiltInSection,
    DeadlineWithinDaysCondition,
    LatestCheckInTypeIsCondition,
    RulebookSettings,
    RuleDefinition,
    build_default_rulebook_settings,
)
from handoff.services import settings_service


def _patch_settings_path(monkeypatch: pytest.MonkeyPatch, path: Path) -> None:
    """Patch settings path so tests use a controlled file."""
    settings_path = path / "handoff_settings.json"

    def _get_path() -> Path:
        return settings_path

    monkeypatch.setattr(settings_service, "_get_settings_path", _get_path)


def _patch_session_context(monkeypatch, session) -> None:
    """Patch session_context in all data sub-modules to reuse the test session.

    Each sub-module imports session_context directly, so all five must be
    patched: activity (log_activity), handoffs (CRUD), io (import/export),
    projects (project CRUD), queries (queries).
    """
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


def test_get_export_payload_via_service(session, monkeypatch) -> None:
    """get_export_payload returns backup dict through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="P"))
    session.commit()
    payload = settings_service.get_export_payload()
    assert "projects" in payload
    assert "handoffs" in payload
    assert isinstance(payload["projects"], list)
    assert isinstance(payload["handoffs"], list)
    assert len(payload["projects"]) == 1
    assert payload["projects"][0]["name"] == "P"


def test_import_payload_via_service(session, monkeypatch) -> None:
    """import_payload replaces data through the service boundary (legacy format)."""
    _patch_session_context(monkeypatch, session)
    payload = {
        "projects": [
            {
                "id": 1,
                "name": "Imported",
                "created_at": "2026-03-01T00:00:00",
                "is_archived": False,
            },
        ],
        "todos": [
            {
                "id": 1,
                "project_id": 1,
                "name": "Imported todo",
                "status": "handoff",
                "next_check": "2026-04-01",
                "deadline": None,
                "helper": "Alice",
                "notes": "",
                "created_at": "2026-03-01T00:00:00",
                "completed_at": None,
                "is_archived": False,
            },
        ],
    }
    settings_service.import_payload(payload)
    projects = list(session.exec(select(Project)).all())
    handoffs = list(session.exec(select(Handoff)).all())
    assert len(projects) == 1
    assert projects[0].name == "Imported"
    assert len(handoffs) == 1
    assert handoffs[0].need_back == "Imported todo"


# --- deadline_near_days persistence ---


def test_get_deadline_near_days_missing_file_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When settings file does not exist, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    assert not (tmp_path / "handoff_settings.json").exists()
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_invalid_json_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When settings file has invalid JSON, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text("not valid json {", encoding="utf-8")
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_non_int_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When deadline_near_days is not an int, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text(
        '{"deadline_near_days": "seven"}', encoding="utf-8"
    )
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_out_of_range_returns_default(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When value is outside min/max, return default."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text('{"deadline_near_days": 99}', encoding="utf-8")
    assert settings_service.get_deadline_near_days() == 1


def test_get_deadline_near_days_valid_returns_value(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When value is valid, return it."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text('{"deadline_near_days": 3}', encoding="utf-8")
    assert settings_service.get_deadline_near_days() == 3


def test_set_deadline_near_days_clamps_and_persists(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """set_deadline_near_days clamps to min/max and persists."""
    _patch_settings_path(monkeypatch, tmp_path)

    settings_service.set_deadline_near_days(0)
    assert settings_service.get_deadline_near_days() == 1

    settings_service.set_deadline_near_days(99)
    assert settings_service.get_deadline_near_days() == 14

    settings_service.set_deadline_near_days(5)
    assert settings_service.get_deadline_near_days() == 5
    assert (tmp_path / "handoff_settings.json").read_text(encoding="utf-8") == (
        '{\n  "deadline_near_days": 5\n}'
    )


# --- rulebook persistence ---


def test_get_rulebook_settings_missing_file_returns_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When settings file does not exist, return built-in defaults."""
    _patch_settings_path(monkeypatch, tmp_path)
    assert not (tmp_path / "handoff_settings.json").exists()

    settings = settings_service.get_rulebook_settings()

    assert settings == build_default_rulebook_settings()


def test_get_rulebook_settings_invalid_json_returns_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When settings file has invalid JSON, return defaults."""
    _patch_settings_path(monkeypatch, tmp_path)
    (tmp_path / "handoff_settings.json").write_text("not valid json {", encoding="utf-8")

    settings = settings_service.get_rulebook_settings()

    assert settings == build_default_rulebook_settings()


def test_get_rulebook_settings_invalid_rulebook_payload_returns_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When rulebook key is invalid or malformed, return defaults."""
    _patch_settings_path(monkeypatch, tmp_path)

    (tmp_path / "handoff_settings.json").write_text('{"rulebook": "not a dict"}', encoding="utf-8")
    settings = settings_service.get_rulebook_settings()
    assert settings == build_default_rulebook_settings()

    (tmp_path / "handoff_settings.json").write_text(
        '{"rulebook": {"version": 1, "rules": "not a list"}}', encoding="utf-8"
    )
    settings = settings_service.get_rulebook_settings()
    assert settings == build_default_rulebook_settings()

    (tmp_path / "handoff_settings.json").write_text(
        '{"rulebook": {"version": 1, "rules": []}}', encoding="utf-8"
    )
    settings = settings_service.get_rulebook_settings()
    assert settings == build_default_rulebook_settings()


def test_get_rulebook_settings_valid_returns_persisted(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """When rulebook is valid, return the persisted settings."""
    _patch_settings_path(monkeypatch, tmp_path)
    custom = RulebookSettings(
        version=1,
        rules=(
            RuleDefinition(
                rule_id="custom_risk",
                name="Custom Risk",
                section_id=BuiltInSection.RISK.value,
                priority=5,
                match_reason="Custom rule.",
                conditions=(
                    DeadlineWithinDaysCondition(days=2),
                    LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),
                ),
            ),
            build_default_rulebook_settings().rules[1],
        ),
    )
    settings_service.save_rulebook_settings(custom)

    loaded = settings_service.get_rulebook_settings()

    assert loaded.rules[0].rule_id == "custom_risk"
    assert loaded.rules[0].name == "Custom Risk"


def test_save_rulebook_settings_persists_and_preserves_other_keys(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """save_rulebook_settings persists the rulebook and does not overwrite deadline_near_days."""
    _patch_settings_path(monkeypatch, tmp_path)
    settings_service.set_deadline_near_days(5)

    custom = build_default_rulebook_settings(deadline_near_days=3)
    settings_service.save_rulebook_settings(custom)

    assert settings_service.get_deadline_near_days() == 5
    loaded = settings_service.get_rulebook_settings()
    assert loaded.version == custom.version
    assert len(loaded.rules) == len(build_default_rulebook_settings().rules)

    raw = (tmp_path / "handoff_settings.json").read_text(encoding="utf-8")
    assert "deadline_near_days" in raw
    assert "rulebook" in raw


def test_reset_rulebook_settings_saves_defaults(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """reset_rulebook_settings writes built-in defaults to disk."""
    _patch_settings_path(monkeypatch, tmp_path)
    custom = RulebookSettings(
        version=1,
        rules=(
            RuleDefinition(
                rule_id="custom_risk",
                name="Custom Risk",
                section_id=BuiltInSection.RISK.value,
                priority=5,
                match_reason="Custom.",
                conditions=(
                    DeadlineWithinDaysCondition(days=1),
                    LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),
                ),
            ),
            build_default_rulebook_settings().rules[1],
        ),
    )
    settings_service.save_rulebook_settings(custom)
    assert settings_service.get_rulebook_settings().rules[0].rule_id == "custom_risk"

    settings_service.reset_rulebook_settings()

    loaded = settings_service.get_rulebook_settings()
    assert loaded.rules[0].rule_id == "default_risk_deadline_near_and_delayed"
