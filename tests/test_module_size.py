"""Ensure no Python source file in src/ exceeds the PyArmor trial obfuscation limit.

PyArmor's trial license refuses to obfuscate "big scripts". Empirical testing
shows the limit is roughly 780–840 lines for typical application code. We use
750 lines as a conservative threshold so every module in src/ can be fully
obfuscated without requiring a paid PyArmor license.

If a file exceeds this limit, split it into smaller focused modules.
"""

from __future__ import annotations

from pathlib import Path

SRC_ROOT = Path(__file__).resolve().parents[1] / "src"

# Conservative threshold that keeps every module comfortably below the
# ~780-line limit observed with PyArmor 9.x trial license.
MAX_LINES = 750


def _python_files() -> list[Path]:
    return sorted(SRC_ROOT.rglob("*.py"))


def test_no_source_file_exceeds_pyarmor_trial_limit() -> None:
    """Every .py file under src/ must stay under MAX_LINES lines."""
    violations: list[str] = []
    for path in _python_files():
        line_count = len(path.read_text(encoding="utf-8").splitlines())
        if line_count > MAX_LINES:
            violations.append(f"{path.relative_to(SRC_ROOT)}: {line_count} lines (max {MAX_LINES})")

    assert not violations, (
        "The following files exceed the PyArmor trial license limit "
        f"({MAX_LINES} lines). Split them into smaller modules:\n"
        + "\n".join(f"  {v}" for v in violations)
    )
