"""Tests for the developer and app CLI command wiring."""

from __future__ import annotations

import sqlite3
import subprocess
import sys
from pathlib import Path

from typer.testing import CliRunner

import handoff.interfaces.cli as app_cli
import scripts
import scripts.dev_cli
import scripts.seed_demo

RUNNER = CliRunner()
_COUNTABLE_TABLES = {"project", "handoff", "check_in"}


def _capture_run_cmd(monkeypatch, module=None):
    if module is None:
        module = scripts.dev_cli
    calls: list[list[str]] = []

    def fake_run_cmd(args, **_kwargs) -> None:
        calls.append(list(args))

    monkeypatch.setattr(module, "run_cmd", fake_run_cmd)
    return calls


def _capture_launch_streamlit(monkeypatch) -> list[dict[str, object]]:
    """Capture _launch_streamlit calls from handoff.interfaces.cli."""
    calls: list[dict[str, object]] = []

    def fake_launch(extra_args: list[str], env: dict[str, str] | None = None) -> None:
        cmd = [sys.executable, "-m", "handoff", *extra_args]
        calls.append({"args": cmd, "cwd": app_cli.ROOT, "env": env})

    monkeypatch.setattr(app_cli, "_launch_streamlit", fake_launch)
    return calls


def _count_rows(db_path: Path, table: str) -> int:
    assert table in _COUNTABLE_TABLES
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def test_lint_is_non_mutating_by_default(monkeypatch) -> None:
    """`handoff-dev lint` should check without fixing unless requested."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    scripts.dev_cli.lint()

    assert calls == [["uv", "run", "ruff", "check", "."]]


def test_lint_accepts_fix_flag(monkeypatch) -> None:
    """`handoff-dev lint --fix` should forward the fix flag to Ruff."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    scripts.dev_cli.lint(["--fix", "src"])

    assert calls == [["uv", "run", "ruff", "check", "--fix", "src"]]


def test_check_is_non_mutating_by_default(monkeypatch) -> None:
    """`handoff-dev check` should run format/lint in check mode."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    scripts.dev_cli.check_command()

    assert calls == [
        ["uv", "run", "ruff", "format", "--check", "."],
        ["uv", "run", "ruff", "check", "."],
    ]


def test_check_fix_applies_formatter_and_lint_fixes(monkeypatch) -> None:
    """`handoff-dev check --fix` should run the mutating Ruff commands."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    scripts.dev_cli.check_command(["--fix", "src"])

    assert calls == [
        ["uv", "run", "ruff", "format", "src"],
        ["uv", "run", "ruff", "check", "--fix", "src"],
    ]


def test_ci_fix_only_applies_to_ruff_steps(monkeypatch) -> None:
    """`handoff-dev ci --fix` should not leak the fix flag to pyright or pytest."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    scripts.dev_cli.ci(["--fix"])

    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
        ["uv", "run", "pyright", "src", "scripts"],
        ["uv", "run", "pytest", "."],
    ]


def test_check_cli_accepts_fix_flag(monkeypatch) -> None:
    """Typer should pass `--fix` through to the check command."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    result = RUNNER.invoke(scripts.dev_cli.app, ["check", "--fix"])

    assert result.exit_code == 0
    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
    ]


