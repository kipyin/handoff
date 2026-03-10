"""Check that Python source files stay under the PyArmor trial file-size limit.

PyArmor's trial license refuses to obfuscate files over ~32KB. This script
ensures every .py file under src/ (or the given paths) is under that limit
so the issue surfaces before building.

Usage:
    uv run handoff sizecheck
    uv run handoff sizecheck src/handoff/data/queries.py
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import ROOT, SRC

# PyArmor trial license refuses files over ~32KB. Use a conservative limit.
MAX_BYTES = 32 * 1024


def _resolve_paths(paths: list[str] | None) -> list[Path]:
    """Return absolute paths to check. Default: all .py under src/."""
    if paths:
        resolved: list[Path] = []
        for p in paths:
            path = Path(p)
            if not path.is_absolute():
                path = ROOT / path
            if path.is_dir():
                resolved.extend(path.rglob("*.py"))
            elif path.suffix == ".py":
                resolved.append(path)
        return sorted(set(resolved))
    return sorted(SRC.rglob("*.py"))


def run_sizecheck(paths: list[str] | None = None) -> tuple[bool, list[str]]:
    """Check that all Python files are under MAX_BYTES.

    Args:
        paths: Optional list of paths (files or dirs). Default: all src/**/*.py.

    Returns:
        (ok, violations) where ok is True if no violations, violations list
        describes each oversized file.
    """
    to_check = _resolve_paths(paths)
    violations: list[str] = []
    for path in to_check:
        size = path.stat().st_size
        if size > MAX_BYTES:
            try:
                rel = path.relative_to(ROOT)
            except ValueError:
                rel = path
            violations.append(f"{rel}: {size:,} bytes (max {MAX_BYTES:,})")
    return (len(violations) == 0, violations)


def main() -> None:
    """CLI entrypoint. Exit 0 if all files pass, 1 otherwise."""
    args = sys.argv[1:] if len(sys.argv) > 1 else []
    ok, violations = run_sizecheck(args if args else None)
    if not ok:
        print(
            "The following files exceed the PyArmor trial license limit "
            f"({MAX_BYTES:,} bytes). Split them into smaller modules:\n"
            + "\n".join(f"  {v}" for v in violations),
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
