"""Guard tests for bootstrap module independence.

The bootstrap module must not import from handoff.db, handoff.core, handoff.data,
handoff.services, or handoff.interfaces. These tests enforce that bootstrap is
infra-only and can be extracted for template projects without dragging in app
dependencies.

Per template-readiness-refactoring.md, bootstrap independence is critical for
decoupling modules ahead of template extraction.
"""

from __future__ import annotations

import ast
from pathlib import Path

BOOTSTRAP_FILES = list(Path("src/handoff/bootstrap").glob("*.py"))


def _collect_imports_from_nodes(nodes: list[ast.AST]) -> set[str]:
    """Extract imports from a list of AST nodes (handles Import, ImportFrom, Try, If)."""
    imports = set()
    for node in nodes:
        if isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
        elif isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.Try):
            imports |= _collect_imports_from_nodes(node.body)
            for handler in node.handlers:
                imports |= _collect_imports_from_nodes(handler.body)
            imports |= _collect_imports_from_nodes(node.orelse)
            imports |= _collect_imports_from_nodes(node.finalbody)
        elif isinstance(node, ast.If):
            imports |= _collect_imports_from_nodes(node.body)
            imports |= _collect_imports_from_nodes(node.orelse)
    return imports


def _get_imports_from_file(path: Path, scope: str = "module") -> set[str]:
    """Extract module imports from a Python file.

    Args:
        path: Path to Python file.
        scope: 'module' for top-level imports only (executed on import),
               'all' for all imports including lazy/dynamic ones.
    """
    imports = set()
    try:
        tree = ast.parse(path.read_text(encoding="utf-8"), filename=str(path))
    except SyntaxError as e:
        raise SyntaxError(f"Bootstrap file {path} has syntax error: {e}") from e

    if scope == "module":
        # Top-level imports including those in try/if blocks (executed on import)
        imports = _collect_imports_from_nodes(tree.body)
    else:  # 'all'
        # All imports, including those inside functions/conditions
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module:
                    imports.add(node.module)
            elif isinstance(node, ast.Import):
                for alias in node.names:
                    imports.add(alias.name)
    return imports


def test_bootstrap_does_not_import_db() -> None:
    """Bootstrap: no db import at module level (lazy imports in functions OK)."""
    offenders: list[tuple[Path, str]] = []

    for path in BOOTSTRAP_FILES:
        if path.name == "__init__.py":
            continue
        imports = _get_imports_from_file(path, scope="module")
        if "handoff.db" in imports or any(imp.startswith("handoff.db.") for imp in imports):
            offenders.append((path, "handoff.db"))

    assert offenders == [], f"Bootstrap imports handoff.db at module level: {offenders}"


def test_bootstrap_does_not_import_core() -> None:
    """Bootstrap modules must not import from handoff.core at module level."""
    offenders: list[tuple[Path, str]] = []

    for path in BOOTSTRAP_FILES:
        if path.name == "__init__.py":
            continue
        imports = _get_imports_from_file(path, scope="module")
        if "handoff.core" in imports or any(imp.startswith("handoff.core.") for imp in imports):
            offenders.append((path, "handoff.core"))

    assert offenders == [], f"Bootstrap imports handoff.core at module level: {offenders}"


def test_bootstrap_does_not_import_data() -> None:
    """Bootstrap modules must not import from handoff.data at module level."""
    offenders: list[tuple[Path, str]] = []

    for path in BOOTSTRAP_FILES:
        if path.name == "__init__.py":
            continue
        imports = _get_imports_from_file(path, scope="module")
        if "handoff.data" in imports or any(imp.startswith("handoff.data.") for imp in imports):
            offenders.append((path, "handoff.data"))

    assert offenders == [], f"Bootstrap imports handoff.data at module level: {offenders}"