def test_ci_cli_accepts_fix_flag(monkeypatch) -> None:
    """Typer should pass `--fix` through to the ci command."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)

    result = RUNNER.invoke(scripts.dev_cli.app, ["ci", "--fix"])

    assert result.exit_code == 0
    assert calls == [
        ["uv", "run", "ruff", "format", "."],
        ["uv", "run", "ruff", "check", "--fix", "."],
        ["uv", "run", "pyright", "src", "scripts"],
        ["uv", "run", "pytest", "."],
    ]


def test_sizecheck_cli_uses_defaults_when_no_paths(monkeypatch) -> None:
    """`handoff-dev sizecheck` should default to src with default thresholds."""
    seen: dict[str, object] = {}

    def fake_run_sizecheck(paths, *, default_path: str, max_bytes: int, warn_threshold: float):
        seen["paths"] = paths
        seen["default_path"] = default_path
        seen["max_bytes"] = max_bytes
        seen["warn_threshold"] = warn_threshold
        return True, [], []

    monkeypatch.setattr(scripts.dev_cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(scripts.dev_cli.app, ["sizecheck"])

    assert result.exit_code == 0
    assert seen == {
        "paths": None,
        "default_path": "src",
        "max_bytes": 32 * 1024,
        "warn_threshold": 0.9,
    }
    assert "All files under 32,768 bytes." in result.stdout


def test_sizecheck_cli_surfaces_warnings_and_fails_on_violations(monkeypatch) -> None:
    """`handoff-dev sizecheck` should print warnings and exit non-zero on violations."""

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

    monkeypatch.setattr(scripts.dev_cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(
        scripts.dev_cli.app,
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
    """`handoff-dev sizecheck` should pass options/paths through to run_sizecheck."""
    captured: dict[str, object] = {}

    def fake_run_sizecheck(paths, *, default_path, max_bytes, warn_threshold):
        captured["paths"] = paths
        captured["default_path"] = default_path
        captured["max_bytes"] = max_bytes
        captured["warn_threshold"] = warn_threshold
        return True, [], ["src/example.py: 9 bytes (90% of limit)"]

    monkeypatch.setattr(scripts.dev_cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(
        scripts.dev_cli.app,
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
    """`handoff-dev sizecheck` should fail fast when any file exceeds the limit."""

    def fake_run_sizecheck(_paths, *, default_path, max_bytes, warn_threshold):
        del default_path, warn_threshold
        return False, [f"src/too_big.py: {max_bytes + 1} bytes (max {max_bytes})"], []

    monkeypatch.setattr(scripts.dev_cli.sizecheck_module, "run_sizecheck", fake_run_sizecheck)

    result = RUNNER.invoke(scripts.dev_cli.app, ["sizecheck", "--max-bytes", "10"])

    assert result.exit_code == 1
    assert "The following files exceed the limit (10 bytes):" in result.stdout
    assert "src/too_big.py: 11 bytes (max 10)" in result.stdout


def test_ci_runs_sizecheck_with_fixed_src_settings(monkeypatch) -> None:
    """`handoff-dev ci` should always run sizecheck against src/ only."""
    calls = _capture_run_cmd(monkeypatch, scripts.dev_cli)
    sizecheck_calls: list[dict[str, object]] = []

    def fake_sizecheck(**kwargs) -> None:
        sizecheck_calls.append(kwargs)

    monkeypatch.setattr(scripts.dev_cli, "sizecheck", fake_sizecheck)

    scripts.dev_cli.ci(["--fix"])

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
    """`handoff cli` should print a clear "not implemented" message to stdout."""
    result = RUNNER.invoke(app_cli.app, ["cli"])

    assert result.exit_code == 1
    assert "handoff cli is not implemented yet" in result.stdout
    assert "future interactive CLI interface" in result.stdout


def test_cli_command_stub_exits_with_code_1() -> None:
    """`handoff cli` should exit with non-zero code to signal failure."""
    result = RUNNER.invoke(app_cli.app, ["cli"])

    assert result.exit_code == 1


def test_seed_demo_cli_seeds_database_at_requested_path(tmp_path: Path) -> None:
    """`handoff-dev seed-demo` should create and seed a DB at the provided path."""
    db_path = tmp_path / "demo.db"

    result = RUNNER.invoke(scripts.dev_cli.app, ["seed-demo", "--db-path", str(db_path)])

    assert result.exit_code == 0
    assert db_path.exists()
    assert _count_rows(db_path, "project") >= 3
    assert _count_rows(db_path, "handoff") >= 9
    assert "Demo database ready at" in result.stdout


def test_run_db_path_sets_env_for_subprocess(tmp_path: Path, monkeypatch) -> None:
    """`handoff run --db-path PATH` should pass HANDOFF_DB_PATH without requiring --demo."""
    db_path = tmp_path / "custom.db"
    db_path.touch()
    calls = _capture_launch_streamlit(monkeypatch)

    result = RUNNER.invoke(
        app_cli.app,
        ["run", "--db-path", str(db_path), "--", "--server.port", "9999"],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    env = calls[0]["env"]
    assert isinstance(env, dict)
    assert env["HANDOFF_DB_PATH"] == str(db_path.resolve())


def test_run_demo_seeds_db_and_sets_env_for_subprocess(tmp_path: Path, monkeypatch) -> None:
    """`handoff run --demo` should seed an empty DB and pass HANDOFF_DB_PATH through."""
    db_path = tmp_path / "demo.db"
    calls = _capture_launch_streamlit(monkeypatch)

    result = RUNNER.invoke(
        app_cli.app,
        [
            "run",
            "--demo",
            "--db-path",
            str(db_path),
            "--",
            "--server.port",
            "9999",
        ],
    )

    assert result.exit_code == 0
    assert db_path.exists()
    assert _count_rows(db_path, "project") >= 3
    assert len(calls) == 1
    assert calls[0]["args"] == [sys.executable, "-m", "handoff", "--server.port", "9999"]
    assert calls[0]["cwd"] == app_cli.ROOT
    env = calls[0]["env"]
    assert isinstance(env, dict)
    assert env["HANDOFF_DB_PATH"] == str(db_path.resolve())


def test_cli_command_stub_does_not_accept_subcommands() -> None:
    """`handoff cli` should not accept arbitrary subcommands (reserved for future)."""
    result = RUNNER.invoke(app_cli.app, ["cli", "subcommand"])

    assert result.exit_code != 0


def test_resolve_demo_db_path_uses_provided_path() -> None:
    """_resolve_demo_db_path should return expanded/resolved provided path."""
    # Test with absolute path
    result = app_cli._resolve_demo_db_path("/tmp/test.db")
    assert result == Path("/tmp/test.db").resolve()

    # Test with relative path
    result = app_cli._resolve_demo_db_path("test.db")
    assert result == Path("test.db").resolve()


def test_resolve_demo_db_path_with_tilde_expansion() -> None:
    """_resolve_demo_db_path should expand ~ in paths."""
    result = app_cli._resolve_demo_db_path("~/test.db")
    assert "~" not in str(result)
    assert result == Path("~/test.db").expanduser().resolve()


def test_resolve_demo_db_path_uses_default_when_none() -> None:
    """_resolve_demo_db_path should use get_demo_db_path() when no path provided."""
    result = app_cli._resolve_demo_db_path(None)
    expected = app_cli.get_demo_db_path()
    assert result == expected


def test_db_has_projects_returns_false_when_db_not_exists(tmp_path: Path) -> None:
    """_db_has_projects should return False when DB file does not exist."""
    missing_db = tmp_path / "nonexistent.db"
    assert app_cli._db_has_projects(missing_db) is False


def test_db_has_projects_returns_false_when_table_missing(tmp_path: Path) -> None:
    """_db_has_projects should return False when project table doesn't exist."""
    db_path = tmp_path / "empty.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE other_table (id INTEGER)")
        conn.commit()

    assert app_cli._db_has_projects(db_path) is False


