"""App CLI interface: run the product (Streamlit, future interactive CLI)."""

from __future__ import annotations

import os
import sqlite3
import subprocess
import sys
from pathlib import Path

import typer
from rich.console import Console

from handoff.bootstrap.paths import get_app_root
from handoff.db import get_demo_db_path

ROOT = get_app_root()
app = typer.Typer(help="Handoff app launcher.")
EXTRA_ARGS_ARG = typer.Argument(None)


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
                "SELECT 1 FROM sqlite_master WHERE type=? AND name=?",
                ("table", "project"),
            ).fetchone()
            if table_exists is None:
                return False
            row = conn.execute("SELECT COUNT(*) FROM project").fetchone()
    except sqlite3.Error:
        return False

    return bool(row and row[0] > 0)


def _launch_streamlit(extra_args: list[str], env: dict[str, str] | None = None) -> None:
    """Spawn Streamlit via python -m handoff, inheriting or using the given env."""
    root = get_app_root()
    final_env: dict[str, str] = dict(env) if env is not None else dict(os.environ)
    cmd = [sys.executable, "-m", "handoff", *extra_args]
    subprocess.run(cmd, cwd=root, env=final_env, check=True)


@app.command("cli")
def cli_command() -> None:
    """Run the handoff CLI (stub for future implementation)."""
    console = Console()
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
    """Run the Streamlit app (applies Streamlit options from runtime_config)."""
    extra_args = list(extra_args) if extra_args else []
    env = None
    if demo:
        import scripts.seed_demo as seed_demo_module

        resolved = _resolve_demo_db_path(db_path)
        if not _db_has_projects(resolved):
            seed_demo_module.seed_demo_db(resolved, force=False)
        env = {**os.environ, "HANDOFF_DB_PATH": str(resolved)}
    elif db_path is not None:
        env = {**os.environ, "HANDOFF_DB_PATH": str(db_path)}
    _launch_streamlit(extra_args, env=env)


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Default entrypoint so `uv run handoff` behaves like `uv run handoff run`."""
    if ctx.invoked_subcommand is None:
        run(extra_args=list(ctx.args))


def main() -> None:
    """Entrypoint for `uv run handoff`."""
    app()


__all__ = ["ROOT", "app", "main"]
