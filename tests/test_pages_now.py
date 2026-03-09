"""Tests for the Now page."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handoff.pages.now import render_now_page


def _make_fake_handoff(
    handoff_id: int = 1,
    project_name: str = "Work",
    pitchman: str | None = "Alice",
    need_back: str = "Need back",
    next_check: date | None = None,
    deadline: date | None = None,
    notes: str = "",
) -> SimpleNamespace:
    """Build a minimal handoff-like object for Now page render tests."""
    proj = SimpleNamespace(id=1, name=project_name)
    return SimpleNamespace(
        id=handoff_id,
        project=proj,
        pitchman=pitchman,
        need_back=need_back,
        next_check=next_check or date(2026, 1, 15),
        deadline=deadline,
        notes=notes,
        check_ins=[],
    )


def test_render_now_page_no_projects_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When there are no projects, the Now page shows an info message."""
    st_mock = MagicMock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    render_now_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]


def test_render_now_page_with_projects_queries_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """When projects exist, the page calls query_now_items and renders results."""
    st_mock = MagicMock()
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.text_area.return_value = ""
    st_mock.columns.return_value = [MagicMock(), MagicMock(), MagicMock()]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    query_calls: list[dict] = []

    def capture_query(**kwargs):
        query_calls.append(kwargs)
        return []

    monkeypatch.setattr("handoff.pages.now.query_now_items", capture_query)
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kwargs: [])
    render_now_page()
    assert len(query_calls) == 1
    assert "project_ids" in query_calls[0]
    assert "pitchman_names" in query_calls[0]


def test_render_now_page_with_action_required_items_renders_expanders_and_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When query_now_items and query_upcoming_handoffs return items, _render_item is used."""
    st_mock = MagicMock()
    st_mock.session_state = {}
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.text_area.return_value = ""
    st_mock.button.return_value = False
    st_mock.date_input.return_value = date(2026, 1, 20)

    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    st_mock.columns.side_effect = lambda n: [
        Ctx() for _ in range(n if isinstance(n, int) else len(n))
    ]
    st_mock.expander.return_value = Ctx()
    st_mock.popover.return_value = Ctx()
    st_mock.form.return_value = Ctx()

    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    handoff_action = _make_fake_handoff(handoff_id=1, need_back="Action item")
    handoff_upcoming = _make_fake_handoff(handoff_id=2, need_back="Upcoming item")
    monkeypatch.setattr(
        "handoff.pages.now.query_now_items",
        lambda **kw: [(handoff_action, False)],
    )
    monkeypatch.setattr(
        "handoff.pages.now.query_upcoming_handoffs",
        lambda **kw: [handoff_upcoming],
    )
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])
    render_now_page()
    assert st_mock.expander.call_count >= 2
    button_labels = [c[0][0] for c in st_mock.button.call_args_list if c[0]]
    assert any(label == "Snooze" for label in button_labels)
    assert any(label == "Edit" for label in button_labels)
    assert any(label == "✓ Conclude" for label in button_labels)


def test_render_now_page_concluded_expander_queries_handoffs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the page renders, the Concluded expander queries concluded handoffs."""
    st_mock = MagicMock()
    st_mock.session_state = {}
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.text_area.return_value = ""
    st_mock.button.return_value = False
    st_mock.date_input.return_value = date(2026, 1, 20)

    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    st_mock.columns.side_effect = lambda n: [
        Ctx() for _ in range(n if isinstance(n, int) else len(n))
    ]
    st_mock.expander.return_value = Ctx()
    st_mock.popover.return_value = Ctx()
    st_mock.form.return_value = Ctx()

    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    monkeypatch.setattr("handoff.pages.now.query_now_items", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])

    concluded_calls: list[dict] = []

    def capture_concluded(**kwargs):
        concluded_calls.append(kwargs)
        return []

    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", capture_concluded)
    render_now_page()

    assert len(concluded_calls) == 1
    st_mock.expander.assert_called()
    concluded_call = [c for c in st_mock.expander.call_args_list if c[0][0] == "Concluded >"]
    assert len(concluded_call) == 1


def test_render_now_page_with_editing_shows_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """When session_state now_editing_handoff_id is set, edit form is rendered."""
    st_mock = MagicMock()
    st_mock.session_state = {"now_editing_handoff_id": 1}
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.text_area.return_value = ""
    st_mock.button.return_value = False
    st_mock.date_input.return_value = date(2026, 1, 20)

    class Ctx:
        def __enter__(self):
            return self

        def __exit__(self, *a):
            return False

    st_mock.columns.side_effect = lambda n: [
        Ctx() for _ in range(n if isinstance(n, int) else len(n))
    ]
    st_mock.expander.return_value = Ctx()
    st_mock.popover.return_value = Ctx()
    st_mock.form.return_value = Ctx()
    st_mock.selectbox.return_value = "Work"

    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    handoff_action = _make_fake_handoff(handoff_id=1, need_back="Edit me")
    monkeypatch.setattr(
        "handoff.pages.now.query_now_items",
        lambda **kw: [(handoff_action, False)],
    )
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])
    render_now_page()
    st_mock.form.assert_called()
    assert any("edit" in str(c).lower() for c in st_mock.form.call_args_list)
