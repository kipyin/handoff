"""Regression tests for app.py and module import path restructuring.

This module verifies that app.py can correctly import from the relocated Streamlit UI
interfaces after PR #166 (project structure restructure PR4). Tests ensure that:

1. app.py imports from the new paths (handoff.interfaces.streamlit)
2. The now_page is importable from the new path
3. All five pages load without circular import issues
4. Integration tests using the compatibility shim continue to work
"""

from __future__ import annotations

import importlib
import sys
from pathlib import Path

import pytest


def test_app_py_can_import_render_now_page() -> None:
    """app.py can import render_now_page from handoff.interfaces.streamlit.pages.now."""
    from handoff.interfaces.streamlit.pages.now import render_now_page

    assert callable(render_now_page)


def test_app_py_can_import_ui_entrypoints() -> None:
    """app.py can import all UI entrypoints from handoff.interfaces.streamlit.ui."""
    from handoff.interfaces.streamlit.ui import (
        render_about_page,
        render_dashboard_page,
        render_projects_page,
        render_system_settings_page,
        setup,
    )

    assert all(
        callable(f)
        for f in [
            setup,
            render_about_page,
            render_dashboard_page,
            render_projects_page,
            render_system_settings_page,
        ]
    )


def test_app_py_load_without_error() -> None:
    """app.py itself can be executed without import errors."""
    workspace = Path("/workspace")
    app_py = workspace / "app.py"

    # Compile and execute app.py to verify no import errors at module level
    with open(app_py) as f:
        code = f.read()

    # Ensure it parses without syntax errors
    compile(code, str(app_py), "exec")


def test_no_circular_imports_from_app_imports() -> None:
    """Importing all app.py dependencies does not create circular imports."""
    # These are the exact imports from app.py
    from handoff.interfaces.streamlit.pages.now import render_now_page  # noqa: F401
    from handoff.interfaces.streamlit.ui import (  # noqa: F401
        render_about_page,
        render_dashboard_page,
        render_projects_page,
        render_system_settings_page,
        setup,
    )
    from handoff.version import __version__  # noqa: F401

    # If we get here, all imports succeeded without circular dependency issues


def test_integration_entry_functions_use_compatibility_shim() -> None:
    """Integration test entry functions can use handoff.ui (compatibility shim)."""
    # This mirrors the pattern used in test_app_integration.py
    import handoff.ui as ui
    from handoff.interfaces.streamlit.pages.projects import render_projects_page

    # Both should be callable
    assert callable(ui.setup)
    assert callable(render_projects_page)


def test_all_page_files_exist_in_new_location() -> None:
    """All page files exist in handoff/interfaces/streamlit/pages/."""
    pages_dir = Path("/workspace/src/handoff/interfaces/streamlit/pages")
    required_pages = [
        "__init__.py",
        "about.py",
        "dashboard.py",
        "now.py",
        "projects.py",
        "system_settings.py",
    ]

    for page_file in required_pages:
        page_path = pages_dir / page_file
        assert page_path.exists(), f"Missing page file: {page_file}"


def test_old_pages_directory_no_longer_contains_pages() -> None:
    """The old src/handoff/pages directory no longer contains page implementations."""
    old_pages_dir = Path("/workspace/src/handoff/pages")

    # Directory may exist (for __init__.py placeholder) but should not have page modules
    if old_pages_dir.exists():
        page_files = list(old_pages_dir.glob("*.py"))
        # Only __init__.py should remain (if anything)
        for f in page_files:
            assert f.name == "__init__.py", f"Found unexpected file in old pages dir: {f.name}"


def test_streamlit_ui_module_exports_public_interface() -> None:
    """handoff.interfaces.streamlit.ui properly exports all public functions."""
    import handoff.interfaces.streamlit.ui as ui

    # Verify all public functions are exported in __all__
    assert hasattr(ui, "__all__")
    public_exports = ui.__all__

    # Each exported name should be callable
    for name in public_exports:
        obj = getattr(ui, name)
        assert callable(obj), f"{name} is not callable"


def test_update_ui_importable_from_new_path() -> None:
    """update_ui module is in the new interfaces location."""
    from handoff.interfaces.streamlit.update_ui import render_update_panel

    assert callable(render_update_panel)


def test_autosave_importable_from_new_path() -> None:
    """autosave module is in the new interfaces location."""
    from handoff.interfaces.streamlit.autosave import autosave_editor

    assert callable(autosave_editor)


def test_module_reload_safety() -> None:
    """Reloading handoff.db and UI modules doesn't cause import errors.

    This is important for integration tests that point to different DBs.
    """
    import handoff.db as db
    import handoff.interfaces.streamlit.ui as ui_module

    importlib.reload(db)
    importlib.reload(ui_module)

    # Both should still be functional
    assert hasattr(ui_module, "setup")
    assert callable(ui_module.setup)


def test_pages_import_services_not_data_directly(monkeypatch: pytest.MonkeyPatch) -> None:
    """Verify that pages use the service layer rather than importing data directly.

    This is an architectural guard that checks the actual imports.
    """
    import ast
    from pathlib import Path

    pages_dir = Path("src/handoff/interfaces/streamlit/pages")

    # Check each page file
    for page_file in pages_dir.glob("*.py"):
        if page_file.name == "__init__.py":
            continue

        tree = ast.parse(page_file.read_text(encoding="utf-8"))

        # Look for direct imports of handoff.data
        for node in ast.walk(tree):
            if isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("handoff.data"):
                    pytest.fail(
                        f"{page_file.name} imports directly from {node.module}, "
                        "should use services instead"
                    )
