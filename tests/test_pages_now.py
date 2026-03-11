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
    _render_check_in_flow,
    _render_check_in_trail,
    _render_reopen_flow,
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
    assert "Edit" in labels
    assert "On-track" in labels
    assert "Delayed" in labels
    assert "Conclude" in labels


def test_render_now_page_risk_item_shows_check_in_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Risk items also render On-track/Delayed/Conclude check-in actions."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    risk_handoff = _make_fake_handoff(
        handoff_id=22,
        need_back="Risk check",
        next_check=date(2026, 3, 12),
        deadline=date(2026, 3, 10),
    )
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [risk_handoff])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    labels = [call[0][0] for call in st_mock.button.call_args_list if call[0]]
    assert "Edit" in labels
    assert "On-track" in labels
    assert "Delayed" in labels
    assert "Conclude" in labels


def test_render_now_page_upcoming_item_shows_check_in_buttons(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upcoming items also render On-track/Delayed/Conclude check-in actions."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    upcoming_handoff = _make_fake_handoff(
        handoff_id=23,
        need_back="Upcoming check",
        next_check=date(2026, 4, 1),
    )
    monkeypatch.setattr("handoff.pages.now.query_risk_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_action_handoffs", lambda **kw: [])
    monkeypatch.setattr(
        "handoff.pages.now.query_upcoming_handoffs", lambda **kw: [upcoming_handoff]
    )
    monkeypatch.setattr("handoff.pages.now.query_concluded_handoffs", lambda **kw: [])

    render_now_page()

    labels = [call[0][0] for call in st_mock.button.call_args_list if call[0]]
    assert "Edit" in labels
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


def test_render_check_in_flow_due_shows_due_caption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Due handoffs keep due-state check-in messaging."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=31, next_check=date(2000, 1, 1))

    _render_check_in_flow(handoff, key_prefix="now_action")

    captions = [call[0][0] for call in st_mock.caption.call_args_list if call[0]]
    assert any("Check-in due now" in text for text in captions)


def test_render_check_in_flow_non_due_shows_early_caption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-due handoffs offer optional early check-in messaging."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=32, next_check=date(2099, 1, 1))

    _render_check_in_flow(handoff, key_prefix="now_upcoming")

    captions = [call[0][0] for call in st_mock.caption.call_args_list if call[0]]
    assert any("Optional early check-in" in text for text in captions)


