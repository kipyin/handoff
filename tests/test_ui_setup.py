"""Tests for UI setup and render entrypoints."""

from __future__ import annotations

from contextlib import suppress
from unittest.mock import MagicMock, patch

import pytest


def test_setup_calls_st_error_and_st_stop_when_init_db_raises(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When init_db raises DatabaseInitializationError, setup shows error and stops."""
    import importlib

    import handoff.interfaces.streamlit.ui as ui_module
    from handoff.db import DatabaseInitializationError

    # Reload to clear any state from prior tests that might use a different st reference
    importlib.reload(ui_module)
    setup = ui_module.setup

    # Ensure no test DB from other tests; use a path that will not exist
    monkeypatch.setenv("HANDOFF_DB_PATH", "/nonexistent/path/handoff.db")

    st_mock = MagicMock()
    init_db_mock = MagicMock(side_effect=DatabaseInitializationError("DB failed"))
    with (
        patch.object(ui_module, "init_db", init_db_mock),
        patch.object(ui_module, "st", st_mock),
        patch.object(ui_module, "configure_logging"),
        suppress(DatabaseInitializationError),
    ):
        setup("1.0.0")  # st.stop() may raise; error path was still taken
    init_db_mock.assert_called_once()
    st_mock.error.assert_called_once()
    assert "could not be initialised" in st_mock.error.call_args[0][0].lower()
    st_mock.stop.assert_called_once()


def test_render_projects_page_calls_impl() -> None:
    """render_projects_page delegates to the projects page implementation."""
    with patch("handoff.interfaces.streamlit.ui._render_projects_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_projects_page

        render_projects_page()
    mock_impl.assert_called_once()


def test_render_dashboard_page_calls_impl() -> None:
    """render_dashboard_page delegates to the dashboard page implementation."""
    with patch("handoff.interfaces.streamlit.ui._render_dashboard_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_dashboard_page

        render_dashboard_page()
    mock_impl.assert_called_once()


def test_render_system_settings_page_calls_impl() -> None:
    """render_system_settings_page delegates to the System Settings page implementation."""
    with patch("handoff.interfaces.streamlit.ui._render_system_settings_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_system_settings_page

        render_system_settings_page()
    mock_impl.assert_called_once()


def test_render_about_page_calls_impl() -> None:
    """render_about_page delegates to the About page implementation."""
    with patch("handoff.interfaces.streamlit.ui._render_about_page_impl") as mock_impl:
        from handoff.interfaces.streamlit.ui import render_about_page

        render_about_page()
    mock_impl.assert_called_once()
