"""Helpers for running subprocess commands with nice console output."""

from __future__ import annotations

import subprocess
from collections.abc import Sequence
from pathlib import Path

from rich.console import Console
from rich.text import Text

console = Console()


def run_cmd(
    args: Sequence[str],
    *,
    cwd: Path | None = None,
    env: dict[str, str] | None = None,
    description: str | None = None,
) -> None:
    """Run a subprocess and echo the command with Rich.

    Args:
        args: Command and arguments to execute.
        cwd: Optional working directory.
        env: Optional environment overrides.
        description: Optional human-friendly description shown before running.

    """
    cmd_str = " ".join(args)
    if description:
        console.print(Text(description, style="bold cyan"))
    console.print(Text(f"$ {cmd_str}", style="dim"))

    try:
        subprocess.run(args, check=True, cwd=str(cwd) if cwd else None, env=env)
    except subprocess.CalledProcessError as exc:
        console.print(
            Text(f"Command failed with exit code {exc.returncode}", style="bold red"),
        )
        raise
