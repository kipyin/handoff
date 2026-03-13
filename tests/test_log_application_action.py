"""Tests for log_application_action parameter and db path handling.

Tests that log_application_action can handle missing db gracefully, ensuring
bootstrap.logging remains usable without forcing a db import at call time.

Per template-readiness-refactoring.md P0 fix: log_application_action should
accept optional db_path parameter so bootstrap.logging never imports db directly.
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from handoff.bootstrap.logging import log_application_action


def test_log_application_action_falls_back_gracefully_without_db(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """log_application_action handles missing db import gracefully (best-effort)."""
    messages: list[str] = []

    def mock_logger_info(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr("handoff.bootstrap.logging.logger.info", mock_logger_info)

    # Mock the db module import to fail
    def mock_import(name, *args, **kwargs):
        if "handoff.db" in name:
            raise ImportError("handoff.db not available")
        return __import__(name, *args, **kwargs)

    monkeypatch.setattr("builtins.__import__", mock_import)

    log_application_action("test_action", source="cli")

    assert len(messages) == 1
    assert "action=test_action" in messages[0]
    assert "db_path=(unknown)" in messages[0]
    assert "source=cli" in messages[0]


def test_log_application_action_with_multiple_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """log_application_action formats multiple detail key-value pairs."""
    messages: list[str] = []

    def mock_logger_info(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr("handoff.bootstrap.logging.logger.info", mock_logger_info)

    # Mock db module to provide a test path
    mock_db_module = MagicMock()
    mock_db_module.get_db_path = MagicMock(return_value=Path("/test/path/db.db"))
    monkeypatch.setitem(sys.modules, "handoff.db", mock_db_module)

    log_application_action("data_export", format="json", rows=42, destination="backup.json")

    assert len(messages) == 1
    message = messages[0]
    assert "action=data_export" in message
    assert "db_path=/test/path/db.db" in message
    assert "format=json" in message
    assert "rows=42" in message
    assert "destination=backup.json" in message


def test_log_application_action_never_raises_on_db_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """log_application_action never raises, even if db lookup fails unexpectedly."""
    messages: list[str] = []

    def mock_logger_info(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr("handoff.bootstrap.logging.logger.info", mock_logger_info)

    # Mock db module that raises on get_db_path()
    mock_db_module = MagicMock()
    mock_db_module.get_db_path = MagicMock(side_effect=RuntimeError("database locked"))
    monkeypatch.setitem(sys.modules, "handoff.db", mock_db_module)

    # Should not raise
    log_application_action("app_update")

    assert len(messages) == 1
    assert "db_path=(unknown)" in messages[0]


def test_log_application_action_special_chars_in_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """log_application_action handles special characters in detail values."""
    messages: list[str] = []

    def mock_logger_info(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr("handoff.bootstrap.logging.logger.info", mock_logger_info)

    log_application_action("backup_export", path="/path/with spaces/file.zip", reason="manual")

    assert len(messages) == 1
    message = messages[0]
    assert "path=/path/with spaces/file.zip" in message
    assert "reason=manual" in message


def test_log_application_action_with_empty_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """log_application_action works with no detail kwargs."""
    messages: list[str] = []

    def mock_logger_info(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr("handoff.bootstrap.logging.logger.info", mock_logger_info)

    log_application_action("simple_action")

    assert len(messages) == 1
    message = messages[0]
    assert "application action=simple_action" in message
    assert "db_path=" in message


def test_log_application_action_message_format(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """log_application_action produces correctly formatted log line."""
    messages: list[str] = []

    def mock_logger_info(message: str) -> None:
        messages.append(message)

    monkeypatch.setattr("handoff.bootstrap.logging.logger.info", mock_logger_info)

    mock_db_module = MagicMock()
    mock_db_module.get_db_path = MagicMock(
        return_value=Path("/home/user/.local/share/handoff/handoff.db")
    )
    monkeypatch.setitem(sys.modules, "handoff.db", mock_db_module)

    log_application_action("app_update", version="2026.3.13", status="success")

    assert len(messages) == 1
    message = messages[0]
    assert message.startswith("application ")
    assert "action=app_update" in message
    assert "db_path=/home/user/.local/share/handoff/handoff.db" in message
    assert "version=2026.3.13" in message
    assert "status=success" in message
