"""Regression tests for handoff.ui compatibility shim and interfaces package structure.

This module verifies that the restructured UI interfaces remain accessible through:
1. The compatibility shim at handoff.ui (for backward compatibility)
2. Direct imports from handoff.interfaces.streamlit.ui (new canonical path)
3. The public package __init__.py at handoff.interfaces.streamlit

These tests prevent regressions when the Streamlit UI is relocated to handoff/interfaces/streamlit/.
"""

from __future__ import annotations

import importlib
import sys
from unittest.mock import MagicMock, patch

import pytest


def test_handoff_ui_compatibility_shim_exports_setup() -> None:
    """handoff.ui shim re-exports setup function from interfaces.streamlit.ui."""
    # Re-import to ensure fresh module state
    import handoff.ui as ui_module

    importlib.reload(ui_module)
    assert hasattr(ui_module, "setup")
    assert callable(ui_module.setup)


def test_handoff_ui_compatibility_shim_exports_render_projects_page() -> None:
    """handoff.ui shim re-exports render_projects_page."""
    import handoff.ui as ui_module

    importlib.reload(ui_module)
    assert hasattr(ui_module, "render_projects_page")
    assert callable(ui_module.render_projects_page)


def test_handoff_ui_compatibility_shim_exports_render_dashboard_page() -> None:
    """handoff.ui shim re-exports render_dashboard_page."""
    import handoff.ui as ui_module

    importlib.reload(ui_module)
    assert hasattr(ui_module, "render_dashboard_page")
    assert callable(ui_module.render_dashboard_page)


def test_handoff_ui_compatibility_shim_exports_render_about_page() -> None:
    """handoff.ui shim re-exports render_about_page."""
    import handoff.ui as ui_module

    importlib.reload(ui_module)
    assert hasattr(ui_module, "render_about_page")
    assert callable(ui_module.render_about_page)


def test_handoff_ui_compatibility_shim_exports_render_system_settings_page() -> None:
    """handoff.ui shim re-exports render_system_settings_page."""
    import handoff.ui as ui_module

    importlib.reload(ui_module)
    assert hasattr(ui_module, "render_system_settings_page")
    assert callable(ui_module.render_system_settings_page)


def test_handoff_ui_all_export_list() -> None:
    """handoff.ui.__all__ lists all public exports."""
    import handoff.ui as ui_module

    importlib.reload(ui_module)
    assert hasattr(ui_module, "__all__")
    expected = {
        "setup",
        "render_projects_page",
        "render_dashboard_page",
        "render_about_page",
        "render_system_settings_page",
    }
    assert set(ui_module.__all__) == expected


def test_handoff_interfaces_streamlit_ui_setup_function() -> None:
    """Direct import of setup from canonical path handoff.interfaces.streamlit.ui."""
    from handoff.interfaces.streamlit.ui import setup

    assert callable(setup)


def test_handoff_interfaces_streamlit_ui_all_render_functions() -> None:
    """All render_*_page functions accessible from canonical path."""
    from handoff.interfaces.streamlit.ui import (
        render_about_page,
        render_dashboard_page,
        render_projects_page,
        render_system_settings_page,
    )

    assert all(
        callable(f)
        for f in [
            render_about_page,
            render_dashboard_page,
            render_projects_page,
            render_system_settings_page,
        ]
    )


def test_handoff_interfaces_streamlit_package_exports() -> None:
    """handoff.interfaces.streamlit.__init__ re-exports from canonical ui module."""
    import handoff.interfaces.streamlit as streamlit_pkg

    importlib.reload(streamlit_pkg)
    assert hasattr(streamlit_pkg, "setup")
    assert hasattr(streamlit_pkg, "render_projects_page")
    assert hasattr(streamlit_pkg, "render_dashboard_page")
    assert hasattr(streamlit_pkg, "render_about_page")
    assert hasattr(streamlit_pkg, "render_system_settings_page")


def test_handoff_interfaces_streamlit_all_export_list() -> None:
    """handoff.interfaces.streamlit.__all__ lists public exports."""
    import handoff.interfaces.streamlit as streamlit_pkg

    importlib.reload(streamlit_pkg)
    assert hasattr(streamlit_pkg, "__all__")
    expected = {
        "setup",
        "render_projects_page",
        "render_dashboard_page",
        "render_about_page",
        "render_system_settings_page",
    }
    assert set(streamlit_pkg.__all__) == expected


def test_handoff_ui_and_interfaces_streamlit_ui_setup_are_same() -> None:
    """The setup function accessible from both paths refers to same implementation."""
    from handoff.interfaces.streamlit.ui import setup as canonical_setup
    from handoff.ui import setup as compat_setup

    # Both should be the same underlying function
    assert compat_setup.__module__ == canonical_setup.__module__
    assert compat_setup.__name__ == canonical_setup.__name__


