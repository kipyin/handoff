"""Streamlit AppTest integration tests for Handoff pages.

Each page is tested in isolation via AppTest.from_function() with a wrapper that
calls setup() and the page renderer. Uses a temporary DB path so tests do not
touch real user data.

Also includes full-app load and programmatic UI interaction tests to verify
no errors when clicking around different elements.
"""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import handoff.data as data
import handoff.db as db
from handoff.dates import add_business_days
from handoff.services import snooze_handoff

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


def _projects_page_entry() -> None:
    """Single-page entrypoint for Projects: setup + render."""
    import handoff.ui as ui
    from handoff.pages.projects import render_projects_page

    ui.setup("2026.2.24")
    render_projects_page()


def _system_settings_page_entry() -> None:
    """Single-page entrypoint for System Settings: setup + render."""
    import handoff.ui as ui
    from handoff.pages.system_settings import render_system_settings_page

    ui.setup("2026.2.24")
    render_system_settings_page()


def _dashboard_page_entry() -> None:
    """Single-page entrypoint for Dashboard: setup + render."""
    import handoff.ui as ui
    from handoff.pages.dashboard import render_dashboard_page

    ui.setup("2026.2.24")
    render_dashboard_page()


def _about_page_entry() -> None:
    """Single-page entrypoint for About: setup + render."""
    import handoff.ui as ui
    from handoff.pages.about import render_about_page

    ui.setup("2026.2.24")
    render_about_page()


def _now_page_entry() -> None:
    """Single-page entrypoint for Now: setup + render."""
    import handoff.ui as ui
    from handoff.pages.now import render_now_page

    ui.setup("2026.2.24")
    render_now_page()


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


def test_system_settings_page_renders_with_app_test(app_test_db: Path) -> None:
    """System Settings page renders (smoke test)."""
    at = AppTest.from_function(_system_settings_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("markdown")) >= 1


def test_dashboard_page_renders_with_app_test(app_test_db: Path) -> None:
    """Dashboard page renders metrics (smoke test)."""
    at = AppTest.from_function(_dashboard_page_entry)
    at.run(timeout=5)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("metric")) >= 4


def test_about_page_renders_with_app_test(app_test_db: Path) -> None:
    """About page renders (smoke test)."""
    at = AppTest.from_function(_about_page_entry)
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
    """Now page shows items when project + handoff exist with next_check due."""
    db.init_db()
    project = data.create_project("Test Project")
    assert project.id is not None
    data.create_handoff(
        project_id=project.id,
        need_back="Follow up with Alice",
        next_check=date(2000, 1, 1),
        pitchman="Alice",
    )
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1
    assert len(at.get("expander")) >= 1


def test_now_page_conclude_button_closes_handoff(app_test_db: Path) -> None:
    """Conclude flow on a due action item adds a concluded check-in.

    Due action items (next_check in the past) use a two-step check-in form:
    1. Click "Conclude" to enter concluded mode.
    2. Submit "Save conclude check-in" to persist and close the handoff.

    Note: the quick "✓ Conclude" button lives inside a st.popover (Actions),
    which Streamlit's AppTest v1 does not expose; that path is covered by the
    unit tests in test_pages_now.py instead.
    """
    db.init_db()
    project = data.create_project("Now Conclude Test")
    assert project.id is not None
    handoff = data.create_handoff(
        project_id=project.id,
        need_back="Conclude this handoff",
        next_check=date(2000, 1, 1),
        pitchman="Alex",
    )
    assert handoff.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    # Due action items show "On-track / Delayed / Conclude" buttons in-line
    # (not in a popover) via _render_due_check_in_flow.
    conclude_buttons = [b for b in at.button if getattr(b, "label", None) == "Conclude"]
    assert conclude_buttons, "Expected Conclude button not found on Now page"
    conclude_buttons[0].click().run(timeout=5)
    assert len(at.exception) == 0

    # After clicking Conclude, a save form appears.
    save_buttons = [b for b in at.button if getattr(b, "label", None) == "Save conclude check-in"]
    assert save_buttons, "Expected 'Save conclude check-in' button not found"
    save_buttons[0].click().run(timeout=5)
    assert len(at.exception) == 0

    # Handoff should no longer be open (concluded check-in was persisted).
    handoffs = data.query_handoffs(project_ids=[project.id], include_concluded=True)
    updated = next((h for h in handoffs if h.id == handoff.id), None)
    assert updated is not None
    assert not data.handoff_is_open(updated)


def test_now_page_snooze_updates_next_check(app_test_db: Path) -> None:
    """Snooze updates a handoff's next_check date.

    The "Snooze" button lives inside a st.popover (Actions), which
    Streamlit's AppTest v1 does not expose.  This test therefore verifies the
    service-layer path directly: the Now page renders cleanly when the handoff
    is in the upcoming section, and snooze_handoff() updates the DB.
    """
    db.init_db()
    project = data.create_project("Now Snooze Test")
    assert project.id is not None
    handoff = data.create_handoff(
        project_id=project.id,
        need_back="Snooze this handoff",
        next_check=add_business_days(date.today(), 5),
        pitchman="Riley",
    )
    assert handoff.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0
    # The handoff appears in the upcoming section (next_check is in the future).
    assert len(at.get("expander")) >= 1

    # Simulate what the Snooze button would do via the service boundary.
    snooze_target = add_business_days(date.today(), 1)
    updated = snooze_handoff(handoff.id, to_date=snooze_target)
    assert updated is not None
    assert updated.next_check == snooze_target


def test_now_page_add_form_creates_handoff(app_test_db: Path) -> None:
    """Submitting the Add handoff form creates a new handoff."""
    db.init_db()
    project = data.create_project("Add Form Test")
    assert project.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    need_back_inputs = [
        ti
        for ti in at.text_input
        if getattr(ti, "key", None) == "now_add_need" or getattr(ti, "label", None) == "Need back"
    ]
    assert need_back_inputs, "Expected Need back text input not found on Now page"
    need_back_inputs[0].input("New handoff from add form").run(timeout=5)

    add_buttons = [b for b in at.button if getattr(b, "label", None) == "Add"]
    assert add_buttons, "Expected Add button not found on Now page"
    add_buttons[0].click().run(timeout=5)
    assert len(at.exception) == 0

    handoffs = data.query_handoffs(project_ids=[project.id], include_concluded=True)
    created = next((h for h in handoffs if h.need_back == "New handoff from add form"), None)
    assert created is not None


def test_full_app_loads_with_app_test(app_test_db: Path) -> None:
    """Full app (app.py with st.navigation) loads without exception."""
    at = AppTest.from_file(str(WORKSPACE / "app.py"))
    at.run(timeout=5)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1 or len(at.get("info")) >= 1


def test_projects_create_form_submit_no_error(app_test_db: Path) -> None:
    """Submitting the create-project form does not raise."""
    at = AppTest.from_function(_projects_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

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


def test_about_page_tab_switch_no_error(app_test_db: Path) -> None:
    """Switching About page tabs (README / Release notes) does not raise."""
    at = AppTest.from_function(_about_page_entry)
    at.run(timeout=5)
    assert len(at.exception) == 0

    tabs = at.tabs
    assert len(tabs) == 2, f"Expected exactly 2 tabs on About page, got {len(tabs)}"
    tabs[1].run(timeout=5)
    assert len(at.exception) == 0
