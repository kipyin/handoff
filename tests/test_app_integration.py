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

# AppTest can be slow on Windows CI; use higher timeout for CI resilience.
APP_TEST_TIMEOUT = 15

WORKSPACE = Path(__file__).resolve().parents[1]


def _reload_db_for_test(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point handoff.db at a test DB path and reload so the engine is recreated."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))

    import handoff.db as db

    db.dispose_db()  # close any existing engine before reload
    importlib.reload(db)
    import handoff.ui as ui

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
    at.run(timeout=APP_TEST_TIMEOUT)
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
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    assert len(at.checkbox) >= 1

    importlib.reload(models)
    at.checkbox[0].check().run(timeout=APP_TEST_TIMEOUT)

    assert len(at.exception) == 0
    assert at.checkbox[0].value is True
    assert len(at.get("subheader")) >= 1


def test_system_settings_page_renders_with_app_test(app_test_db: Path) -> None:
    """System Settings page renders (smoke test)."""
    at = AppTest.from_function(_system_settings_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("markdown")) >= 1


def test_dashboard_page_renders_with_app_test(app_test_db: Path) -> None:
    """Dashboard page renders metrics (smoke test)."""
    at = AppTest.from_function(_dashboard_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("metric")) >= 4


def test_about_page_renders_with_app_test(app_test_db: Path) -> None:
    """About page renders (smoke test)."""
    at = AppTest.from_function(_about_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.get("subheader")) >= 1
    assert len(at.get("tabs")) >= 1 or len(at.get("markdown")) >= 1


def test_now_page_renders_with_app_test(app_test_db: Path) -> None:
    """Now page renders (smoke test). With no projects, shows info message."""
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
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
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1
    assert len(at.get("expander")) >= 1


def test_now_page_default_rulebook_sections_match_legacy(app_test_db: Path) -> None:
    """Default rulebook produces correct section membership on the Now page (parity integration)."""
    today = date.today()
    db.init_db()
    project = data.create_project("Parity Test")
    assert project.id is not None

    # Risk: due + near deadline + delayed check-in
    risk_h = data.create_handoff(
        project_id=project.id,
        need_back="Risk item",
        next_check=date(2000, 1, 1),
        deadline=add_business_days(today, 1),
        pitchman="R",
    )
    data.create_check_in(
        handoff_id=risk_h.id,
        check_in_type=data.CheckInType.DELAYED,
        check_in_date=today,
    )

    # Action: due, not risk (deadline far, no delayed)
    data.create_handoff(
        project_id=project.id,
        need_back="Action item",
        next_check=date(2000, 1, 1),
        deadline=add_business_days(today, 30),
        pitchman="A",
    )

    # Upcoming: future next_check
    data.create_handoff(
        project_id=project.id,
        need_back="Upcoming item",
        next_check=add_business_days(today, 10),
        pitchman="U",
    )

    # Concluded
    concluded_h = data.create_handoff(
        project_id=project.id,
        need_back="Concluded item",
        next_check=date(2000, 1, 1),
        pitchman="C",
    )
    data.conclude_handoff(concluded_h.id, note="Done")

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    markdown_texts = [getattr(m, "value", str(m)) for m in at.get("markdown")]
    expander_labels = [getattr(e, "label", str(e)) for e in at.get("expander")]

    # Section headers appear
    assert any("Risk" in (mt or "") for mt in markdown_texts)
    assert any("Action" in (mt or "") for mt in markdown_texts)
    assert any("Upcoming" in (mt or "") for mt in markdown_texts)
    assert any("Concluded" in (mt or "") for mt in markdown_texts)

    # All four items appear as expanders (default rulebook sectioning)
    assert len(expander_labels) >= 4
    all_labels = " ".join(expander_labels)
    assert "Risk item" in all_labels
    assert "Action item" in all_labels
    assert "Upcoming item" in all_labels
    assert "Concluded item" in all_labels


def test_now_page_conclude_button_closes_handoff(app_test_db: Path) -> None:
    """Conclude flow on a due action item adds a concluded check-in.

    Due action items (next_check in the past) use a two-step check-in form:
    1. Click "Conclude" to enter concluded mode.
    2. Submit "Save conclude check-in" to persist and close the handoff.
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
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Select "Conclude" from check-in segmented control via set_value.
    button_groups = at.get("button_group")
    assert button_groups, "Expected check-in segmented control not found"
    button_groups[0].set_value(["concluded"]).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # After selecting Conclude, a save form appears.
    save_buttons = [b for b in at.button if getattr(b, "label", None) == "Save conclude check-in"]
    assert save_buttons, "Expected 'Save conclude check-in' button not found"
    save_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Handoff should no longer be open (concluded check-in was persisted).
    handoffs = data.query_handoffs(project_ids=[project.id], include_concluded=True)
    updated = next((h for h in handoffs if h.id == handoff.id), None)
    assert updated is not None
    assert not data.handoff_is_open(updated)


def test_now_page_conclude_then_reopen_moves_item_out_of_concluded(app_test_db: Path) -> None:
    """Conclude then reopen flow moves an item back to the open sections."""
    db.init_db()
    project = data.create_project("Now Reopen Test")
    assert project.id is not None
    handoff = data.create_handoff(
        project_id=project.id,
        need_back="Conclude and reopen this handoff",
        next_check=date(2000, 1, 1),
        pitchman="Jordan",
    )
    assert handoff.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Select "Conclude" from check-in segmented control.
    button_groups = at.get("button_group")
    assert button_groups, "Expected check-in segmented control not found"
    button_groups[0].set_value(["concluded"]).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_conclude_buttons = [
        b for b in at.button if getattr(b, "label", None) == "Save conclude check-in"
    ]
    assert save_conclude_buttons, "Expected 'Save conclude check-in' button not found"
    save_conclude_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    reopen_buttons = [b for b in at.button if getattr(b, "label", None) == "Reopen"]
    assert reopen_buttons, "Expected Reopen button not found in Concluded section"
    reopen_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_reopen_buttons = [b for b in at.button if getattr(b, "label", None) == "Save reopen"]
    assert save_reopen_buttons, "Expected 'Save reopen' button not found"
    save_reopen_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    handoffs = data.query_handoffs(project_ids=[project.id], include_concluded=True)
    updated = next((h for h in handoffs if h.id == handoff.id), None)
    assert updated is not None
    assert data.handoff_is_open(updated)

    concluded_names = [h.need_back for h in data.query_concluded_handoffs(project_ids=[project.id])]
    assert "Conclude and reopen this handoff" not in concluded_names


def test_now_page_due_check_in_records_today_and_updates_next_check(app_test_db: Path) -> None:
    """Late (due) check-in records today's check-in date."""
    today = date.today()
    expected_next_check = add_business_days(today, 1)
    db.init_db()
    project = data.create_project("Now Due Check-in Test")
    assert project.id is not None
    handoff = data.create_handoff(
        project_id=project.id,
        need_back="Due check-in should use today",
        next_check=date(2000, 1, 1),
        pitchman="Jamie",
    )
    assert handoff.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Select "On-track" from check-in segmented control.
    button_groups = at.get("button_group")
    assert button_groups, "Expected check-in segmented control not found"
    button_groups[0].set_value(["on_track"]).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_buttons = [b for b in at.button if getattr(b, "label", None) == "Save check-in"]
    assert save_buttons, "Expected 'Save check-in' button not found"
    save_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    updated = next(
        h
        for h in data.query_handoffs(project_ids=[project.id], include_concluded=True)
        if h.id == handoff.id
    )
    latest = max(updated.check_ins, key=lambda ci: (ci.check_in_date, ci.created_at, ci.id or 0))
    assert latest.check_in_type == data.CheckInType.ON_TRACK
    assert latest.check_in_date == today
    assert updated.next_check == expected_next_check


def test_now_page_early_check_in_records_today_and_keeps_planned_next_check(
    app_test_db: Path,
) -> None:
    """Early (not due yet) check-in still records today's check-in date."""
    today = date.today()
    db.init_db()
    project = data.create_project("Now Early Check-in Test")
    assert project.id is not None
    planned_next_check = add_business_days(today, 5)
    handoff = data.create_handoff(
        project_id=project.id,
        need_back="Early check-in should use today",
        next_check=planned_next_check,
        pitchman="Morgan",
    )
    assert handoff.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Select "On-track" from check-in segmented control (upcoming uses first button_group).
    button_groups = at.get("button_group")
    assert button_groups, "Expected check-in segmented control not found"
    button_groups[0].set_value(["on_track"]).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_buttons = [b for b in at.button if getattr(b, "label", None) == "Save check-in"]
    assert save_buttons, "Expected 'Save check-in' button not found"
    save_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    updated = next(
        h
        for h in data.query_handoffs(project_ids=[project.id], include_concluded=True)
        if h.id == handoff.id
    )
    latest = max(updated.check_ins, key=lambda ci: (ci.check_in_date, ci.created_at, ci.id or 0))
    assert latest.check_in_type == data.CheckInType.ON_TRACK
    assert latest.check_in_date == today
    assert updated.next_check == planned_next_check


def test_now_page_archived_toggle_allows_reopen_under_latest_lifecycle(app_test_db: Path) -> None:
    """Archived concluded handoffs are reopenable only when archived toggle is enabled."""
    db.init_db()
    active = data.create_project("Active")
    archived = data.create_project("Archived")
    assert active.id is not None
    assert archived.id is not None
    assert data.archive_project(archived.id) is True

    data.create_handoff(
        project_id=active.id,
        need_back="Active open handoff",
        next_check=date(2000, 1, 1),
        pitchman="Alex",
    )
    archived_handoff = data.create_handoff(
        project_id=archived.id,
        need_back="Archived concluded handoff",
        next_check=date(2000, 1, 1),
        pitchman="Taylor",
    )
    assert archived_handoff.id is not None
    data.conclude_handoff(archived_handoff.id, note="Done in archived project")

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    assert not [b for b in at.button if getattr(b, "label", None) == "Reopen"]

    assert len(at.toggle) >= 1
    at.toggle[0].set_value(True).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    reopen_buttons = [b for b in at.button if getattr(b, "label", None) == "Reopen"]
    assert reopen_buttons, "Expected Reopen button once archived projects are included"
    reopen_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_reopen_buttons = [b for b in at.button if getattr(b, "label", None) == "Save reopen"]
    assert save_reopen_buttons, "Expected Save reopen button after clicking Reopen"
    save_reopen_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    archived_concluded_names = [
        h.need_back
        for h in data.query_concluded_handoffs(
            project_ids=[archived.id],
            include_archived_projects=True,
        )
    ]
    assert "Archived concluded handoff" not in archived_concluded_names

    archived_open_names = [
        h.need_back
        for h in data.query_upcoming_handoffs(
            project_ids=[archived.id],
            include_archived_projects=True,
        )
    ]
    assert "Archived concluded handoff" in archived_open_names


def test_now_page_add_form_creates_handoff(app_test_db: Path) -> None:
    """Submitting the Add handoff form creates a new handoff."""
    db.init_db()
    project = data.create_project("Add Form Test")
    assert project.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Expand add form (shortcut target button when collapsed)
    add_handoff_buttons = [b for b in at.button if "Add handoff" in getattr(b, "label", "")]
    assert add_handoff_buttons, "Expected Add handoff button not found on Now page"
    add_handoff_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    need_back_inputs = [
        ti
        for ti in at.text_input
        if getattr(ti, "key", None) == "now_add_need" or getattr(ti, "label", None) == "Need back"
    ]
    assert need_back_inputs, "Expected Need back text input not found on Now page"
    need_back_inputs[0].input("New handoff from add form").run(timeout=APP_TEST_TIMEOUT)

    add_buttons = [b for b in at.button if getattr(b, "label", None) == "Add"]
    assert add_buttons, "Expected Add button not found on Now page"
    add_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    handoffs = data.query_handoffs(project_ids=[project.id], include_concluded=True)
    created = next((h for h in handoffs if h.need_back == "New handoff from add form"), None)
    assert created is not None


def test_dashboard_page_pm_metrics_smoke_with_seed_data(app_test_db: Path) -> None:
    """Dashboard renders PM cards for seeded lifecycle data."""
    db.init_db()
    project = data.create_project("Dashboard PM Test")
    assert project.id is not None
    today = date.today()

    risk = data.create_handoff(
        project_id=project.id,
        need_back="Risk handoff",
        next_check=today,
        deadline=today,
        pitchman="R1",
    )
    overdue = data.create_handoff(
        project_id=project.id,
        need_back="Overdue action",
        next_check=add_business_days(today, -1),
        pitchman="R2",
    )
    due_today = data.create_handoff(
        project_id=project.id,
        need_back="Due today action",
        next_check=today,
        pitchman="R3",
    )
    reopened = data.create_handoff(
        project_id=project.id,
        need_back="Recently reopened",
        next_check=today,
        pitchman="R4",
    )
    assert all(h.id is not None for h in [risk, overdue, due_today, reopened])

    data.create_check_in(
        handoff_id=risk.id,
        check_in_type=data.CheckInType.DELAYED,
        check_in_date=today,
    )
    data.conclude_handoff(reopened.id, note="initial conclude")
    data.reopen_handoff(
        reopened.id, note="reopen for follow-up", next_check_date=add_business_days(today, 1)
    )

    at = AppTest.from_function(_dashboard_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    metric_labels = [getattr(metric, "label", None) for metric in at.metric]
    assert "At risk now" in metric_labels
    assert "Action overdue" in metric_labels
    assert "Open handoffs" in metric_labels
    assert "Reopen rate (90d)" in metric_labels


def test_full_app_loads_with_app_test(app_test_db: Path) -> None:
    """Full app (app.py with st.navigation) loads without exception."""
    at = AppTest.from_file(str(WORKSPACE / "app.py"))
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1 or len(at.get("info")) >= 1


def test_projects_create_form_submit_no_error(app_test_db: Path) -> None:
    """Submitting the create-project form does not raise."""
    at = AppTest.from_function(_projects_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    project_name_inputs = [
        ti
        for ti in at.text_input
        if getattr(ti, "key", None) == "projects_new_project_name"
        or getattr(ti, "label", None) == "Project name"
    ]
    assert project_name_inputs, "Expected project-name text input not found on Projects page"
    project_name_inputs[0].input("TestProjectFromForm").run(timeout=APP_TEST_TIMEOUT)

    create_btns = [b for b in at.button if getattr(b, "label", None) == "Create"]
    assert create_btns, "Expected Create button not found on Projects page"
    create_btns[0].click().run(timeout=APP_TEST_TIMEOUT)

    assert len(at.exception) == 0


def test_about_page_tab_switch_no_error(app_test_db: Path) -> None:
    """Switching About page tabs (README / Release notes) does not raise."""
    at = AppTest.from_function(_about_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    tabs = at.tabs
    assert len(tabs) == 2, f"Expected exactly 2 tabs on About page, got {len(tabs)}"
    tabs[1].run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