def test_handoff_ui_render_projects_page_delegates_to_impl() -> None:
    """render_projects_page delegates to internal _render_projects_page_impl."""
    with patch("handoff.interfaces.streamlit.ui._render_projects_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_projects_page

        render_projects_page()
        mock_impl.assert_called_once()


def test_handoff_ui_render_dashboard_page_delegates_to_impl() -> None:
    """render_dashboard_page delegates to internal _render_dashboard_page_impl."""
    with patch("handoff.interfaces.streamlit.ui._render_dashboard_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_dashboard_page

        render_dashboard_page()
        mock_impl.assert_called_once()


def test_handoff_ui_render_about_page_delegates_to_impl() -> None:
    """render_about_page delegates to internal _render_about_page_impl."""
    with patch("handoff.interfaces.streamlit.ui._render_about_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_about_page

        render_about_page()
        mock_impl.assert_called_once()


def test_handoff_ui_render_system_settings_page_delegates_to_impl() -> None:
    """render_system_settings_page delegates to internal _render_system_settings_page_impl."""
    with patch("handoff.interfaces.streamlit.ui._render_system_settings_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_system_settings_page

        render_system_settings_page()
        mock_impl.assert_called_once()


def test_handoff_ui_setup_succeeds_with_init_db_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """setup() succeeds when init_db() completes without error."""
    import handoff.interfaces.streamlit.ui as ui_module

    importlib.reload(ui_module)
    setup = ui_module.setup

    st_mock = MagicMock()
    init_db_mock = MagicMock()
    with (
        patch.object(ui_module, "st", st_mock),
        patch.object(ui_module, "init_db", init_db_mock),
        patch.object(ui_module, "configure_logging"),
    ):
        setup("1.0.0")

    st_mock.set_page_config.assert_called_once_with(
        page_title="Handoff", page_icon="📥", layout="centered"
    )
    init_db_mock.assert_called_once()
    st_mock.error.assert_not_called()
    st_mock.stop.assert_not_called()


def test_handoff_ui_setup_renders_error_message_with_correct_content(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When init_db fails, setup displays error message with actionable guidance."""
    import handoff.interfaces.streamlit.ui as ui_module

    importlib.reload(ui_module)
    setup = ui_module.setup

    from handoff.db import DatabaseInitializationError

    st_mock = MagicMock()
    init_db_mock = MagicMock(side_effect=DatabaseInitializationError("DB failed"))
    with (
        patch.object(ui_module, "st", st_mock),
        patch.object(ui_module, "init_db", init_db_mock),
        patch.object(ui_module, "configure_logging"),
    ):
        try:
            setup("1.0.0")
        except DatabaseInitializationError:
            pass

    st_mock.error.assert_called_once()
    error_message = st_mock.error.call_args[0][0]
    assert "could not be initialised" in error_message.lower()
    assert "write access" in error_message.lower()
    assert "HANDOFF_DB_PATH" in error_message


def test_import_from_handoff_interfaces_pages_submodules() -> None:
    """Pages can be imported from handoff.interfaces.streamlit.pages submodules."""
    from handoff.interfaces.streamlit.pages.about import render_about_page
    from handoff.interfaces.streamlit.pages.dashboard import render_dashboard_page
    from handoff.interfaces.streamlit.pages.projects import render_projects_page
    from handoff.interfaces.streamlit.pages.system_settings import (
        render_system_settings_page,
    )

    assert all(
        callable(f)
        for f in [
            render_about_page,
            render_dashboard_page,
            render_projects_page,
            render_system_settings_page,
        ]
    )


def test_app_py_imports_from_new_paths() -> None:
    """Verify app.py uses the new import paths (not the old ones)."""
    app_py_path = "/workspace/app.py"
    content = open(app_py_path).read()

    # Should import from new paths
    assert "from handoff.interfaces.streamlit.pages.now import" in content
    assert "from handoff.interfaces.streamlit.ui import" in content

    # Should NOT import from old paths
    assert "from handoff.pages" not in content
    assert "from handoff.ui import render_" not in content


def test_compatibility_shim_enables_gradual_migration() -> None:
    """Old code using handoff.ui.setup continues to work via compatibility shim."""
    # Simulate old code that used to import setup from handoff.ui
    import handoff.ui as old_style

    importlib.reload(old_style)
    # Should have setup without error
    assert hasattr(old_style, "setup")
    assert callable(old_style.setup)

    # New code can use the canonical path
    from handoff.interfaces.streamlit.ui import setup as new_style_setup

    # Both should work
    assert callable(old_style.setup)
    assert callable(new_style_setup)
