"""UAT tests against a seeded demo database.

Uses a fixed reference date so handoffs land in predictable Now buckets.
Exercises the checklist: Now sections, Conclude, Reopen, Add handoff,
Archived toggle, Dashboard.
"""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

import handoff.data as data
import handoff.db as db
from scripts.seed_demo import seed_demo_db

APP_TEST_TIMEOUT = 15
WORKSPACE = Path(__file__).resolve().parents[1]
REFERENCE_DATE = date(2026, 3, 1)


def _patch_date_today(monkeypatch: pytest.MonkeyPatch, ref: date) -> None:
    """Patch date.today() in modules used by the Now/Dashboard UI."""
    from datetime import date as real_date

    class FixedDate(real_date):
        @classmethod
        def today(cls) -> date:
            return ref

    for mod_name in (
        "handoff.data.handoffs",
        "handoff.data.queries",
        "handoff.services.handoff_service",
        "handoff.dates",
        "handoff.interfaces.streamlit.pages.now_helpers",
        "handoff.interfaces.streamlit.pages.now_forms",
        "handoff.interfaces.streamlit.pages.dashboard",
    ):
        mod = __import__(mod_name, fromlist=[""])
        monkeypatch.setattr(mod, "date", FixedDate)


def _reload_db_for_test(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point handoff.db at a test DB path and reload."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))
    db.dispose_db()
    importlib.reload(db)
    importlib.reload(__import__("handoff.interfaces.streamlit.ui", fromlist=[""]))
    importlib.reload(__import__("handoff.ui", fromlist=[""]))


@pytest.fixture
def seeded_uat_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Set up a temp DB, seed it with reference_date, and patch date.today()."""
    db_path = tmp_path / "uat_seeded.db"
    _reload_db_for_test(db_path, monkeypatch)
    seed_demo_db(db_path, force=True, reference_date=REFERENCE_DATE)
    _patch_date_today(monkeypatch, REFERENCE_DATE)
    return db_path


def _now_page_entry() -> None:
    import handoff.ui as ui
    from handoff.interfaces.streamlit.pages.now import render_now_page

    ui.setup("2026.2.24")
    render_now_page()


def _dashboard_page_entry() -> None:
    import handoff.ui as ui
    from handoff.interfaces.streamlit.pages.dashboard import render_dashboard_page

    ui.setup("2026.2.24")
    render_dashboard_page()


def test_uat_now_sections_render_with_seeded_items(seeded_uat_db: Path) -> None:
    """Risk, Action required, Upcoming, Concluded all render with expected seeded items."""
    db.init_db()
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    markdown_texts = [getattr(m, "value", str(m)) for m in at.get("markdown")]
    all_text = " ".join(mt or "" for mt in markdown_texts)
    assert "Risk" in all_text
    assert "Action" in all_text or "Action required" in all_text
    assert "Upcoming" in all_text
    assert "Concluded" in all_text

    expander_labels = [getattr(e, "label", str(e)) for e in at.get("expander")]
    all_labels = " ".join(expander_labels)
    assert "Overdue deliverable" in all_labels or "Due today" in all_labels
    assert "Concluded task" in all_labels


def test_uat_conclude_moves_handoff_to_concluded(seeded_uat_db: Path) -> None:
    """Conclude a specific handoff via UI; verify it moves to Concluded."""
    db.init_db()
    projects = data.list_projects(include_archived=False)
    acme = next((p for p in projects if p.name == "Acme Corp"), None)
    assert acme is not None
    handoffs = data.query_handoffs(project_ids=[acme.id], include_concluded=False)
    action_item = next((h for h in handoffs if h.need_back == "Action required item"), None)
    assert action_item is not None and action_item.id is not None

    at = AppTest.from_function(_now_page_entry)
    at.session_state[f"now_action_check_in_mode_{action_item.id}"] = "concluded"
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_buttons = [b for b in at.button if getattr(b, "label", None) == "Save conclude check-in"]
    assert save_buttons
    save_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    updated = next(
        (
            h
            for h in data.query_handoffs(project_ids=[acme.id], include_concluded=True)
            if h.id == action_item.id
        ),
        None,
    )
    assert updated is not None and not data.handoff_is_open(updated)


def test_uat_reopen_flow_available(seeded_uat_db: Path) -> None:
    """Concluded section shows Reopen button for handoffs.

    Full reopen flow is covered by test_app_integration.
    """
    db.init_db()
    concluded = [h.need_back for h in data.query_concluded_handoffs(project_ids=None)]
    assert "Concluded task" in concluded

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    reopen_buttons = [b for b in at.button if getattr(b, "label", None) == "Reopen"]
    assert reopen_buttons, "Expected Reopen button in Concluded section"
    assert len(at.exception) == 0


def test_uat_add_handoff_form_available(seeded_uat_db: Path) -> None:
    """Now page renders without error; add-handoff flow in test_app_integration."""
    db.init_db()
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1 or len(at.get("expander")) >= 1


def test_uat_archived_toggle_shows_archived_items(seeded_uat_db: Path) -> None:
    """Enable Include archived projects; verify archived items appear."""
    db.init_db()
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.toggle) >= 1
    at.toggle[0].set_value(True).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    labels = [getattr(e, "label", str(e)) for e in at.get("expander")]
    all_labels = " ".join(labels)
    assert "Archived project handoff" in all_labels or "Archived Project" in all_labels


def test_uat_dashboard_renders_with_seeded_data(seeded_uat_db: Path) -> None:
    """Dashboard renders without error with seeded data."""
    db.init_db()
    at = AppTest.from_function(_dashboard_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1
    assert len(at.get("metric")) >= 4
