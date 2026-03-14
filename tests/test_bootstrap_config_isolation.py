"""Tests for bootstrap.config Streamlit env setup isolation.

bootstrap.config should only set STREAMLIT_* environment variables and must
not depend on any app-specific modules. This ensures bootstrap remains portable
for template extraction.

Per template-readiness-refactoring.md P1 fix: Streamlit config belongs in
interfaces/streamlit, not bootstrap. However, bootstrap.config currently exists
and should be tested for isolation to prevent coupling creep.
"""

from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path


def test_bootstrap_config_imports_are_minimal() -> None:
    """bootstrap.config has no handoff or streamlit imports at module level."""
    import ast

    config_file = Path("src/handoff/bootstrap/config.py")
    tree = ast.parse(config_file.read_text(encoding="utf-8"), filename=str(config_file))

    imports: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            if node.module and node.module != "__future__":
                imports.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                if alias.name != "__future__":
                    imports.add(alias.name)

    # Config was refactored minimal; Streamlit setup lives in runtime_config.
    assert not any(m.startswith("handoff.") or m.startswith("streamlit") for m in imports), (
        f"Unexpected imports in bootstrap.config: {imports}"
    )


def test_bootstrap_config_sets_exactly_five_env_vars() -> None:
    """bootstrap.config sets exactly the expected STREAMLIT_* variables."""
    project_root = Path(__file__).resolve().parents[1]
    code = """
import os
# Clear STREAMLIT keys
for key in list(os.environ.keys()):
    if key.startswith("STREAMLIT_"):
        del os.environ[key]
# Import runtime_config (Streamlit setup moved here from bootstrap.config)
import handoff.interfaces.streamlit.runtime_config
# Report keys
keys = sorted([k for k in os.environ.keys() if k.startswith("STREAMLIT_")])
print("\\n".join(keys))
"""
    env = {**os.environ, "PYTHONPATH": str(project_root / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    keys = result.stdout.strip().split("\n")
    expected_keys = {
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS",
        "STREAMLIT_CLIENT_SHOW_ERROR_DETAILS",
        "STREAMLIT_CLIENT_SHOW_ERROR_LINKS",
        "STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION",
        "STREAMLIT_CLIENT_TOOLBAR_MODE",
    }
    assert set(keys) == expected_keys, f"Got {set(keys)}, expected {expected_keys}"


def test_bootstrap_config_respects_existing_env_vars() -> None:
    """runtime_config uses setdefault; pre-set values are not overwritten.

    Streamlit setup moved from bootstrap.config to runtime_config.
    """
    project_root = Path(__file__).resolve().parents[1]
    code = """
import os
# Pre-set one value
os.environ["STREAMLIT_CLIENT_TOOLBAR_MODE"] = "custom"
# Import runtime_config
import handoff.interfaces.streamlit.runtime_config
# Check it was not overwritten
print(os.environ.get("STREAMLIT_CLIENT_TOOLBAR_MODE"))
"""
    env = {**os.environ, "PYTHONPATH": str(project_root / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    value = result.stdout.strip()
    assert value == "custom", f"Expected setdefault to preserve pre-set value, got {value}"


def test_bootstrap_config_sets_correct_values() -> None:
    """runtime_config sets the expected values for each STREAMLIT_* variable.

    Streamlit setup moved from bootstrap.config to runtime_config.
    """
    project_root = Path(__file__).resolve().parents[1]
    code = """
import os
# Clear STREAMLIT keys
for key in list(os.environ.keys()):
    if key.startswith("STREAMLIT_"):
        del os.environ[key]
# Import runtime_config
import handoff.interfaces.streamlit.runtime_config
# Report values
expected = {
    "STREAMLIT_CLIENT_SHOW_ERROR_DETAILS": "none",
    "STREAMLIT_CLIENT_TOOLBAR_MODE": "viewer",
    "STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION": "false",
    "STREAMLIT_CLIENT_SHOW_ERROR_LINKS": "false",
    "STREAMLIT_BROWSER_GATHER_USAGE_STATS": "false",
}
for key, expected_val in expected.items():
    actual = os.environ.get(key)
    if actual != expected_val:
        print(f"MISMATCH: {key}={actual} (expected {expected_val})")
    else:
        print(f"OK: {key}={actual}")
"""
    env = {**os.environ, "PYTHONPATH": str(project_root / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout.strip()
    # All lines should start with "OK:"
    lines = output.split("\n")
    assert all(line.startswith("OK:") for line in lines), f"Values mismatch:\n{output}"


def test_bootstrap_config_does_not_import_handoff_modules() -> None:
    """Importing bootstrap.config does not import core, data, db, services, or interfaces."""
    project_root = Path(__file__).resolve().parents[1]
    code = """
import sys
initial_modules = set(sys.modules.keys())
import handoff.bootstrap.config
final_modules = set(sys.modules.keys())
new_modules = final_modules - initial_modules
# Filter to problematic handoff modules (not bootstrap)
bad_modules = [m for m in new_modules if any(
    m.startswith(prefix) for prefix in (
        "handoff.core.",
        "handoff.data.",
        "handoff.db",
        "handoff.services.",
        "handoff.interfaces.",
    )
)]
if not bad_modules:
    print("PASS")
else:
    print(f"FAIL: {bad_modules}")
"""
    env = {**os.environ, "PYTHONPATH": str(project_root / "src")}
    result = subprocess.run(
        [sys.executable, "-c", code],
        cwd=str(project_root),
        env=env,
        capture_output=True,
        text=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    output = result.stdout.strip()
    assert output == "PASS", f"bootstrap.config imported unexpected modules: {output}"
