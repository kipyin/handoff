"""Typer-based CLI entrypoint for local development and build tasks."""

from __future__ import annotations

import os
import sqlite3
from enum import StrEnum
from pathlib import Path

import typer
from rich.console import Console

from handoff.db import get_demo_db_path

from . import ROOT
from . import build_full as build_full_module
from . import build_patch as build_patch_module
from . import bump_version as bump_version_module
from . import seed_demo as seed_demo_module
from . import sizecheck as sizecheck_module
from .subprocess_utils import run_cmd


class BuildPlatform(StrEnum):
    """Supported target platforms for full builds."""

    WINDOWS = "windows"
    MAC = "mac"


app = typer.Typer(help="Handoff development and build commands.")
console = Console()

EXTRA_ARGS_ARG = typer.Argument(None)
PLATFORM_OPT = typer.Option(
    BuildPlatform.WINDOWS,
    "--platform",
    help="Target platform for --full builds: 'windows' or 'mac'.",
)


def _extract_fix_flag(extra_args: list[str] | None = None) -> tuple[list[str], bool]:
    """Return non-fix args plus whether ``--fix`` was requested."""
    args = list(extra_args) if isinstance(extra_args, (list, tuple)) else []
    fix = False
    filtered_args: list[str] = []
    for arg in args:
        if arg == "--fix":
            fix = True
            continue
        filtered_args.append(arg)
    return filtered_args, fix


def _ruff_targets(extra_args: list[str] | None = None) -> list[str]:
    """Return Ruff target args, defaulting to the repository root."""
    args = list(extra_args) if isinstance(extra_args, (list, tuple)) else []
    return args or ["."]


def _run_format(extra_args: list[str] | None = None, *, check: bool) -> None:
    """Run Ruff format in check or apply mode."""
    args = _ruff_targets(extra_args)
    cmd = ["uv", "run", "ruff", "format"]
    if check:
        cmd.append("--check")
    cmd.extend(args)
    description = "Running Ruff format check..." if check else "Running Ruff formatter..."
    run_cmd(cmd, cwd=ROOT, description=description)


def _run_lint(extra_args: list[str] | None = None, *, fix: bool) -> None:
    """Run Ruff lint in check or fix mode."""
    args = _ruff_targets(extra_args)
    cmd = ["uv", "run", "ruff", "check"]
    if fix:
        cmd.append("--fix")
    cmd.extend(args)
    description = "Running Ruff lint with fixes..." if fix else "Running Ruff lint..."
    run_cmd(cmd, cwd=ROOT, description=description)


def _format_and_lint(extra_args: list[str] | None = None, *, fix: bool) -> None:
    """Run format and lint checks, optionally applying Ruff fixes."""
    _run_format(extra_args=extra_args, check=not fix)
    _run_lint(extra_args=extra_args, fix=fix)


def _ci_run(extra_args: list[str] | None = None) -> None:
    """Run checks/typecheck/sizecheck/tests, allowing optional Ruff fixes via ``--fix``."""
    extra_args, fix = _extract_fix_flag(extra_args)
    _format_and_lint(extra_args=extra_args, fix=fix)
    typecheck(extra_args=extra_args)
    sizecheck(
        extra_args=[],
        path="src",
        max_bytes=32 * 1024,
        warn_threshold=0.9,
    )  # Always check src/; do not forward test paths
    test(extra_args=extra_args)


def _resolve_demo_db_path(db_path: str | None) -> Path:
    """Return the explicit demo DB path or the default demo location."""
    if db_path:
        return Path(db_path).expanduser().resolve()
    return get_demo_db_path()


def _db_has_projects(db_path: Path) -> bool:
    """Return True when the SQLite DB already has at least one project row."""
    if not db_path.exists():
        return False

    try:
        with sqlite3.connect(db_path) as conn:
            table_exists = conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name='project'"
            ).fetchone()
            if table_exists is None:
                return False
            row = conn.execute("SELECT COUNT(*) FROM project").fetchone()
    except sqlite3.Error:
        return False

    return bool(row and row[0] > 0)


