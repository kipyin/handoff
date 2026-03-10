"""Check that Python source files stay under the PyArmor trial file-size limit.

PyArmor's trial license refuses to obfuscate files over ~32KB. This script
ensures every .py file under src/ (or the given paths) is under that limit
so the issue surfaces before building.

Usage:
    uv run handoff sizecheck                    # defaults to src/
    uv run handoff sizecheck path/to.py        # check given file(s) or dir(s)
    uv run handoff sizecheck --max-bytes 40000  # override size limit
    uv run handoff sizecheck --warn-threshold 0.8  # warn at 80% of limit
"""

from __future__ import annotations

import sys
from pathlib import Path

from . import ROOT

# PyArmor trial license refuses files over ~32KB. Use a conservative limit.
MAX_BYTES = 32 * 1024

# Warn when a file exceeds this fraction of the limit (e.g. 90% = 28.8KB).
WARN_THRESHOLD = 0.9

# Default path when no paths given.
DEFAULT_PATH = "src"


def _resolve_paths(paths: list[str] | None, default_path: str = DEFAULT_PATH) -> list[Path]:
    """Return absolute paths to check. Default: all .py under default_path (src/)."""
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
    root_dir = ROOT / default_path
    return sorted(root_dir.rglob("*.py"))


def run_sizecheck(
    paths: list[str] | None = None,
    *,
    default_path: str = DEFAULT_PATH,
    max_bytes: int = MAX_BYTES,
    warn_threshold: float = WARN_THRESHOLD,
) -> tuple[bool, list[str], list[str]]:
    """Check that all Python files are under max_bytes.

    Defaults to default_path (src/) if no paths provided; with paths, checks
    the given files/dirs.

    Args:
        paths: Optional list of paths (files or dirs). Default: all .py under default_path.
        default_path: Directory to check when paths is None (default: src).
        max_bytes: Maximum file size in bytes (default: 32KB).
        warn_threshold: Warn when file reaches this fraction of max_bytes (0-1).

    Returns:
        (ok, violations, warnings) where ok is True if no violations, violations
        list oversized files, warnings list files at or above warn_threshold of limit.
    """
    to_check = _resolve_paths(paths, default_path=default_path)
    violations: list[str] = []
    warnings_list: list[str] = []
    warn_threshold_bytes = int(max_bytes * warn_threshold)
    for path in to_check:
        size = path.stat().st_size
        try:
            rel = path.relative_to(ROOT)
        except ValueError:
            rel = path
        if size > max_bytes:
            violations.append(f"{rel}: {size:,} bytes (max {max_bytes:,})")
        elif size >= warn_threshold_bytes:
            pct = 100 * size / max_bytes
            warnings_list.append(f"{rel}: {size:,} bytes ({pct:.0f}% of limit)")
    return (len(violations) == 0, violations, warnings_list)


def main() -> None:
    """CLI entrypoint. Exit 0 if all files pass, 1 otherwise."""
    import argparse

    parser = argparse.ArgumentParser(description="Check .py files under size limit.")
    parser.add_argument(
        "paths",
        nargs="*",
        default=None,
        help="Paths to check (default: src/).",
    )
    parser.add_argument(
        "--path",
        "-p",
        default=DEFAULT_PATH,
        help=f"Default directory when no paths given (default: {DEFAULT_PATH}).",
    )
    parser.add_argument(
        "--max-bytes",
        type=int,
        default=MAX_BYTES,
        help=f"Max file size in bytes (default: {MAX_BYTES}).",
    )
    parser.add_argument(
        "--warn-threshold",
        type=float,
        default=WARN_THRESHOLD,
        help=f"Warn when file reaches this fraction of limit 0-1 (default: {WARN_THRESHOLD}).",
    )
    parsed = parser.parse_args()
    paths = parsed.paths if parsed.paths else None
    ok, violations, warnings_list = run_sizecheck(
        paths,
        default_path=parsed.path,
        max_bytes=parsed.max_bytes,
        warn_threshold=parsed.warn_threshold,
    )
    for w in warnings_list:
        print(f"warning: {w}", file=sys.stderr)
    if not ok:
        print(
            f"The following files exceed the limit ({parsed.max_bytes:,} bytes). "
            "Split them into smaller modules:\n" + "\n".join(f"  {v}" for v in violations),
            file=sys.stderr,
        )
        sys.exit(1)
    sys.exit(0)


if __name__ == "__main__":
    main()
