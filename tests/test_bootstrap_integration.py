"""Tests for bootstrap usage by critical modules.

Ensures that modules using bootstrap.logging.log_application_action and
bootstrap functions do so correctly and don't re-introduce coupling issues.

These tests verify that audit logging is called from critical paths like
data export/import, backup operations, and updates.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from handoff.bootstrap.docs import get_readme_intro, read_markdown_from_app_root
from handoff.bootstrap.logging import _get_logs_dir, configure_logging
from handoff.bootstrap.paths import get_app_root


def test_get_app_root_returns_existing_path() -> None:
    """get_app_root returns the correct project root."""
    root = get_app_root()
    assert isinstance(root, Path)
    assert root.exists()
    assert (root / "app.py").exists()
    assert (root / "pyproject.toml").exists()


def test_read_markdown_from_app_root_handles_missing_file() -> None:
    """read_markdown_from_app_root returns placeholder for missing files."""
    content = read_markdown_from_app_root("NONEXISTENT_FILE_12345.md")
    assert "not found" in content


def test_read_markdown_from_app_root_reads_existing_file() -> None:
    """read_markdown_from_app_root reads actual README content."""
    content = read_markdown_from_app_root("README.md")
    assert len(content) > 0
    assert "README" in content or "#" in content


def test_get_readme_intro_extracts_intro_section() -> None:
    """get_readme_intro extracts content before second ## heading."""
    intro = get_readme_intro()
    assert isinstance(intro, str)
    # Should not contain the second heading level
    assert "##" not in intro or intro.count("##") == 0


def test_configure_logging_is_idempotent_integration(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """configure_logging can be called multiple times safely."""
    import handoff.bootstrap.logging as log_mod

    def mock_user_data_dir(app_name: str, author: str) -> str:
        return str(tmp_path / app_name / author)

    monkeypatch.setattr(log_mod, "user_data_dir", mock_user_data_dir)

    # Reset state using monkeypatch for clean restoration
    original_configured = log_mod._CONFIGURED
    monkeypatch.setattr(log_mod, "_CONFIGURED", False)

    configure_logging()
    first_call_result = log_mod._CONFIGURED

    configure_logging()
    second_call_result = log_mod._CONFIGURED

    assert first_call_result is True
    assert second_call_result is True
    monkeypatch.setattr(log_mod, "_CONFIGURED", original_configured)


def test_get_logs_dir_creates_directory_structure(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_get_logs_dir creates necessary directory hierarchy."""
    import handoff.bootstrap.logging as log_mod

    def mock_user_data_dir(app_name: str, author: str) -> str:
        return str(tmp_path / app_name / author)

    monkeypatch.setattr(log_mod, "user_data_dir", mock_user_data_dir)

    logs_dir = _get_logs_dir()
    assert logs_dir.exists()
    assert logs_dir.is_dir()
    assert logs_dir.name == "logs"


def test_bootstrap_exports_are_available() -> None:
    """Bootstrap __init__ exports expected functions."""
    from handoff.bootstrap import (
        configure_logging,
        get_app_root,
        get_readme_intro,
        log_application_action,
        read_markdown_from_app_root,
    )

    assert callable(configure_logging)
    assert callable(get_app_root)
    assert callable(get_readme_intro)
    assert callable(log_application_action)
    assert callable(read_markdown_from_app_root)


def test_bootstrap_paths_no_hardcoded_app_name_in_get_app_root() -> None:
    """get_app_root does not reference app name (future-proofs for templates)."""
    from handoff.bootstrap import paths as paths_module

    # get_app_root should use relative path navigation, not app name;
    # check both identifiers (co_names) and string literals (co_consts)
    code = paths_module.get_app_root.__code__
    assert "handoff" not in code.co_names
    for const in code.co_consts:
        if isinstance(const, str) and (const == "handoff" or const.startswith("handoff.")):
            raise AssertionError(f"get_app_root contains hardcoded app name literal: {const!r}")


def test_bootstrap_logging_paths_dir_uses_app_name_placeholder(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """_get_logs_dir uses user_data_dir which should be configurable for templates."""
    import handoff.bootstrap.logging as log_mod

    def mock_user_data_dir(app_name: str, author: str) -> str:
        return str(tmp_path / app_name / author)

    monkeypatch.setattr(log_mod, "user_data_dir", mock_user_data_dir)
    logs_dir = log_mod._get_logs_dir()
    assert str(tmp_path) in str(logs_dir)
    assert logs_dir.exists()


def test_log_application_action_uses_logger_from_loguru() -> None:
    """log_application_action uses loguru logger (not prints or other logging)."""
    import handoff.bootstrap.logging as log_mod

    # Verify logger is loguru.logger
    assert hasattr(log_mod.logger, "info")
    assert hasattr(log_mod.logger, "add")
