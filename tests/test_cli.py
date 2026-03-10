"""Tests for the developer CLI command wiring."""

from __future__ import annotations

from typer.testing import CliRunner

import scripts.cli as cli

RUNNER = CliRunner()


def _capture_run_cmd(monkeypatch):
    calls: list[list[str]] = []

    def fake_run_cmd(args, **_kwargs) -> None:
        calls.append(list(args))

    monkeypatch.setattr(cli, "run_cmd", fake_run_cmd)
    return calls


def test_lint_is_non_mutating_by_default(monkeypatch) -> None:
    """`handoff lint` should check without fixing unless requested."""
    calls = _capture_run_cmd(monkeypatch)

    cli.lint()

    assert calls == [["uv", "run", "ruff", "check", "."]]


def test_lint_accepts_fix_flag(monkeypatch) -> None:
    """`handoff lint --fix` should forward the fix flag to Ruff."""
    calls = _capture_run_cmd(monkeypatch)

    cli.lint(["--fix", "src"])

    assert calls == [["uv", "run", "ruff", "check", "--fix", "src"]]


def test_check_is_non_mutating_by_default(monkeypatch) -> None:
    """`handoff check` should run format/lint in check mode."""
    calls = _capture_run_cmd(monkeypatch)

    cli.check_command()

    assert calls == [
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "ruff", "check", "."],
    ]


def test_check_fix_applies_formatter_and_lint_fixes(monkeypatch) -> None:
    """`handoff check --fix` should run the mutating Ruff commands."""
    calls = _capture_run_cmd(monkeypatch)

    cli.check_command(["--fix", "src"])

    assert calls == [
        ["uv", "run", "ruff", "format", "src"],
        ["uv", "run", "ruff", "check", "--fix", "src"],
    ]


def test_ci_fix_only_applies_to_ruff_steps(monkeypatch) -> None:
    """`handoff ci --fix` should not leak the fix flag to pyright or pytest."""
    calls = _capture_run_cmd(monkeypatch)

    cli.ci(["--fix"])

    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
        ["uv", "run", "pyright", "src", "scripts"],
        ["uv", "run", "pytest", "."],
    ]


def test_check_cli_accepts_fix_flag(monkeypatch) -> None:
    """Typer should pass `--fix` through to the check command."""
    calls = _capture_run_cmd(monkeypatch)

    result = RUNNER.invoke(cli.app, ["check", "--fix"])

    assert result.exit_code == 0
    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
    ]


def test_ci_cli_accepts_fix_flag(monkeypatch) -> None:
    """Typer should pass `--fix` through to the ci command."""
    calls = _capture_run_cmd(monkeypatch)

    result = RUNNER.invoke(cli.app, ["ci", "--fix"])

    assert result.exit_code == 0
    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
        ["uv", "run", "pyright", "src", "scripts"],
        ["uv", "run", "pytest", "."],
    ]
