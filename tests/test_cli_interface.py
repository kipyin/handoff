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


def _minimum_version(spec: str) -> tuple[int, ...]:
    """Return the declared >= lower bound as a comparable version tuple."""
    match = re.search(r">=\s*([0-9]+(?:\.[0-9]+)*)", spec)
    assert match is not None, f"expected a >= lower bound in {spec!r}"
    return tuple(int(part) for part in match.group(1).split("."))


def test_app_cli_runtime_dependencies_include_typer_and_rich() -> None:
    """Runtime deps must include CLI modules imported by handoff entrypoint."""
    specs = _runtime_dependency_specs()
    typer_spec = specs.get("typer")
    rich_spec = specs.get("rich")
    assert typer_spec is not None, "typer must be a runtime dependency"
    assert rich_spec is not None, "rich must be a runtime dependency"
    # Compare the declared floor, not an exact pin, so Dependabot lower-bound
    # bumps do not break this guarantee check.
    assert _minimum_version(typer_spec) >= (0, 27, 1), typer_spec
    assert _minimum_version(rich_spec) >= (15, 0, 0), rich_spec