@app.command("cli")
def cli_command() -> None:
    """Run the handoff CLI (stub for future implementation)."""
    console.print(
        "[bold red]handoff cli is not implemented yet.[/bold red]\n"
        "This subcommand is reserved for a future interactive CLI interface."
    )
    raise typer.Exit(code=1)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def run(
    demo: bool = typer.Option(False, "--demo", help="Run against a demo database."),
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help="Override the database path. With --demo, defaults to the demo DB path.",
    ),
    extra_args: list[str] = EXTRA_ARGS_ARG,
) -> None:
    """Run the Streamlit app (applies Streamlit options from handoff.bootstrap.config)."""
    extra_args = list(extra_args) if extra_args else []
    env = None
    if demo:
        demo_db_path = _resolve_demo_db_path(db_path)
        if not _db_has_projects(demo_db_path):
            seed_demo_module.seed_demo_db(demo_db_path, force=False)
        env = {**os.environ, "HANDOFF_DB_PATH": str(demo_db_path)}
    run_cmd(
        ["uv", "run", "python", "-m", "handoff", *extra_args],
        cwd=ROOT,
        env=env,
        description="Starting Streamlit app...",
    )


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Default entrypoint so `uv run handoff` behaves like `uv run handoff run`."""
    if ctx.invoked_subcommand is None:
        run(extra_args=list(ctx.args))


@app.command("seed-demo")
def seed_demo(
    db_path: str | None = typer.Option(
        None,
        "--db-path",
        help="Override the database path. Defaults to the demo DB path.",
    ),
    force: bool = typer.Option(False, "--force", help="Replace any existing demo DB."),
) -> None:
    """Create or refresh a demo database with representative seed data."""
    resolved_path = _resolve_demo_db_path(db_path)
    seed_demo_module.seed_demo_db(resolved_path, force=force)
    console.print(f"Demo database ready at {resolved_path}", style="bold green")


@app.command()
def sync(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Install or update project dependencies using uv."""
    extra_args = list(extra_args) if extra_args else []
    run_cmd(["uv", "sync", *extra_args], cwd=ROOT, description="Syncing dependencies with uv...")


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def lint(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Run Ruff lint checks; pass ``--fix`` to apply fixes."""
    extra_args, fix = _extract_fix_flag(extra_args)
    _run_lint(extra_args=extra_args, fix=fix)


@app.command("format", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def format_(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Run Ruff formatter."""
    extra_args, _ = _extract_fix_flag(extra_args)
    _run_format(extra_args=extra_args, check=False)


@app.command("check", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def check_command(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Run format/lint checks; pass ``--fix`` to apply Ruff changes."""
    extra_args, fix = _extract_fix_flag(extra_args)
    _format_and_lint(extra_args=extra_args, fix=fix)


@app.command(context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def test(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Run the pytest test suite."""
    extra_args = list(extra_args) if extra_args else ["."]
    run_cmd(
        [
            "uv",
            "run",
            "pytest",
            *extra_args,
        ],
        cwd=ROOT,
        description="Running tests with pytest...",
    )


@app.command("typecheck")
def typecheck(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Run pyright type checking over src/ and scripts/."""
    extra_args = list(extra_args) if extra_args else ["src", "scripts"]
    run_cmd(
        ["uv", "run", "pyright", *extra_args],
        cwd=ROOT,
        description="Running pyright type checking...",
    )


@app.command("sizecheck", context_settings={"allow_extra_args": True})
def sizecheck(
    extra_args: list[str] = EXTRA_ARGS_ARG,
    path: str = typer.Option(
        "src",
        "--path",
        "-p",
        help="Default directory to check when no paths given.",
    ),
    max_bytes: int = typer.Option(
        32 * 1024,
        "--max-bytes",
        help="Max file size in bytes.",
    ),
    warn_threshold: float = typer.Option(
        0.9,
        "--warn-threshold",
        help="Warn when file reaches this fraction of limit (0-1).",
    ),
) -> None:
    """Check .py files under size limit. Defaults to src/; with args, checks given paths."""
    extra_args = list(extra_args) if extra_args else []
    ok, violations, warnings_list = sizecheck_module.run_sizecheck(
        extra_args if extra_args else None,
        default_path=path,
        max_bytes=max_bytes,
        warn_threshold=warn_threshold,
    )
    for w in warnings_list:
        console.print(f"warning: {w}", style="bold yellow")
    if not ok:
        console.print(
            f"The following files exceed the limit ({max_bytes:,} bytes):\n"
            + "\n".join(f"  {v}" for v in violations),
            style="bold red",
        )
        raise typer.Exit(code=1)
    console.print(f"All files under {max_bytes:,} bytes.", style="bold green")


@app.command("ci", context_settings={"allow_extra_args": True, "ignore_unknown_options": True})
def ci(extra_args: list[str] = EXTRA_ARGS_ARG) -> None:
    """Run check, type checking, and tests; pass ``--fix`` for Ruff fixes first."""
    extra_args = list(extra_args) if extra_args else []
    _ci_run(extra_args=extra_args)


@app.command("build")
def build(
    full: bool = typer.Option(
        False, "--full", help="Build a full embedded/standalone distribution."
    ),
    patch: bool = typer.Option(False, "--patch", help="Build a patch zip from the build output."),
    platform: BuildPlatform = PLATFORM_OPT,
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Run build steps without download/obfuscation/archive; for CI.",
    ),
) -> None:
    """Build the application (full distribution or patch)."""
    if full:
        label = "macOS standalone" if platform == BuildPlatform.MAC else "Windows embedded zip"
        console.print(f"Building full {label} distribution...", style="bold cyan")
        build_full_module.main(platform=platform.value, dry_run=dry_run)
    elif patch:
        path = build_patch_module.build_patch(dry_run=dry_run)
        if dry_run:
            console.print(f"Dry run complete. Would create {path}", style="bold cyan")
        else:
            console.print(f"Patch zip created at {path}", style="bold green")
    else:
        console.print("Please specify either --full or --patch.", style="bold red")
        raise typer.Exit(code=1)


@app.command("bump")
def bump(
    version: str = typer.Argument(..., help="New version string (for example: 2026.3.0)"),
) -> None:
    """Bump project and app version together."""
    bump_version_module.bump_version(version)
    console.print(f"Bumped version to {version}", style="bold green")


@app.command("db-path")
def db_path() -> None:
    """Print the resolved SQLite database path."""
    from handoff.db import get_db_path

    console.print(str(get_db_path()))


def main() -> None:
    """Entrypoint for `python -m scripts.cli`."""
    app()


if __name__ == "__main__":
    main()