def test_db_has_projects_returns_false_when_no_rows(tmp_path: Path) -> None:
    """_db_has_projects should return False when project table is empty."""
    db_path = tmp_path / "empty.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY)")
        conn.commit()

    assert app_cli._db_has_projects(db_path) is False


def test_db_has_projects_returns_true_when_rows_exist(tmp_path: Path) -> None:
    """_db_has_projects should return True when project table has rows."""
    db_path = tmp_path / "seeded.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO project (name) VALUES ('Test Project')")
        conn.commit()

    assert app_cli._db_has_projects(db_path) is True


def test_db_has_projects_handles_corrupt_db_gracefully(tmp_path: Path, monkeypatch) -> None:
    """_db_has_projects should return False if sqlite3.Error occurs (corrupt DB)."""
    db_path = tmp_path / "corrupt.db"
    db_path.touch()

    def raise_on_connect(*_args, **_kwargs):
        raise sqlite3.DatabaseError("database disk image is malformed")

    monkeypatch.setattr(sqlite3, "connect", raise_on_connect)

    assert app_cli._db_has_projects(db_path) is False


def test_run_without_demo_or_db_path_passes_no_env(monkeypatch) -> None:
    """`handoff run` without flags should not set HANDOFF_DB_PATH env var."""
    calls = _capture_launch_streamlit(monkeypatch)

    result = RUNNER.invoke(app_cli.app, ["run"])

    assert result.exit_code == 0
    assert len(calls) == 1
    # When no demo/db_path, env should be None (inherit from parent)
    assert calls[0]["env"] is None


