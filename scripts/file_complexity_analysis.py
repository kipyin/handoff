"""Analyze file complexity for PyArmor obfuscation compatibility.

PyArmor trial version limits each code object to ~32,768 bytes. This script
reports module-level compiled sizes and cyclomatic complexity to identify
files that may fail obfuscation.

Usage:
    uv run python scripts/file_complexity_analysis.py
"""

from pathlib import Path
import marshal
import subprocess
import sys

PYARMOR_LIMIT = 32_768
SRC_ROOT = Path(__file__).resolve().parent.parent / "src" / "handoff"


def code_size(co: object) -> int:
    """Serialized size of a code object (what PyArmor processes)."""
    return len(marshal.dumps(co))


def get_module_sizes() -> list[tuple[int, Path]]:
    """Return (size, path) for each Python file, sorted by size descending."""
    results: list[tuple[int, Path]] = []
    for path in sorted(SRC_ROOT.rglob("*.py")):
        try:
            with path.open() as f:
                code = compile(f.read(), str(path), "exec")
            results.append((code_size(code), path))
        except Exception:
            pass
    results.sort(key=lambda x: -x[0])
    return results


def run_radon_cc() -> str | None:
    """Run radon cc if available; return summary or None."""
    try:
        proc = subprocess.run(
            ["radon", "cc", str(SRC_ROOT), "-a", "-s"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        return proc.stdout if proc.returncode == 0 else None
    except (FileNotFoundError, subprocess.TimeoutExpired):
        return None


def main() -> int:
    print("=" * 60)
    print("PyArmor Complexity Analysis")
    print("=" * 60)
    print(f"Trial limit: {PYARMOR_LIMIT:,} bytes per code object")
    print()

    sizes = get_module_sizes()
    over_limit = [(s, p) for s, p in sizes if s > PYARMOR_LIMIT]
    under_limit = [(s, p) for s, p in sizes if s <= PYARMOR_LIMIT]

    print("Module compiled size (marshal) - largest first:")
    print(f"  {'Bytes':>8}  File")
    print("  " + "-" * 48)
    for size, path in sizes[:20]:
        rel = path.relative_to(SRC_ROOT)
        flag = " ** EXCEEDS 32KB **" if size > PYARMOR_LIMIT else ""
        print(f"  {size:>8,}  {rel}{flag}")

    print()
    if over_limit:
        print(f"Files exceeding PyArmor trial limit: {len(over_limit)}")
        for size, path in over_limit:
            print(f"  - {path.relative_to(SRC_ROOT)} ({size:,} bytes)")
        print()
        print("Consider splitting the largest file or purchasing a PyArmor license.")
        return 1
    else:
        print("All files are within PyArmor trial limits.")
        return 0


if __name__ == "__main__":
    sys.exit(main())
