"""Tests for the Now page."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handoff.models import CheckIn, CheckInType
from handoff.pages.now import (
    _check_in_header,
    _is_check_in_due,
    _render_check_in_trail,
    render_now_page,
)


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
    st_mock.checkbox.return_value = False
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
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    render_now_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]


def test_render_now_page_archived_only_projects_shows_toggle_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When only archived projects exist, the page suggests enabling archived visibility."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    archived_project = SimpleNamespace(id=2, name="Archived")
    list_project_calls: list[bool] = []

    def _list_projects(**kwargs):
        include_archived = kwargs["include_archived"]
        list_project_calls.append(include_archived)
        return [archived_project] if include_archived else []

    monkeypatch.setattr("handoff.pages.now.list_projects", _list_projects)
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)

    render_now_page()

    assert list_project_calls == [False, True]
    st_mock.info.assert_called_once()
    assert "No active projects." in st_mock.info.call_args[0][0]


def test_render_now_page_queries_phase2_sections(monkeypatch: pytest.MonkeyPatch) -> None:
    """Now page calls risk/action/upcoming/concluded query functions."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
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
    assert concluded_calls[0]["include_archived_projects"] is False


def test_render_now_page_include_archived_projects_passed_to_queries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page passes the include-archived toggle through all section queries."""
    st_mock = _build_streamlit_mock()
    st_mock.checkbox.return_value = True
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
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

    assert risk_calls[0]["include_archived_projects"] is True
    assert action_calls[0]["include_archived_projects"] is True
    assert upcoming_calls[0]["include_archived_projects"] is True
    assert concluded_calls[0]["include_archived_projects"] is True


def test_render_now_page_include_archived_projects_passed_to_pitchmen_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page forwards include-archived toggle to pitchman query."""
    st_mock = _build_streamlit_mock()
    st_mock.checkbox.return_value = True
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    pitchmen_calls: list[dict] = []
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: pitchmen_calls.append(kwargs) or ["Alice"],
    )
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 3)
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    assert len(pitchmen_calls) == 1
    assert pitchmen_calls[0]["include_archived_projects"] is True


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
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
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
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
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


def test_render_now_page_risk_section_renders_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Risk items appear in the Risk section with their expanders."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    risk_handoff = _make_fake_handoff(
        handoff_id=2,
        need_back="At risk",
        deadline=date(2026, 3, 9),
    )
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [risk_handoff])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    expander_headers = [str(call[0][0]) for call in st_mock.expander.call_args_list]
    assert any("At risk" in h for h in expander_headers)


def test_render_now_page_upcoming_section_renders_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Upcoming items appear in the Upcoming section with their expanders."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    upcoming_handoff = _make_fake_handoff(
        handoff_id=3,
        need_back="Check later",
        next_check=date(2026, 4, 1),
    )
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr(
        "handoff.pages.now.query_upcoming_handoffs", lambda **kw: [upcoming_handoff]
    )
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    expander_headers = [str(call[0][0]) for call in st_mock.expander.call_args_list]
    assert any("Check later" in h for h in expander_headers)


def test_render_now_page_item_with_context_renders_markdown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Items with notes display context markdown inside the expander."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    handoff_with_notes = _make_fake_handoff(
        handoff_id=4,
        need_back="Has notes",
        notes="Important context here",
    )
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr(
        "handoff.pages.now.query_upcoming_handoffs", lambda **kw: [handoff_with_notes]
    )
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    markdown_calls = [str(c) for c in st_mock.markdown.call_args_list]
    assert any("Important context here" in c for c in markdown_calls)


# --- Unit tests for _check_in_header ---


def _make_check_in(
    check_in_type: CheckInType = CheckInType.ON_TRACK,
    note: str | None = None,
    check_in_date: date = date(2026, 3, 9),
) -> CheckIn:
    return CheckIn(
        id=1,
        handoff_id=1,
        check_in_type=check_in_type,
        check_in_date=check_in_date,
        note=note,
    )


def test_check_in_header_no_note() -> None:
    """Header with no note returns base label + date only."""
    ci = _make_check_in(check_in_type=CheckInType.ON_TRACK, note=None)
    header = _check_in_header(ci)
    assert "[On Track]" in header
    assert " — " not in header


def test_check_in_header_with_short_note() -> None:
    """Header with a short note appends the note after a dash."""
    ci = _make_check_in(note="All good")
    header = _check_in_header(ci)
    assert "All good" in header
    assert " — " in header


def test_check_in_header_with_long_note_truncates() -> None:
    """Header with a note longer than 40 chars is truncated with an ellipsis."""
    long_note = "A" * 50
    ci = _make_check_in(note=long_note)
    header = _check_in_header(ci)
    assert "…" in header
    # Preview should be truncated to 40 chars + ellipsis
    parts = header.split(" — ")
    assert len(parts[1]) <= 41  # 40 chars + "…"


def test_check_in_header_multiline_note_flattened() -> None:
    """Newlines in the note are replaced with spaces in the header preview."""
    ci = _make_check_in(note="Line one\nLine two")
    header = _check_in_header(ci)
    assert "\n" not in header
    assert "Line one Line two" in header


# --- Unit tests for _render_check_in_trail ---


def test_render_check_in_trail_empty(monkeypatch: pytest.MonkeyPatch) -> None:
    """An empty check-in list shows 'No check-ins yet.' caption."""
    st_mock = MagicMock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    fake_handoff = SimpleNamespace(check_ins=[])
    _render_check_in_trail(fake_handoff)
    st_mock.caption.assert_called_once_with("No check-ins yet.")
    st_mock.expander.assert_not_called()


def test_render_check_in_trail_with_entry_no_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check-in without a note shows 'No note.' caption inside the expander."""
    st_mock = MagicMock()
    st_mock.expander.return_value = _Ctx()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    ci = _make_check_in(check_in_type=CheckInType.ON_TRACK, note=None)
    fake_handoff = SimpleNamespace(check_ins=[ci])
    _render_check_in_trail(fake_handoff)

    st_mock.expander.assert_called_once()
    st_mock.caption.assert_called_with("No note.")


def test_render_check_in_trail_with_entry_with_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check-in with a note renders the note as markdown inside the expander."""
    st_mock = MagicMock()
    st_mock.expander.return_value = _Ctx()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    ci = _make_check_in(check_in_type=CheckInType.DELAYED, note="Still waiting")
    fake_handoff = SimpleNamespace(check_ins=[ci])
    _render_check_in_trail(fake_handoff)

    st_mock.markdown.assert_called_with("Still waiting")


# --- Unit tests for _is_check_in_due ---


def test_is_check_in_due_past_date() -> None:
    """Returns True when next_check is in the past."""
    from types import SimpleNamespace

    h = SimpleNamespace(next_check=date(2000, 1, 1))
    assert _is_check_in_due(h) is True


def test_is_check_in_due_future_date() -> None:
    """Returns False when next_check is in the future."""
    from types import SimpleNamespace

    h = SimpleNamespace(next_check=date(2099, 1, 1))
    assert _is_check_in_due(h) is False


def test_is_check_in_due_none() -> None:
    """Returns False when next_check is None."""
    from types import SimpleNamespace

    h = SimpleNamespace(next_check=None)
    assert _is_check_in_due(h) is False