def test_run_demo_without_db_path_uses_default_demo_location(tmp_path: Path, monkeypatch) -> None:
    """`handoff run --demo` without --db-path should use default demo location."""
    calls = _capture_launch_streamlit(monkeypatch)

    # Mock get_demo_db_path to return a known location
    def mock_get_demo_db_path():
        return tmp_path / "demo.db"

    monkeypatch.setattr(app_cli, "get_demo_db_path", mock_get_demo_db_path)

    result = RUNNER.invoke(app_cli.app, ["run", "--demo"])

    assert result.exit_code == 0
    assert len(calls) == 1
    env = calls[0]["env"]
    assert isinstance(env, dict)
    assert env["HANDOFF_DB_PATH"] == str((tmp_path / "demo.db").resolve())


def test_run_demo_skips_seeding_when_db_already_has_projects(tmp_path: Path, monkeypatch) -> None:
    """_run --demo should skip seeding if DB already has project rows."""
    db_path = tmp_path / "seeded.db"
    # Create a DB with a project already seeded
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY, name TEXT)")
        conn.execute("INSERT INTO project (name) VALUES ('Existing Project')")
        conn.commit()

    calls = _capture_launch_streamlit(monkeypatch)
    seed_calls: list[tuple[Path, dict[str, object]]] = []

    def mock_seed_demo(path: Path, **kwargs) -> None:
        seed_calls.append((path, kwargs))

    monkeypatch.setattr(scripts.seed_demo, "seed_demo_db", mock_seed_demo)

    result = RUNNER.invoke(
        app_cli.app,
        ["run", "--demo", "--db-path", str(db_path)],
    )

    assert result.exit_code == 0
    # Should not call seed_demo_db since DB already has projects
    assert len(seed_calls) == 0
    assert len(calls) == 1


def test_run_demo_seeds_when_db_is_empty(tmp_path: Path, monkeypatch) -> None:
    """`handoff run --demo` should seed an empty DB."""
    db_path = tmp_path / "empty.db"
    # Create empty DB with schema but no data
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY, name TEXT)")
        conn.commit()

    calls = _capture_launch_streamlit(monkeypatch)
    seed_calls: list[tuple[Path, dict[str, object]]] = []

    def mock_seed_demo(path: Path, **kwargs) -> None:
        seed_calls.append((path, kwargs))

    monkeypatch.setattr(scripts.seed_demo, "seed_demo_db", mock_seed_demo)

    result = RUNNER.invoke(
        app_cli.app,
        ["run", "--demo", "--db-path", str(db_path)],
    )

    assert result.exit_code == 0
    # Should call seed_demo_db since DB is empty
    assert len(seed_calls) == 1
    assert seed_calls[0][0] == db_path
    assert seed_calls[0][1] == {"force": False}


