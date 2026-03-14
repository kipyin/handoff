"""UAT tests for the seeded demo database workflow.

Each test exercises one item from the PR-5 checklist using the ``seeded_uat_db``
fixture which provides a deterministically seeded DB with a pinned reference date
of 2026-03-09 (Monday).
"""

from __future__ import annotations

import importlib
from datetime import date
from pathlib import Path

import pytest
from streamlit.testing.v1 import AppTest

from scripts.seed_demo import seed_demo_db

APP_TEST_TIMEOUT = 15


def _reload_db_for_test(db_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """Point handoff.db at a test DB path and reload so the engine is recreated."""
    monkeypatch.setenv("HANDOFF_DB_PATH", str(db_path))

    import handoff.db as db

    db.dispose_db()
    importlib.reload(db)
    import handoff.interfaces.streamlit.ui as streamlit_ui

    importlib.reload(streamlit_ui)


def _patch_uat_date(monkeypatch: pytest.MonkeyPatch, fixed_date_class: type[date]) -> None:
    """Patch date.today() in the modules that drive seeded UAT behaviour.

    Keep this list in sync with any new Now-page or supporting modules that call
    ``date.today()`` directly; seeded UAT tests rely on a fixed reference date.

    Note: ``now_forms`` is intentionally excluded. Its ``isinstance(value, date)``
    form-validation guards are incompatible with the FixedDate subclass, and the
    form rendering date defaults do not affect section-placement correctness.
    """
    import handoff.data.handoffs as data_handoffs
    import handoff.data.queries as data_queries
    import handoff.dates as handoff_dates
    import handoff.interfaces.streamlit.pages.now_helpers as now_helpers
    import handoff.services.handoff_service as handoff_service

    for module in (
        data_handoffs,
        data_queries,
        handoff_dates,
        now_helpers,
        handoff_service,
    ):
        monkeypatch.setattr(module, "date", fixed_date_class)


@pytest.fixture
def seeded_uat_db(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    """Create a seeded demo DB and pin date.today() for deterministic UAT tests."""
    db_path = tmp_path / "seeded-uat.db"
    reference_date = date(2026, 3, 9)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return reference_date

    seed_demo_db(db_path, reference_date=reference_date)
    _reload_db_for_test(db_path, monkeypatch)
    _patch_uat_date(monkeypatch, FixedDate)
    return db_path


def _now_page_entry() -> None:
    """Single-page entrypoint for the seeded Now page."""
    import handoff.interfaces.streamlit.ui as ui
    from handoff.interfaces.streamlit.pages.now import render_now_page
    from handoff.version import __version__

    ui.setup(__version__)
    render_now_page()


def _dashboard_page_entry() -> None:
    """Single-page entrypoint for the seeded Dashboard page."""
    import handoff.interfaces.streamlit.ui as ui
    from handoff.interfaces.streamlit.pages.dashboard import render_dashboard_page
    from handoff.version import __version__

    ui.setup(__version__)
    render_dashboard_page()


# ---------------------------------------------------------------------------
# Checklist item 1: Now sections present with expected seeded items
# ---------------------------------------------------------------------------


def test_now_page_renders_with_seeded_uat_db(seeded_uat_db: Path) -> None:
    """Seeded demo data should render the Now page without errors."""
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)

    assert len(at.exception) == 0
    markdown_texts = [getattr(markdown, "value", "") for markdown in at.get("markdown")]
    expander_labels = [getattr(expander, "label", "") for expander in at.get("expander")]

    assert any("Risk" in text for text in markdown_texts)
    assert any("Action required" in text for text in markdown_texts)
    assert any("Upcoming" in text for text in markdown_texts)
    assert any("Concluded" in text for text in markdown_texts)
    assert any("Overdue deliverable" in label for label in expander_labels)


def test_now_sections_contain_expected_seeded_items(seeded_uat_db: Path) -> None:
    """Each Now section shows the correct seeded handoffs from the demo DB."""
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)

    assert len(at.exception) == 0
    expander_labels = [getattr(e, "label", "") for e in at.get("expander")]

    # Risk: both overdue and due-today items must be present.
    assert any("Overdue deliverable" in lbl for lbl in expander_labels), (
        "Expected 'Overdue deliverable' in Risk section"
    )
    assert any("Due today" in lbl for lbl in expander_labels), (
        "Expected 'Due today' in Risk section"
    )

    # Action required: action item must be present.
    assert any("Action required item" in lbl for lbl in expander_labels), (
        "Expected 'Action required item' in Action required section"
    )

    # Upcoming: at least the plain upcoming task must be visible.
    assert any("Upcoming task" in lbl for lbl in expander_labels), (
        "Expected 'Upcoming task' in Upcoming section"
    )

    # Concluded: concluded task must be present.
    assert any("Concluded task" in lbl for lbl in expander_labels), (
        "Expected 'Concluded task' in Concluded section"
    )


# ---------------------------------------------------------------------------
# Checklist item 2: Conclude a handoff via UI
# ---------------------------------------------------------------------------


