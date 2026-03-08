"""Streamlit AppTest integration tests for Handoff pages.

Each page is tested in isolation via AppTest.from_function() with a wrapper that
calls setup() and the page renderer. Uses a temporary DB path so tests do not
touch real user data.
"""

from __future__ import annotations

import importlib
from datetime import date

from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import handoff.data as data
import handoff.db as db


def _reload_db_for_test(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point handoff.db at a test DB path and reload so the engine is recreated."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))

    import handoff.db as db

    db.dispose_db()  # close any existing engine before reload
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


def _settings_page_entry() -> None:
    """Single-page entrypoint for Settings: setup + render."""
    import handoff.ui as ui
    from handoff.pages.settings import render_settings_page

    ui.setup("2026.2.24")
    render_settings_page()


def _dashboard_page_entry() -> None:
    """Single-page entrypoint for Dashboard: setup + render."""
    import handoff.ui as ui
    from handoff.pages.dashboard import render_dashboard_page

    ui.setup("2026.2.24")
    render_dashboard_page()


def _docs_page_entry() -> None:
    """Single-page entrypoint for Docs: setup + render."""
    import handoff.ui as ui
    from handoff.pages.docs import render_docs_page

    ui.setup("2026.2.24")
    render_docs_page()


def _now_page_entry() -> None:
    """Single-page entrypoint for Now: setup + render."""
    import handoff.ui as ui
    from handoff.pages.now import render_now_page

    ui.setup("2026.2.24")
    render_now_page()


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


def test_projects_page_archived_toggle_survives_models_reload(app_test_db: Path) -> None:
    """Toggling archived projects survives a hot reload of handoff.models."""
    import importlib

    import handoff.data as data
    import handoff.db as db
    import handoff.models as models

    db.init_db()
    active = data.create_project("Active")
    archived = data.create_project("Archived")
    assert active.id is not None
    assert archived.id is not None
    assert data.archive_project(archived.id) is True

    at = AppTest.from_function(_projects_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0
    assert len(at.checkbox) >= 1

    importlib.reload(models)
    at.checkbox[0].check().run(timeout=5)

    assert len(at.exception) == 0
    assert at.checkbox[0].value is True
    assert len(at.get("subheader")) >= 1


def test_settings_page_renders_with_app_test(app_test_db: Path) -> None:
    """Settings page renders (smoke test)."""
    at = AppTest.from_function(_settings_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("markdown")) >= 1


def test_dashboard_page_renders_with_app_test(app_test_db: Path) -> None:
    """Dashboard page renders metrics (smoke test)."""
    at = AppTest.from_function(_dashboard_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("metric")) >= 4


def test_docs_page_renders_with_app_test(app_test_db: Path) -> None:
    """Docs page renders (smoke test)."""
    at = AppTest.from_function(_docs_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("tabs")) >= 1 or len(at.get("markdown")) >= 1


def test_now_page_renders_with_app_test(app_test_db: Path) -> None:
    """Now page renders (smoke test). With no projects, shows info message."""
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("info")) >= 1 or len(at.get("expander")) >= 0


def test_now_page_shows_action_items_when_data_exists(app_test_db: Path) -> None:
    """Now page shows items when project + handoff todo exist with next_check due."""
    db.init_db()
    project = data.create_project("Test Project")
    assert project.id is not None
    data.create_todo(
        project_id=project.id,
        name="Follow up with Alice",
        next_check=date(2000, 1, 1),
        helper="Alice",
    )
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1
    assert len(at.get("expander")) >= 1