def test_run_passes_extra_streamlit_args(monkeypatch) -> None:
    """`handoff run` should forward extra args to Streamlit via subprocess."""
    calls = _capture_launch_streamlit(monkeypatch)

    result = RUNNER.invoke(
        app_cli.app,
        [
            "run",
            "--",
            "--server.port",
            "9999",
            "--logger.level",
            "debug",
        ],
    )

    assert result.exit_code == 0
    assert len(calls) == 1
    assert calls[0]["args"] == [
        sys.executable,
        "-m",
        "handoff",
        "--server.port",
        "9999",
        "--logger.level",
        "debug",
    ]


def test_main_invokes_app_callback(monkeypatch) -> None:
    """main() should invoke the app() which runs typer."""
    invoked = {"called": False}

    def mock_app() -> None:
        invoked["called"] = True

    monkeypatch.setattr(app_cli, "app", mock_app)

    app_cli.main()

    assert invoked["called"] is True


def test_main_callback_without_subcommand_invokes_run(monkeypatch) -> None:
    """main_callback without subcommand should invoke run() command."""
    calls = _capture_launch_streamlit(monkeypatch)

    # Invoke with no arguments - should trigger the callback with no subcommand
    result = RUNNER.invoke(app_cli.app, ["run"])

    assert result.exit_code == 0
    assert len(calls) == 1
    # Should have called _launch_streamlit via run()
    assert calls[0]["args"] == [sys.executable, "-m", "handoff"]


def test_main_callback_with_subcommand_does_not_invoke_run(monkeypatch) -> None:
    """main_callback with subcommand should not invoke run()."""
    calls = _capture_launch_streamlit(monkeypatch)

    result = RUNNER.invoke(app_cli.app, ["cli"])

    assert result.exit_code == 1
    # Should not have invoked _launch_streamlit since 'cli' is a subcommand
    assert len(calls) == 0
    assert "handoff cli is not implemented yet" in result.stdout


def test_launch_streamlit_with_no_env_inherits_parent(monkeypatch) -> None:
    """_launch_streamlit with env=None should use os.environ."""
    monkeypatch.setenv("TEST_VAR", "test_value")
    run_calls: list[dict[str, object]] = []

    def mock_run(cmd, **kwargs) -> None:
        run_calls.append({"cmd": cmd, "kwargs": kwargs})

    monkeypatch.setattr(subprocess, "run", mock_run)

    app_cli._launch_streamlit(["--test"], env=None)

    assert len(run_calls) == 1
    # env should be a copy of os.environ
    assert "TEST_VAR" in run_calls[0]["kwargs"]["env"]
    assert run_calls[0]["kwargs"]["env"]["TEST_VAR"] == "test_value"


def test_launch_streamlit_with_env_uses_provided(monkeypatch) -> None:
    """_launch_streamlit with env dict should use and extend that dict."""
    run_calls: list[dict[str, object]] = []

    def mock_run(cmd, **kwargs) -> None:
        run_calls.append({"cmd": cmd, "kwargs": kwargs})

    monkeypatch.setattr(subprocess, "run", mock_run)

    custom_env = {"CUSTOM_VAR": "custom_value"}
    app_cli._launch_streamlit(["--test"], env=custom_env)

    assert len(run_calls) == 1
    assert run_calls[0]["kwargs"]["env"]["CUSTOM_VAR"] == "custom_value"
    # Should not mutate input env
    assert "HANDOFF_DB_PATH" not in custom_env


def test_db_has_projects_count_query_checks_row_value(tmp_path: Path) -> None:
    """_db_has_projects should correctly evaluate COUNT(*) > 0."""
    db_path = tmp_path / "multi.db"
    with sqlite3.connect(db_path) as conn:
        conn.execute("CREATE TABLE project (id INTEGER PRIMARY KEY, name TEXT)")
        # Insert multiple rows
        conn.execute("INSERT INTO project (name) VALUES ('P1')")
        conn.execute("INSERT INTO project (name) VALUES ('P2')")
        conn.execute("INSERT INTO project (name) VALUES ('P3')")
        conn.commit()

    assert app_cli._db_has_projects(db_path) is True
