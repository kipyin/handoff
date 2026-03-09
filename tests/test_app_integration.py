"""Streamlit AppTest integration tests for Handoff pages.

Each page is tested in isolation via AppTest.from_function() with a wrapper that
calls setup() and the page renderer. Uses a temporary DB path so tests do not
touch real user data.

Also includes full-app load and programmatic UI interaction tests to verify
no errors when clicking around different elements.
"""

from __future__ import annotations

import importlib
from datetime import date, timedelta
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import handoff.data as data
import handoff.db as db
from handoff.models import TodoStatus

WORKSPACE = Path(__file__).resolve().parents[1]


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
    assert len(at.get("info")) >= 1
    assert len(at.get("expander")) == 0


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


def test_now_page_close_button_marks_todo_done(app_test_db: Path) -> None:
    """Clicking Close on a Now item marks it done."""
    db.init_db()
    project = data.create_project("Now Close Test")
    assert project.id is not None
    todo = data.create_todo(
        project_id=project.id,
        name="Close this handoff",
        next_check=date(2000, 1, 1),
        helper="Alex",
    )
    assert todo.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    close_buttons = [b for b in at.button if getattr(b, "label", None) == "✓ Close"]
    assert close_buttons, "Expected Close button not found on Now page"
    close_buttons[0].click().run(timeout=5)
    assert len(at.exception) == 0

    todos = data.query_todos(project_ids=[project.id])
    updated = next((t for t in todos if t.id == todo.id), None)
    assert updated is not None
    assert updated.status == TodoStatus.DONE
    assert updated.completed_at is not None


def test_now_page_snooze_plus_one_day_updates_next_check(app_test_db: Path) -> None:
    """Clicking +1d snooze updates the todo next_check date."""
    db.init_db()
    project = data.create_project("Now Snooze Test")
    assert project.id is not None
    todo = data.create_todo(
        project_id=project.id,
        name="Snooze this handoff",
        next_check=date(2000, 1, 1),
        helper="Riley",
    )
    assert todo.id is not None
    start_today = date.today()

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    plus_one_buttons = [b for b in at.button if getattr(b, "label", None) == "+1d"]
    assert plus_one_buttons, "Expected +1d snooze button not found on Now page"
    plus_one_buttons[0].click().run(timeout=5)
    assert len(at.exception) == 0

    todos = data.query_todos(project_ids=[project.id])
    updated = next((t for t in todos if t.id == todo.id), None)
    assert updated is not None
    expected_dates = {start_today + timedelta(days=1), date.today() + timedelta(days=1)}
    assert updated.next_check in expected_dates
    assert updated.status == TodoStatus.HANDOFF


def test_full_app_loads_with_app_test(app_test_db: Path) -> None:
    """Full app (app.py with st.navigation) loads without exception."""
    at = AppTest.from_file(str(WORKSPACE / "app.py"))
    at.run(timeout=5)
    assert len(at.exception) == 0
    # First page (Todos) should render; we expect at least a subheader or info
    assert len(at.get("subheader")) >= 1 or len(at.get("info")) >= 1


def test_projects_create_form_submit_no_error(app_test_db: Path) -> None:
    """Submitting the create-project form does not raise."""
    at = AppTest.from_function(_projects_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    # Fill project name and submit. The Projects page always renders a project-name
    # text input and a Create submit button. Target them by label/key so the test
    # fails if the UI contract breaks.
    project_name_inputs = [
        ti
        for ti in at.text_input
        if getattr(ti, "key", None) == "projects_new_project_name"
        or getattr(ti, "label", None) == "Project name"
    ]
    assert project_name_inputs, "Expected project-name text input not found on Projects page"
    project_name_inputs[0].input("TestProjectFromForm").run(timeout=5)

    create_btns = [b for b in at.button if getattr(b, "label", None) == "Create"]
    assert create_btns, "Expected Create button not found on Projects page"
    create_btns[0].click().run(timeout=5)

    assert len(at.exception) == 0


def test_todos_page_filter_selectbox_interaction_no_error(app_test_db: Path) -> None:
    """Changing deadline filter selectbox does not raise."""
    import handoff.data as data
    import handoff.db as db

    db.init_db()
    proj = data.create_project("Proj")
    assert proj.id is not None
    data.create_todo(proj.id, "Task", status="handoff")

    at = AppTest.from_function(_todos_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    # Interact with deadline filter selectbox; it should always be present once a
    # project exists.
    selectboxes = at.selectbox
    assert selectboxes, "Expected at least one selectbox on Todos page"
    deadline_box = next(
        (sb for sb in selectboxes if getattr(sb, "label", None) == "Deadline"),
        selectboxes[0],
    )
    deadline_box.select("Overdue").run(timeout=5)

    assert len(at.exception) == 0


def test_docs_page_tab_switch_no_error(app_test_db: Path) -> None:
    """Switching docs page tabs (README / Release notes) does not raise."""
    at = AppTest.from_function(_docs_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    tabs = at.tabs
    assert len(tabs) == 2, f"Expected exactly 2 tabs on Docs page, got {len(tabs)}"
    tabs[1].run(timeout=5)  # Switch to Release notes tab
    assert len(at.exception) == 0