def test_bootstrap_does_not_import_services() -> None:
    """Bootstrap modules must not import from handoff.services at module level."""
    offenders: list[tuple[Path, str]] = []

    for path in BOOTSTRAP_FILES:
        if path.name == "__init__.py":
            continue
        imports = _get_imports_from_file(path, scope="module")
        if "handoff.services" in imports or any(
            imp.startswith("handoff.services.") for imp in imports
        ):
            offenders.append((path, "handoff.services"))

    assert offenders == [], f"Bootstrap imports handoff.services at module level: {offenders}"


def test_bootstrap_does_not_import_interfaces() -> None:
    """Bootstrap modules must not import from handoff.interfaces at module level."""
    offenders: list[tuple[Path, str]] = []

    for path in BOOTSTRAP_FILES:
        if path.name == "__init__.py":
            continue
        imports = _get_imports_from_file(path, scope="module")
        if "handoff.interfaces" in imports or any(
            imp.startswith("handoff.interfaces.") for imp in imports
        ):
            offenders.append((path, "handoff.interfaces"))

    assert offenders == [], f"Bootstrap imports handoff.interfaces at module level: {offenders}"


def test_bootstrap_does_not_import_streamlit_at_module_level() -> None:
    """Bootstrap: no streamlit import at module level (except config)."""
    offenders: list[Path] = []

    for path in BOOTSTRAP_FILES:
        if path.name == "config.py" or path.name == "__init__.py":
            # config.py is interface-specific by design; __init__ just re-exports
            continue
        imports = _get_imports_from_file(path)
        if "streamlit" in imports or any(imp.startswith("streamlit") for imp in imports):
            offenders.append(path)

    assert offenders == [], f"Non-config bootstrap files import streamlit: {offenders}"


def test_bootstrap_logging_can_import_without_db() -> None:
    """bootstrap.logging importable without triggering db import at call time."""
    import handoff.bootstrap.logging

    # Verify the module is importable
    assert hasattr(handoff.bootstrap.logging, "configure_logging")
    assert hasattr(handoff.bootstrap.logging, "log_application_action")


def test_bootstrap_paths_can_import_without_app_context() -> None:
    """Import bootstrap.paths without any app initialization."""
    import handoff.bootstrap.paths

    assert hasattr(handoff.bootstrap.paths, "get_app_root")
    # Call it to ensure it works
    path = handoff.bootstrap.paths.get_app_root()
    assert path.exists()


def test_bootstrap_docs_can_import_without_app_context() -> None:
    """Import bootstrap.docs without any app initialization."""
    import handoff.bootstrap.docs

    assert hasattr(handoff.bootstrap.docs, "read_markdown_from_app_root")
    assert hasattr(handoff.bootstrap.docs, "get_readme_intro")


def test_config_sets_only_streamlit_env_vars() -> None:
    """Streamlit runtime_config only sets STREAMLIT_* env vars (no app initialization)."""
    import os
    import subprocess
    import sys
    from pathlib import Path

    project_root = Path(__file__).resolve().parents[1]
    code = """
import os
# Clear STREAMLIT keys to test setdefault behavior
for key in list(os.environ.keys()):
    if key.startswith("STREAMLIT_"):
        del os.environ[key]
# Import runtime_config (Streamlit config moved from bootstrap.config)
import handoff.interfaces.streamlit.runtime_config  # noqa: F401
# Check only STREAMLIT_* keys were set
changed_keys = [k for k in os.environ.keys() if k.startswith("STREAMLIT_")]
print(",".join(sorted(changed_keys)))
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
    keys = result.stdout.strip().split(",")
    expected = {
        "STREAMLIT_BROWSER_GATHER_USAGE_STATS",
        "STREAMLIT_CLIENT_SHOW_ERROR_DETAILS",
        "STREAMLIT_CLIENT_SHOW_ERROR_LINKS",
        "STREAMLIT_CLIENT_SHOW_SIDEBAR_NAVIGATION",
        "STREAMLIT_CLIENT_TOOLBAR_MODE",
    }
    assert set(keys) == expected
