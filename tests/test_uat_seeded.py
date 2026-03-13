"""Smoke tests for the seeded UAT database workflow."""

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
    import handoff.ui as ui

    importlib.reload(ui)


def _patch_uat_date(monkeypatch: pytest.MonkeyPatch, fixed_date_class: type[date]) -> None:
    """Patch date.today() in the modules that drive seeded UAT behaviour."""
    import handoff.data.handoffs as data_handoffs
    import handoff.data.queries as data_queries
    import handoff.dates as handoff_dates
    import handoff.interfaces.streamlit.pages.now_forms as now_forms
    import handoff.interfaces.streamlit.pages.now_helpers as now_helpers
    import handoff.services.handoff_service as handoff_service

    for module in (
        data_handoffs,
        data_queries,
        handoff_dates,
        now_forms,
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
    import handoff.ui as ui
    from handoff.interfaces.streamlit.pages.now import render_now_page

    ui.setup("2026.2.24")
    render_now_page()


def test_now_page_renders_with_seeded_uat_db(seeded_uat_db: Path) -> None:
    """Seeded demo data should render the Now page without errors."""
    del seeded_uat_db
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
