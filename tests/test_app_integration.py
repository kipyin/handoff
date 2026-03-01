"""Streamlit AppTest integration tests for Handoff pages.

Each page is tested in isolation via AppTest.from_function() with a wrapper that
calls setup() and the page renderer. Uses a temporary DB path so tests do not
touch real user data.
"""

from __future__ import annotations

import importlib
from pathlib import Path

import pytest

from streamlit.testing.v1 import AppTest


def _reload_db_for_test(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point handoff.db at a test DB path and reload so the engine is recreated."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))
    import handoff.db as db  # noqa: F401

    importlib.reload(db)
    import handoff.ui as ui  # noqa: F401

    importlib.reload(ui)


@pytest.fixture
def app_test_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temporary DB path and reload handoff.db / ui so app uses it."""
    db_path = tmp_path / "handoff_test.db"
    _reload_db_for_test(db_path, monkeypatch)
    return db_path


def _todos_page_entry() -> None:
    """Single-page entrypoint for Todos: setup + render."""
    import handoff.ui as ui
    from handoff.pages.todos import render_todos_page

    ui.setup("2026.2.24")
    render_todos_page()


def _projects_page_entry() -> None:
    """Single-page entrypoint for Projects: setup + render."""
    import handoff.ui as ui
    from handoff.pages.projects import render_projects_page

    ui.setup("2026.2.24")
    render_projects_page()


def _calendar_page_entry() -> None:
    """Single-page entrypoint for Calendar: setup + render."""
    import handoff.ui as ui
    from handoff.pages.calendar import render_calendar_page

    ui.setup("2026.2.24")
    render_calendar_page()


def _settings_page_entry() -> None:
    """Single-page entrypoint for Settings: setup + render."""
    import handoff.ui as ui
    from handoff.pages.settings import render_settings_page

    ui.setup("2026.2.24")
    render_settings_page()


def test_todos_page_renders_with_app_test(app_test_db: Path) -> None:
    """Todos page renders (smoke test)."""
    at = AppTest.from_function(_todos_page_entry)
    at.run(timeout=5)
    # With no projects we get subheader + info; with projects we get data_editor
    assert len(at.get("subheader")) >= 1
    assert len(at.get("data_editor")) >= 0 or len(at.get("info")) >= 1


def test_projects_page_renders_with_app_test(app_test_db: Path) -> None:
    """Projects page renders create form (smoke test)."""
    at = AppTest.from_function(_projects_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("text_input")) >= 1 or len(at.get("info")) >= 1


def test_calendar_page_renders_with_app_test(app_test_db: Path) -> None:
    """Calendar page renders week navigation (smoke test)."""
    at = AppTest.from_function(_calendar_page_entry)
    at.run(timeout=5)
    assert len(at.get("button")) >= 2  # Previous week, Next week
    assert len(at.get("subheader")) >= 1 or len(at.get("info")) >= 1


def test_settings_page_renders_with_app_test(app_test_db: Path) -> None:
    """Settings page renders (smoke test)."""
    at = AppTest.from_function(_settings_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("markdown")) >= 1
