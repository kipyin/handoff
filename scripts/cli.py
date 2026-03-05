"""Typer-based CLI entrypoint for local development and build tasks."""

from __future__ import annotations

import typer
from rich.console import Console

from . import ROOT
from . import build_patch as build_patch_module
from . import build_zip as build_zip_module
from . import bump_version as bump_version_module
from .subprocess_utils import run_cmd

app = typer.Typer(help="Handoff development and build commands.")
console = Console()

def _format_and_lint(extra_args: list[str] | None = None) -> None:
    """Run lint and format with optional extra args passed to underlying tools."""
    extra_args = list(extra_args) if extra_args else []
    format(extra_args=extra_args)
    lint(extra_args=extra_args)


def _ci_run(extra_args: list[str] | None = None) -> None:
    """Run lint/format/typecheck/tests in a CI-like sequence with optional extra args."""
    extra_args = list(extra_args) if extra_args else []
    _format_and_lint(extra_args=extra_args)
    typecheck(extra_args=extra_args)
    test(extra_args=extra_args)


@app.command()
def run(extra_args: list[str] = typer.Argument(None, nargs=-1)) -> None:
    """Run the Streamlit app (applies Streamlit options from handoff.config)."""
    extra_args = list(extra_args) if extra_args else []
    run_cmd(
        ["uv", "run", "python", "-m", "handoff", *extra_args],
        cwd=ROOT,
        description="Starting Streamlit app...",
    )


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Default entrypoint so `uv run handoff` behaves like `uv run handoff run`."""
    if ctx.invoked_subcommand is None:
        run()


@app.command()
def sync(extra_args: list[str] = typer.Argument(None, nargs=-1)) -> None:
    """Install or update project dependencies using uv."""
    extra_args = list(extra_args) if extra_args else []
    run_cmd(["uv", "sync", *extra_args], cwd=ROOT, description="Syncing dependencies with uv...")


@app.command()
def lint(extra_args: list[str] = typer.Argument(None, nargs=-1)) -> None:
    """Run Ruff lint checks."""
    extra_args = list(extra_args) if extra_args else []
    run_cmd(["uv", "run", "ruff", "check", ".", *extra_args], cwd=ROOT, description="Running Ruff lint...")


@app.command()
def format(extra_args: list[str] = typer.Argument(None, nargs=-1)) -> None:
    """Run Ruff formatter."""
    extra_args = list(extra_args) if extra_args else []
    run_cmd(
        ["uv", "run", "ruff", "format", ".", *extra_args],
        cwd=ROOT,
        description="Running Ruff formatter...",
    )


@app.command("check")
def check_command() -> None:
    """Run lint and format in sequence."""
    format()
    lint()


@app.command()
def test(extra_args: list[str] = typer.Argument(None, nargs=-1)) -> None:
    """Run the pytest test suite."""
    extra_args = list(extra_args) if extra_args else []
    run_cmd(["uv", "run", "pytest", *extra_args], cwd=ROOT, description="Running tests with pytest...")


@app.command("typecheck")
def typecheck() -> None:
    """Run pyright type checking over src/ and scripts/."""
    run_cmd(
        ["uv", "run", "pyright", "src", "scripts"],
        cwd=ROOT,
        description="Running pyright type checking...",
    )


@app.command("ci")
def ci(extra_args: list[str] = typer.Argument(None, nargs=-1)) -> None:
    """Run lint, format, type checking, and tests."""
    extra_args = list(extra_args) if extra_args else []
    _ci_run(extra_args=extra_args)


@app.command("build")
def build(
    full: bool = typer.Option(
        False, "--full", help="Build the full Windows embedded zip distribution."
    ),
    patch: bool = typer.Option(False, "--patch", help="Build a patch zip from the build output."),
    include_pages: bool = typer.Option(
        True,
        "--include-pages/--skip-pages",
        help="Include the pages/ directory (from source) in the patch zip (only for --patch).",
    ),
) -> None:
    """Build the application (full distribution or patch)."""
    if full:
        console.print("Building full Windows embedded zip distribution...", style="bold cyan")
        build_zip_module.main()
    elif patch:
        path = build_patch_module.build_patch(include_pages=include_pages)
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


def main() -> None:
    """Entrypoint for `python -m scripts.cli`."""
    app()


if __name__ == "__main__":
    main()
