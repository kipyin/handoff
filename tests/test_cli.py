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


def test_sizecheck_cli_uses_defaults_when_no_paths(monkeypatch) -> None:
    """`handoff sizecheck` should default to src with default thresholds."""
    seen: dict[str, object] = {}

    def fake_run_sizecheck(paths, *, default_path: str, max_bytes: int, warn_threshold: float):
        seen["paths"] = paths
        seen["default_path"] = default_path
        seen["max_bytes"] = max_bytes
        seen["warn_threshold"] = warn_threshold
        return True, [], []

    monkeypatch.setattr(cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(cli.app, ["sizecheck"])

    assert result.exit_code == 0
    assert seen == {
        "paths": None,
        "default_path": "src",
        "max_bytes": 32 * 1024,
        "warn_threshold": 0.9,
    }
    assert "All files under 32,768 bytes." in result.stdout


def test_sizecheck_cli_surfaces_warnings_and_fails_on_violations(monkeypatch) -> None:
    """`handoff sizecheck` should print warnings and exit non-zero on violations."""

    def fake_run_sizecheck(paths, *, default_path: str, max_bytes: int, warn_threshold: float):
        assert paths == ["src/handoff", "scripts"]
        assert default_path == "src"
        assert max_bytes == 100
        assert warn_threshold == 0.8
        return (
            False,
            ["src/handoff/data.py: 1,234 bytes (max 100)"],
            ["src/handoff/io.py: 80 bytes (80% of limit)"],
        )

    monkeypatch.setattr(cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(
        cli.app,
        [
            "sizecheck",
            "--max-bytes",
            "100",
            "--warn-threshold",
            "0.8",
            "src/handoff",
            "scripts",
        ],
    )

    assert result.exit_code == 1
    assert "warning: src/handoff/io.py: 80 bytes (80% of limit)" in result.stdout
    assert "The following files exceed the limit (100 bytes):" in result.stdout
    assert "src/handoff/data.py: 1,234 bytes (max 100)" in result.stdout


def test_sizecheck_cli_forwards_options_and_paths(monkeypatch) -> None:
    """`handoff sizecheck` should pass options/paths through to run_sizecheck."""
    captured: dict[str, object] = {}

    def fake_run_sizecheck(paths, *, default_path, max_bytes, warn_threshold):
        captured["paths"] = paths
        captured["default_path"] = default_path
        captured["max_bytes"] = max_bytes
        captured["warn_threshold"] = warn_threshold
        return True, [], ["src/example.py: 9 bytes (90% of limit)"]

    monkeypatch.setattr(cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(
        cli.app,
        [
            "sizecheck",
            "--path",
            "custom-src",
            "--max-bytes",
            "10",
            "--warn-threshold",
            "0.9",
            "scripts/cli.py",
        ],
    )

    assert result.exit_code == 0
    assert captured == {
        "paths": ["scripts/cli.py"],
        "default_path": "custom-src",
        "max_bytes": 10,
        "warn_threshold": 0.9,
    }
    assert "warning: src/example.py: 9 bytes (90% of limit)" in result.stdout
    assert "All files under 10 bytes." in result.stdout


def test_sizecheck_cli_exits_nonzero_on_violations(monkeypatch) -> None:
    """`handoff sizecheck` should fail fast when any file exceeds the limit."""

    def fake_run_sizecheck(_paths, *, default_path, max_bytes, warn_threshold):
        del default_path, warn_threshold
        return False, [f"src/too_big.py: {max_bytes + 1} bytes (max {max_bytes})"], []

    monkeypatch.setattr(cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(cli.app, ["sizecheck", "--max-bytes", "10"])

    assert result.exit_code == 1
    assert "The following files exceed the limit (10 bytes):" in result.stdout
    assert "src/too_big.py: 11 bytes (max 10)" in result.stdout


def test_ci_runs_sizecheck_with_fixed_src_settings(monkeypatch) -> None:
    """`handoff ci` should always run sizecheck against src/ only."""
    calls = _capture_run_cmd(monkeypatch)
    sizecheck_calls: list[dict[str, object]] = []

    def fake_sizecheck(**kwargs) -> None:
        sizecheck_calls.append(kwargs)

    monkeypatch.setattr(cli, "sizecheck", fake_sizecheck)

    cli.ci(["--fix"])

    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
        ["uv", "run", "pyright", "src", "scripts"],
        ["uv", "run", "pytest", "."],
    ]
    assert sizecheck_calls == [
        {
            "extra_args": [],
            "path": "src",
            "max_bytes": 32 * 1024,
            "warn_threshold": 0.9,
        }
    ]


def test_cli_command_stub_prints_not_implemented_message() -> None:
    """`handoff cli` should print a clear "not implemented" message to stderr."""
    result = RUNNER.invoke(cli.app, ["cli"])

    assert result.exit_code == 1
    assert "handoff cli is not implemented yet" in result.stdout
    assert "future interactive CLI interface" in result.stdout


def test_cli_command_stub_exits_with_code_1() -> None:
    """`handoff cli` should exit with non-zero code to signal failure."""
    result = RUNNER.invoke(cli.app, ["cli"])

    assert result.exit_code == 1


def test_cli_command_stub_does_not_accept_subcommands() -> None:
    """`handoff cli` should not accept arbitrary subcommands (reserved for future)."""
    result = RUNNER.invoke(cli.app, ["cli", "subcommand"])

    assert result.exit_code != 0