def test_now_uat_conclude_moves_handoff_to_concluded(seeded_uat_db: Path) -> None:
    """Conclude the 'Action required item' via UI and verify it is no longer open."""
    import handoff.data as data
    import handoff.db as db

    db.init_db()
    all_open = data.query_handoffs(include_concluded=False)
    action_h = next((h for h in all_open if h.need_back == "Action required item"), None)
    assert action_h is not None, "Expected 'Action required item' in open handoffs"
    assert action_h.id is not None
    handoff_id = action_h.id

    at = AppTest.from_function(_now_page_entry)
    # Pre-set check-in mode to avoid button-group set_value ambiguity.
    at.session_state[f"now_action_check_in_mode_{handoff_id}"] = "concluded"
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_buttons = [b for b in at.button if getattr(b, "label", None) == "Save conclude check-in"]
    assert save_buttons, "Expected 'Save conclude check-in' button"
    save_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    updated = next(
        (h for h in data.query_handoffs(include_concluded=True) if h.id == handoff_id),
        None,
    )
    assert updated is not None
    assert not data.handoff_is_open(updated), "Handoff should be concluded after UI conclude flow"


# ---------------------------------------------------------------------------
# Checklist item 3: Reopen a concluded handoff
# ---------------------------------------------------------------------------


def test_now_uat_reopen_moves_handoff_out_of_concluded(seeded_uat_db: Path) -> None:
    """Reopen the 'Concluded task' via UI and verify it returns to open sections."""
    import handoff.data as data
    import handoff.db as db

    db.init_db()
    concluded = data.query_concluded_handoffs()
    concluded_h = next((h for h in concluded if h.need_back == "Concluded task"), None)
    assert concluded_h is not None, "Expected 'Concluded task' in concluded handoffs"
    assert concluded_h.id is not None
    handoff_id = concluded_h.id

    # Pre-set the reopen mode. The next-check date will be populated by the
    # date_input widget's default value (add_business_days(today, 1)).
    at = AppTest.from_function(_now_page_entry)
    mode_key = f"now_concluded_reopen_mode_{handoff_id}"
    at.session_state[mode_key] = "reopen"
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    save_reopen_buttons = [b for b in at.button if getattr(b, "label", None) == "Save reopen"]
    assert save_reopen_buttons, "Expected 'Save reopen' button"
    save_reopen_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    updated = next(
        (h for h in data.query_handoffs(include_concluded=True) if h.id == handoff_id),
        None,
    )
    assert updated is not None
    assert data.handoff_is_open(updated), "Handoff should be open after reopen flow"

    still_concluded = [h.need_back for h in data.query_concluded_handoffs()]
    assert "Concluded task" not in still_concluded, (
        "Reopened handoff should not remain in concluded list"
    )


# ---------------------------------------------------------------------------
# Checklist item 4: Add handoff via form
# ---------------------------------------------------------------------------


def test_now_uat_add_handoff_persists_and_is_placed(seeded_uat_db: Path) -> None:
    """Adding a handoff via the Now page form persists it to the database."""
    import handoff.data as data
    import handoff.db as db

    db.init_db()

    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    add_buttons = [b for b in at.button if "Add handoff" in getattr(b, "label", "")]
    assert add_buttons, "Expected 'Add handoff' trigger button"
    add_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    need_back_inputs = [
        ti
        for ti in at.text_input
        if getattr(ti, "key", None) == "now_add_need" or getattr(ti, "label", None) == "Need back *"
    ]
    assert need_back_inputs, "Expected 'Need back' input in add form"
    need_back_inputs[0].input("UAT new handoff").run(timeout=APP_TEST_TIMEOUT)

    submit_buttons = [b for b in at.button if getattr(b, "label", None) == "Add"]
    assert submit_buttons, "Expected 'Add' submit button"
    submit_buttons[0].click().run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    all_handoffs = data.query_handoffs(include_concluded=True)
    created = next((h for h in all_handoffs if h.need_back == "UAT new handoff"), None)
    assert created is not None, "Newly added handoff should be persisted in the database"


# ---------------------------------------------------------------------------
# Checklist item 5: Archived toggle shows archived project items
# ---------------------------------------------------------------------------


def test_now_uat_archived_toggle_reveals_archived_items(seeded_uat_db: Path) -> None:
    """Toggling 'Include archived projects' makes the archived handoff visible."""
    at = AppTest.from_function(_now_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    # Archived handoff must not be visible before toggle.
    expander_labels_before = [getattr(e, "label", "") for e in at.get("expander")]
    assert not any("Archived project follow-up" in lbl for lbl in expander_labels_before), (
        "Archived handoff should be hidden before toggling Include archived projects"
    )

    # Toggle the archived-projects control (checkbox or toggle widget).
    archived_controls = [
        w
        for w in list(at.checkbox) + list(at.toggle)
        if "archived" in getattr(w, "label", "").lower()
    ]
    assert archived_controls, "Expected 'Include archived projects' toggle/checkbox"
    archived_controls[0].set_value(True).run(timeout=APP_TEST_TIMEOUT)
    assert len(at.exception) == 0

    expander_labels_after = [getattr(e, "label", "") for e in at.get("expander")]
    assert any("Archived project follow-up" in lbl for lbl in expander_labels_after), (
        "Archived handoff should appear after enabling Include archived projects"
    )


# ---------------------------------------------------------------------------
# Checklist item 6: Dashboard renders without error with seeded data
# ---------------------------------------------------------------------------


def test_dashboard_renders_with_seeded_uat_db(seeded_uat_db: Path) -> None:
    """Dashboard page renders without errors and shows key metrics for seeded data."""
    at = AppTest.from_function(_dashboard_page_entry)
    at.run(timeout=APP_TEST_TIMEOUT)

    assert len(at.exception) == 0
    assert len(at.get("subheader")) >= 1
    metric_labels = [getattr(m, "label", None) for m in at.metric]
    assert "At risk now" in metric_labels
    assert "Open handoffs" in metric_labels
