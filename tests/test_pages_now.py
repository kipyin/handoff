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
    """Build a minimal handoff-like object for Now page tests."""
    proj = SimpleNamespace(id=1, name=project_name)
    return SimpleNamespace(
        id=handoff_id,
        project=proj,
        pitchman=pitchman,
        need_back=need_back,
        next_check=next_check or date(2026, 3, 9),
        deadline=deadline,
        notes=notes,
        check_ins=[],
    )


class _Ctx:
    def __enter__(self):
        return self

    def __exit__(self, *args):
        return False


def _build_streamlit_mock() -> MagicMock:
    """Create a streamlit mock with context manager widgets configured."""
    st_mock = MagicMock()
    st_mock.session_state = {}
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.text_area.return_value = ""
    st_mock.button.return_value = False
    st_mock.form_submit_button.return_value = False
    st_mock.date_input.return_value = date(2026, 3, 10)
    st_mock.selectbox.return_value = "Work"
    st_mock.columns.side_effect = lambda n: [
        _Ctx() for _ in range(n if isinstance(n, int) else len(n))
    ]
    st_mock.expander.return_value = _Ctx()
    st_mock.popover.return_value = _Ctx()
    st_mock.form.return_value = _Ctx()
    return st_mock


def test_render_now_page_no_projects_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When there are no projects, the Now page shows an info message."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    render_now_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]


def test_render_now_page_queries_phase2_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Now page calls risk/action/upcoming/concluded query functions."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 3)

    risk_calls: list[dict] = []
    action_calls: list[dict] = []
    upcoming_calls: list[dict] = []
    concluded_calls: list[dict] = []
    monkeypatch.setattr(
        "handoff.pages.now.query_risk_handoffs", lambda **kwargs: risk_calls.append(kwargs) or []
    )
    monkeypatch.setattr(
        "handoff.pages.now.query_action_handoffs",
        lambda **kwargs: action_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        "handoff.pages.now.query_upcoming_handoffs",
        lambda **kwargs: upcoming_calls.append(kwargs) or [],
    )
    monkeypatch.setattr(
        "handoff.pages.now.query_concluded_handoffs",
        lambda **kwargs: concluded_calls.append(kwargs) or [],
    )

    render_now_page()

    assert len(risk_calls) == 1
    assert len(action_calls) == 1
    assert len(upcoming_calls) == 1
    assert len(concluded_calls) == 1
    assert "project_ids" in risk_calls[0]
    assert "pitchman_names" in action_calls[0]


def test_render_now_page_action_item_shows_check_in_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Action items render On-track/Delayed/Conclude check-in actions."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr("handoff.pages.now.date", FixedDate)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 3)

    action_handoff = _make_fake_handoff(
        handoff_id=1,
        need_back="Due now",
        next_check=date(2026, 3, 9),
    )
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [action_handoff])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    labels = [call[0][0] for call in st_mock.button.call_args_list if call[0]]
    assert "On-track" in labels
    assert "Delayed" in labels
    assert "Conclude" in labels


def test_render_now_page_concluded_section_renders_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concluded handoffs are rendered as item expanders with no dataframe."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr(
        "handoff.pages.now.query_concluded_handoffs",
        lambda **kw: [_make_fake_handoff(handoff_id=9, need_back="Closed item")],
    )

    render_now_page()

    assert st_mock.expander.call_count >= 2  # add-form + concluded item
    st_mock.dataframe.assert_not_called()
