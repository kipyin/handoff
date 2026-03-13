"""Tests for the logging configuration module."""

from __future__ import annotations

from pathlib import Path

import pytest

from handoff.bootstrap.logging import _get_logs_dir


def test_get_logs_dir_returns_path_and_creates_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_get_logs_dir returns a Path under the data dir and creates it."""
    monkeypatch.setattr(
        "handoff.bootstrap.logging.user_data_dir", lambda app, author: str(tmp_path)
    )
    logs_dir = _get_logs_dir()
    assert isinstance(logs_dir, Path)
    assert logs_dir.exists()
    assert logs_dir == tmp_path / "logs"
    assert logs_dir.name == "logs"


def test_configure_logging_writes_sinks(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """configure_logging sets up stdout + file sinks and marks _CONFIGURED."""
    import handoff.bootstrap.logging as log_mod

    monkeypatch.setattr(
        "handoff.bootstrap.logging.user_data_dir", lambda app, author: str(tmp_path)
    )
    # Force fresh configuration regardless of previous test runs.
    monkeypatch.setattr(log_mod, "_CONFIGURED", False)

    log_mod.configure_logging()

    assert log_mod._CONFIGURED is True
    # Log file should be created inside logs/
    log_file = tmp_path / "logs" / "handoff.log"
    assert log_file.exists()


def test_configure_logging_is_idempotent(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Calling configure_logging() twice does not raise and honours _CONFIGURED guard."""
    import handoff.bootstrap.logging as log_mod

    monkeypatch.setattr(
        "handoff.bootstrap.logging.user_data_dir", lambda app, author: str(tmp_path)
    )
    monkeypatch.setattr(log_mod, "_CONFIGURED", False)

    log_mod.configure_logging()
    # Second call should be a no-op (returns early, no exception).
    log_mod.configure_logging()

    assert log_mod._CONFIGURED is True


def test_log_application_action_includes_db_path_and_details(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import handoff.bootstrap.logging as log_mod
    import handoff.db as db_mod

    db_path = Path("/tmp/handoff.db")
    monkeypatch.setattr(db_mod, "get_db_path", lambda: db_path)
    messages: list[str] = []
    monkeypatch.setattr(log_mod.logger, "info", lambda message: messages.append(message))

    log_mod.log_application_action("data_export", format="json")

    assert len(messages) == 1
    message = messages[0]
    assert message.startswith("application action=data_export")
    assert f"db_path={db_path}" in message
    assert "format=json" in message


def test_log_application_action_falls_back_to_unknown_db_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import handoff.bootstrap.logging as log_mod
    import handoff.db as db_mod

    def _raise() -> Path:
        raise RuntimeError("boom")

    monkeypatch.setattr(db_mod, "get_db_path", _raise)
    messages: list[str] = []
    monkeypatch.setattr(log_mod.logger, "info", lambda message: messages.append(message))

    log_mod.log_application_action("app_update")

    assert len(messages) == 1
    assert "action=app_update" in messages[0]
    assert "db_path=(unknown)" in messages[0]