@pytest.mark.parametrize("mode", ["on_track", "delayed"])
def test_render_check_in_flow_prefills_future_next_check_date(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
) -> None:
    """On-track/delayed forms keep a future next_check as the default date input."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=35, next_check=date(2099, 1, 5))
    st_mock.session_state["now_action_check_in_mode_35"] = mode

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert st_mock.date_input.call_count == 1
    assert st_mock.date_input.call_args.kwargs["value"] == date(2099, 1, 5)


def test_render_check_in_flow_prefills_next_business_day_for_due_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overdue next_check values default to the next business day when checking in."""
    from handoff.pages import now as now_page

    class _FrozenDate(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return cls(2030, 1, 1)

    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr(now_page, "date", _FrozenDate)
    handoff = _make_fake_handoff(handoff_id=36, next_check=date(2000, 1, 5))
    st_mock.session_state["now_action_check_in_mode_36"] = "on_track"

    _render_check_in_flow(handoff, key_prefix="now_action")

    expected_default = now_page.add_business_days(_FrozenDate.today(), 1)
    assert st_mock.date_input.call_count == 1
    assert st_mock.date_input.call_args.kwargs["value"] == expected_default


def test_render_now_page_concluded_item_shows_reopen_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concluded section renders a dedicated Reopen action."""
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
        lambda **kw: [_make_fake_handoff(handoff_id=15, need_back="Closed item")],
    )

    render_now_page()

    labels = [call[0][0] for call in st_mock.button.call_args_list if call[0]]
    assert "Reopen" in labels


def test_render_reopen_flow_save_calls_reopen_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saving reopen appends a reopen check-in and shows updated feedback."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = [True, False]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_reopen_handoff(handoff_id: int, *, note: str | None, next_check_date: date) -> None:
        calls.append(
            {
                "handoff_id": handoff_id,
                "note": note,
                "next_check_date": next_check_date,
            }
        )

    monkeypatch.setattr("handoff.pages.now.reopen_handoff", _fake_reopen_handoff)
    handoff = _make_fake_handoff(handoff_id=19, need_back="Closed")
    st_mock.session_state["now_concluded_reopen_mode_19"] = "reopen"

    _render_reopen_flow(handoff, key_prefix="now_concluded")

    assert len(calls) == 1
    assert calls[0]["handoff_id"] == 19
    assert "Checked in today; next check set to" in st_mock.session_state["now_flash_success"]


def test_render_check_in_flow_save_sets_flash_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saving a non-concluded check-in sets post-rerun success feedback."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = [True, False]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_add_check_in(
        handoff_id: int,
        *,
        check_in_type: CheckInType,
        note: str | None,
        next_check_date: date,
    ) -> None:
        calls.append(
            {
                "handoff_id": handoff_id,
                "check_in_type": check_in_type,
                "note": note,
                "next_check_date": next_check_date,
            }
        )

    monkeypatch.setattr("handoff.pages.now.add_check_in", _fake_add_check_in)
    handoff = _make_fake_handoff(handoff_id=41, next_check=date(2026, 3, 12))
    st_mock.session_state["now_action_check_in_mode_41"] = "on_track"

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert len(calls) == 1
    assert calls[0]["handoff_id"] == 41
    assert "Checked in today; next check set to" in st_mock.session_state["now_flash_success"]


def test_render_check_in_flow_save_concluded_sets_flash_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving concluded mode closes the handoff and sets flash feedback."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.text_area.return_value = "  wrapped up  "
    st_mock.form_submit_button.side_effect = [True, False]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_conclude_handoff(handoff_id: int, note: str | None = None) -> None:
        calls.append({"handoff_id": handoff_id, "note": note})

    monkeypatch.setattr("handoff.pages.now.conclude_handoff", _fake_conclude_handoff)
    handoff = _make_fake_handoff(handoff_id=42, next_check=date(2026, 3, 12))
    st_mock.session_state["now_action_check_in_mode_42"] = "concluded"

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert calls == [{"handoff_id": 42, "note": "wrapped up"}]
    assert st_mock.session_state["now_flash_success"] == "Checked in today as concluded."


def test_render_check_in_flow_delayed_mode_uses_delayed_type(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delayed mode persists a delayed check-in type."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.text_area.return_value = "  waiting on dependency  "
    st_mock.date_input.return_value = date(2026, 3, 20)
    st_mock.form_submit_button.side_effect = [True, False]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_add_check_in(
        handoff_id: int,
        *,
        check_in_type: CheckInType,
        note: str | None,
        next_check_date: date,
    ) -> None:
        calls.append(
            {
                "handoff_id": handoff_id,
                "check_in_type": check_in_type,
                "note": note,
                "next_check_date": next_check_date,
            }
        )

    monkeypatch.setattr("handoff.pages.now.add_check_in", _fake_add_check_in)
    handoff = _make_fake_handoff(handoff_id=43, next_check=date(2026, 3, 12))
    st_mock.session_state["now_action_check_in_mode_43"] = "delayed"

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert len(calls) == 1
    assert calls[0]["check_in_type"] is CheckInType.DELAYED
    assert calls[0]["note"] == "waiting on dependency"
    assert calls[0]["next_check_date"] == date(2026, 3, 20)


def test_render_reopen_flow_save_value_error_shows_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation errors from reopen are shown and keep form state active."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = [True, False]
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    def _raise_value_error(
        handoff_id: int,
        *,
        note: str | None,
        next_check_date: date,
    ) -> None:
        raise ValueError("Can only reopen concluded handoffs")

    monkeypatch.setattr("handoff.pages.now.reopen_handoff", _raise_value_error)
    handoff = _make_fake_handoff(handoff_id=19, need_back="Closed")
    st_mock.session_state["now_concluded_reopen_mode_19"] = "reopen"

    _render_reopen_flow(handoff, key_prefix="now_concluded")

    st_mock.error.assert_called_once_with("Can only reopen concluded handoffs")
    assert st_mock.session_state["now_concluded_reopen_mode_19"] == "reopen"
    assert "now_flash_success" not in st_mock.session_state
    st_mock.rerun.assert_not_called()


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
