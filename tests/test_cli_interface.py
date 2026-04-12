"""Regression tests for the app CLI interface."""

from __future__ import annotations

import importlib
import re
import tomllib
from pathlib import Path

from typer.testing import CliRunner

import handoff.interfaces.cli as cli_module

RUNNER = CliRunner()
ROOT = Path(__file__).resolve().parents[1]
PYPROJECT = ROOT / "pyproject.toml"


def _runtime_dependency_specs() -> dict[str, str]:
    """Map normalized package name to full requirement line from [project].dependencies."""
    with PYPROJECT.open("rb") as fp:
        data = tomllib.load(fp)
    deps = data["project"].get("dependencies", [])
    specs: dict[str, str] = {}
    for spec in deps:
        match = re.match(r"^([A-Za-z0-9_.-]+)", spec)
        if match:
            specs[match.group(1).lower()] = spec.strip()
    return specs


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


def test_app_cli_runtime_dependencies_include_typer_and_rich() -> None:
    """Runtime deps must include CLI modules imported by handoff entrypoint."""
    specs = _runtime_dependency_specs()
    typer_spec = specs.get("typer")
    rich_spec = specs.get("rich")
    assert typer_spec is not None, "typer must be a runtime dependency"
    assert rich_spec is not None, "rich must be a runtime dependency"
    assert re.search(r">=\s*0\.12\.3", typer_spec), typer_spec
    assert re.search(r">=\s*13\.7\.0", rich_spec), rich_spec
