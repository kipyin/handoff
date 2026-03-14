"""Regression tests for the app CLI interface."""

from __future__ import annotations

import importlib

from typer.testing import CliRunner

import handoff.interfaces.cli as cli_module

RUNNER = CliRunner()


def test_cli_module_exports_main_and_app() -> None:
    """The CLI interface module should export main and app."""
    assert hasattr(cli_module, "main")
    assert hasattr(cli_module, "app")
    assert "main" in cli_module.__all__
    assert "app" in cli_module.__all__


def test_cli_interface_is_importable() -> None:
    """The CLI interface module should be importable."""
    imported = importlib.import_module("handoff.interfaces.cli")
    assert hasattr(imported, "main")
    assert hasattr(imported, "app")


def test_cli_command_stub_via_invoke() -> None:
    """The `handoff cli` subcommand should print not-implemented message and exit 1."""
    result = RUNNER.invoke(cli_module.app, ["cli"])
    assert result.exit_code == 1
    assert "not implemented" in result.stdout.lower()
