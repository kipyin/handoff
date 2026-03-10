"""Ensure no Python source file in src/ exceeds the PyArmor trial obfuscation limit.

PyArmor's trial license refuses to obfuscate files over ~32KB. We use that
as the limit so every module in src/ can be fully obfuscated without
requiring a paid PyArmor license.

If a file exceeds this limit, split it into smaller focused modules.
"""

from __future__ import annotations

import scripts.sizecheck as sizecheck_module


def test_no_source_file_exceeds_pyarmor_trial_limit() -> None:
    """Every .py file under src/ must stay under 32KB."""
    ok, violations = sizecheck_module.run_sizecheck(paths=None)
    assert ok, (
        "The following files exceed the PyArmor trial license limit. "
        "Split them into smaller modules, or run `uv run handoff sizecheck` "
        "for details:\n" + "\n".join(f"  {v}" for v in violations)
    )
