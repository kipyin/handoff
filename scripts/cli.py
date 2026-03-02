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


@app.command()
def run() -> None:
    """Run the Streamlit app (applies Streamlit options from handoff.config)."""
    run_cmd(
        ["uv", "run", "python", "-m", "handoff"],
        cwd=ROOT,
        description="Starting Streamlit app...",
    )


@app.callback(invoke_without_command=True)
def main_callback(ctx: typer.Context) -> None:
    """Default entrypoint so `uv run handoff` behaves like `uv run handoff run`."""
    if ctx.invoked_subcommand is None:
        run()


@app.command()
def sync() -> None:
    """Install or update project dependencies using uv."""
    run_cmd(["uv", "sync"], cwd=ROOT, description="Syncing dependencies with uv...")


@app.command()
def lint() -> None:
    """Run Ruff lint checks."""
    run_cmd(["uv", "run", "ruff", "check", "."], cwd=ROOT, description="Running Ruff lint...")


@app.command()
def format() -> None:
    """Run Ruff formatter."""
    run_cmd(
        ["uv", "run", "ruff", "format", "."],
        cwd=ROOT,
        description="Running Ruff formatter...",
    )


@app.command("check")
def check_command() -> None:
    """Run lint and format in sequence."""
    lint()
    format()


@app.command()
def test() -> None:
    """Run the pytest test suite."""
    run_cmd(["uv", "run", "pytest"], cwd=ROOT, description="Running tests with pytest...")


@app.command("typecheck")
def typecheck() -> None:
    """Run pyright type checking over src/ and scripts/."""
    run_cmd(
        ["uv", "run", "pyright", "src", "scripts"],
        cwd=ROOT,
        description="Running pyright type checking...",
    )


@app.command("ci")
def ci() -> None:
    """Run lint, format, type checking, and tests."""
    check_command()
    typecheck()
    test()


@app.command("build-full")
def build_full() -> None:
    """Build the full Windows embedded zip distribution."""
    console.print("Building full Windows embedded zip distribution...", style="bold cyan")
    build_zip_module.main()


@app.command("bump-version")
def bump_version(
    version: str = typer.Argument(..., help="New version string (for example: 2026.3.0)"),
) -> None:
    """Bump project and app version together."""
    bump_version_module.bump_version(version)
    console.print(f"Bumped version to {version}", style="bold green")


@app.command("build-patch")
def build_patch(
    include_pages: bool = typer.Option(
        True,
        "--include-pages/--skip-pages",
        help="Include the pages/ directory (from source) in the patch zip.",
    ),
) -> None:
    """Build a patch zip from the build output (run after build-full for PyArmor installs)."""
    path = build_patch_module.build_patch(include_pages=include_pages)
    console.print(f"Patch zip created at {path}", style="bold green")


def main() -> None:
    """Entrypoint for `python -m scripts.cli`."""
    app()


if __name__ == "__main__":
    main()
