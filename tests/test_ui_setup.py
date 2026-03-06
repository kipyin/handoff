"""Tests for UI setup and render entrypoints."""

from __future__ import annotations

from unittest.mock import MagicMock, patch


def test_setup_calls_st_error_and_st_stop_when_init_db_raises() -> None:
    """When init_db raises DatabaseInitializationError, setup shows error and stops."""
    import handoff.ui as ui

    st_mock = MagicMock()
    err = ui.DatabaseInitializationError("DB failed")
    with (
        patch("handoff.ui.init_db", side_effect=err),
        patch("handoff.ui.st", st_mock),
        patch("handoff.ui.configure_logging"),
    ):
        try:
            ui.setup("1.0.0")
        except type(err):
            pass  # st.stop() may raise; error path was still taken
    st_mock.error.assert_called_once()
    assert "could not be initialised" in st_mock.error.call_args[0][0].lower()
    st_mock.stop.assert_called_once()


def test_render_todos_page_calls_impl() -> None:
    """render_todos_page delegates to the todos page implementation."""
    with patch("handoff.ui._render_todos_page_impl") as mock_impl:
        import handoff.ui as ui

        ui.render_todos_page()
    mock_impl.assert_called_once()


def test_render_projects_page_calls_impl() -> None:
    """render_projects_page delegates to the projects page implementation."""
    with patch("handoff.ui._render_projects_page_impl") as mock_impl:
        import handoff.ui as ui

        ui.render_projects_page()
    mock_impl.assert_called_once()


def test_render_calendar_page_calls_impl() -> None:
    """render_calendar_page delegates to the calendar page implementation."""
    with patch("handoff.ui._render_calendar_page_impl") as mock_impl:
        import handoff.ui as ui

        ui.render_calendar_page()
    mock_impl.assert_called_once()


def test_render_analytics_page_calls_impl() -> None:
    """render_analytics_page delegates to the analytics page implementation."""
    with patch("handoff.ui._render_analytics_page_impl") as mock_impl:
        import handoff.ui as ui

        ui.render_analytics_page()
    mock_impl.assert_called_once()


def test_render_settings_page_calls_impl() -> None:
    """render_settings_page delegates to the settings page implementation."""
    with patch("handoff.ui._render_settings_page_impl") as mock_impl:
        import handoff.ui as ui

        ui.render_settings_page()
    mock_impl.assert_called_once()


def test_render_docs_page_calls_impl() -> None:
    """render_docs_page delegates to the docs page implementation."""
    with patch("handoff.ui._render_docs_page_impl") as mock_impl:
        import handoff.ui as ui

        ui.render_docs_page()
    mock_impl.assert_called_once()
