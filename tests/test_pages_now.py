"""Tests for the Now page."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handoff.models import CheckIn, CheckInType
from handoff.page_models import NowSnapshot
from handoff.pages.now import (
    _NOW_ADD_EXPANDED_KEY,
    _check_in_header,
    _is_check_in_due,
    _render_add_form,
    _render_check_in_flow,
    _render_check_in_trail,
    _render_item,
    _render_reopen_flow,
    render_now_page,
)


def _make_fake_snapshot(
    *,
    risk: list | None = None,
    action: list | None = None,
    upcoming: list | None = None,
    concluded: list | None = None,
    projects: list | None = None,
    pitchmen: list | None = None,
) -> NowSnapshot:
    """Build a minimal NowSnapshot for Now page tests."""
    mock_project = SimpleNamespace(id=1, name="Work")
    return NowSnapshot(
        risk=risk or [],
        action=action or [],
        upcoming=upcoming or [],
        concluded=concluded or [],
        projects=projects or [mock_project],
        pitchmen=pitchmen or [],
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
    st_mock.segmented_control.return_value = "1d"
    st_mock.columns.side_effect = lambda n: [
        _Ctx() for _ in range(n if isinstance(n, int) else len(n))
    ]
    st_mock.expander.return_value = _Ctx()
    st_mock.popover.return_value = _Ctx()
    st_mock.form.return_value = _Ctx()
    return st_mock


def _simulate_widget_submit(label_to_click: str):
    """Return a side-effect that submits one widget label callback."""

    def _side_effect(label: str, *args, **kwargs) -> bool:
        if label == label_to_click:
            on_click = kwargs.get("on_click")
            if callable(on_click):
                on_click(**kwargs.get("kwargs", {}))
            return True
        return False

    return _side_effect


def test_render_now_page_no_projects_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When there are no projects, the Now page shows an info message."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [])
    render_now_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]


def test_render_now_page_flash_error_message_is_rendered_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flash errors are displayed once and cleared from session state."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state["now_flash_error"] = "Invalid form submission"
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [])

    render_now_page()

    st_mock.error.assert_called_once_with("Invalid form submission")
    assert "now_flash_error" not in st_mock.session_state


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

    render_now_page()

    assert list_project_calls == [False, True]
    st_mock.info.assert_called_once()
    assert "No active projects." in st_mock.info.call_args[0][0]


def test_render_now_page_calls_get_now_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Now page calls get_now_snapshot with filters from the UI."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    prefetched_projects = [mock_project]
    prefetched_pitchmen = ["Alice"]
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: prefetched_projects)
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: prefetched_pitchmen,
    )

    snapshot_calls: list[dict] = []

    def _capture_snapshot(**kwargs):
        snapshot_calls.append(kwargs)
        return _make_fake_snapshot()

    monkeypatch.setattr("handoff.pages.now.get_now_snapshot", _capture_snapshot)

    render_now_page()

    assert len(snapshot_calls) == 1
    assert snapshot_calls[0]["include_archived_projects"] is False
    assert "project_ids" in snapshot_calls[0]
    assert "pitchman_names" in snapshot_calls[0]
    assert "search_text" in snapshot_calls[0]
    assert snapshot_calls[0]["projects"] is prefetched_projects
    assert snapshot_calls[0]["pitchmen"] is prefetched_pitchmen


def test_render_now_page_shows_shortcuts_caption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page shows discoverable shortcuts caption."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

    render_now_page()

    caption_calls = [str(c) for c in st_mock.caption.call_args_list]
    assert any("Shortcuts" in c and "Add handoff" in c for c in caption_calls)


def test_render_now_page_add_button_has_shortcut_when_collapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add handoff trigger button has shortcut 'a' when Streamlit supports it."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

    render_now_page()

    add_btn_calls = [
        c for c in st_mock.button.call_args_list if c[0] and "Add handoff" in str(c[0][0])
    ]
    assert len(add_btn_calls) >= 1
    # First call uses shortcut when supported; fallback omits it
    first_call = add_btn_calls[0]
    assert first_call.kwargs.get("shortcut") == "a" or "shortcut" not in first_call.kwargs


def test_render_now_page_add_button_fallback_when_shortcut_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When Streamlit lacks shortcut param (e.g. in-app patch), button renders without it."""
    st_mock = _build_streamlit_mock()

    def button_raising_shortcut(*args, **kwargs):
        if "shortcut" in kwargs:
            raise TypeError("got an unexpected keyword argument 'shortcut'")
        return False

    st_mock.button.side_effect = button_raising_shortcut
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

    render_now_page()

    # Fallback call has no shortcut; page rendered without error
    add_btn_calls = [
        c for c in st_mock.button.call_args_list if c[0] and "Add handoff" in str(c[0][0])
    ]
    assert len(add_btn_calls) >= 1
    # At least one call succeeded (fallback); it must not have shortcut
    fallback_calls = [c for c in add_btn_calls if "shortcut" not in c.kwargs]
    assert len(fallback_calls) >= 1


def test_expand_add_form_sets_session_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expand add form callback sets now_add_expanded in session state."""
    from handoff.pages.now import _expand_add_form

    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    _expand_add_form()

    assert st_mock.session_state[_NOW_ADD_EXPANDED_KEY] is True


def test_collapse_add_form_clears_session_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collapse add form callback removes now_add_expanded from session state."""
    from handoff.pages.now import _collapse_add_form

    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    _collapse_add_form()

    assert _NOW_ADD_EXPANDED_KEY not in st_mock.session_state


def test_render_now_page_add_form_expands_when_add_expanded_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When now_add_expanded is True, the add form is rendered instead of the trigger button."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
    add_form_called = []

    def _track_add_form(*args, **kwargs):
        add_form_called.append(True)

    monkeypatch.setattr("handoff.pages.now._render_add_form", _track_add_form)
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

    render_now_page()

    assert add_form_called == [True]


def test_render_now_page_add_form_uses_snapshot_pitchmen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page uses snapshot.pitchmen for add form options."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(pitchmen=["Bob", "Carol"]),
    )
    add_form_calls: list[dict] = []

    def _capture_add_form(project_by_name, pitchmen, key_prefix):
        add_form_calls.append(
            {
                "project_by_name": project_by_name,
                "pitchmen": pitchmen,
                "key_prefix": key_prefix,
            }
        )

    monkeypatch.setattr("handoff.pages.now._render_add_form", _capture_add_form)

    render_now_page()

    assert len(add_form_calls) == 1
    assert add_form_calls[0]["pitchmen"] == ["Bob", "Carol"]
    assert add_form_calls[0]["key_prefix"] == "now"


def test_render_now_page_include_archived_projects_passed_to_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page passes the include-archived toggle to get_now_snapshot."""
    st_mock = _build_streamlit_mock()
    st_mock.checkbox.return_value = True
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr(
        "handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: ["Alice"]
    )

    snapshot_calls: list[dict] = []

    def _capture_snapshot(**kwargs):
        snapshot_calls.append(kwargs)
        return _make_fake_snapshot()

    monkeypatch.setattr("handoff.pages.now.get_now_snapshot", _capture_snapshot)

    render_now_page()

    assert len(snapshot_calls) == 1
    assert snapshot_calls[0]["include_archived_projects"] is True


def test_render_now_page_include_archived_passed_to_list_pitchmen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page forwards include-archived toggle to list_pitchmen_with_open_handoffs."""
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
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

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

    action_handoff = _make_fake_handoff(
        handoff_id=1,
        need_back="Due now",
        next_check=date(2026, 3, 9),
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(action=[action_handoff]),
    )

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
    risk_handoff = _make_fake_handoff(
        handoff_id=22,
        need_back="Risk check",
        next_check=date(2026, 3, 12),
        deadline=date(2026, 3, 10),
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(risk=[risk_handoff]),
    )

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
    upcoming_handoff = _make_fake_handoff(
        handoff_id=23,
        need_back="Upcoming check",
        next_check=date(2026, 4, 1),
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(upcoming=[upcoming_handoff]),
    )

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
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            concluded=[_make_fake_handoff(handoff_id=9, need_back="Closed item")]
        ),
    )

    render_now_page()

    assert st_mock.expander.call_count >= 1  # concluded item (add form no longer uses expander)
    st_mock.dataframe.assert_not_called()


def test_render_now_page_risk_section_renders_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Risk items appear in the Risk section with their expanders."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda **kwargs: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_pitchmen_with_open_handoffs", lambda **kwargs: [])
    risk_handoff = _make_fake_handoff(
        handoff_id=2,
        need_back="At risk",
        deadline=date(2026, 3, 9),
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(risk=[risk_handoff]),
    )

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
    upcoming_handoff = _make_fake_handoff(
        handoff_id=3,
        need_back="Check later",
        next_check=date(2026, 4, 1),
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(upcoming=[upcoming_handoff]),
    )

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
    handoff_with_notes = _make_fake_handoff(
        handoff_id=4,
        need_back="Has notes",
        notes="Important context here",
    )
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(upcoming=[handoff_with_notes]),
    )

    render_now_page()

    markdown_calls = [str(c) for c in st_mock.markdown.call_args_list]
    assert any("Important context here" in c for c in markdown_calls)


def test_render_item_snooze_callback_uses_state_date(monkeypatch: pytest.MonkeyPatch) -> None:
    """Snooze button callback reads the date from session state and persists it."""
    st_mock = _build_streamlit_mock()
    st_mock.button.side_effect = _simulate_widget_submit("Snooze")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    snooze_calls: list[tuple[int, date]] = []

    def _fake_snooze_handoff(handoff_id: int, *, to_date: date) -> None:
        snooze_calls.append((handoff_id, to_date))

    monkeypatch.setattr("handoff.pages.now.snooze_handoff", _fake_snooze_handoff)
    handoff = _make_fake_handoff(handoff_id=90, need_back="Snooze me")
    st_mock.session_state["now_action_custom_90"] = date(2026, 3, 20)

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=False,
    )

    assert snooze_calls == [(90, date(2026, 3, 20))]
    assert st_mock.session_state["now_flash_success"].startswith("Snoozed to ")


def test_render_item_snooze_presets_segmented_control_shown(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Actions popover shows snooze presets (1d, 3d, 1w) via segmented_control."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=93, need_back="Check presets")

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=False,
    )

    assert st_mock.segmented_control.called
    call = next(c for c in st_mock.segmented_control.call_args_list if c[0])
    assert list(call.kwargs.get("options", call.args[1] if len(call.args) > 1 else [])) == [
        "1d",
        "3d",
        "1w",
    ]
    assert call.kwargs.get("default") == "1d"


def test_render_item_snooze_preset_callback_updates_date(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting a snooze preset updates the date in session state."""
    from handoff.dates import add_business_days

    class _FrozenDate(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return date(2026, 3, 10)

    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.pages.now.date", _FrozenDate)
    handoff = _make_fake_handoff(handoff_id=94, need_back="Preset date")

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=False,
    )

    # Simulate user selecting "3d" preset (on_change fires)
    seg_call = next(c for c in st_mock.segmented_control.call_args_list if c[0])
    on_change = seg_call.kwargs.get("on_change")
    assert on_change is not None
    kwargs = seg_call.kwargs.get("kwargs", {})
    preset_key = seg_call.kwargs["key"]
    st_mock.session_state[preset_key] = "3d"
    on_change(**kwargs)

    expected = add_business_days(_FrozenDate.today(), 3)
    assert st_mock.session_state[kwargs["date_key"]] == expected


def test_render_item_snooze_callback_invalid_date_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Snooze callback reports a validation error when session date is invalid."""
    st_mock = _build_streamlit_mock()
    st_mock.button.side_effect = _simulate_widget_submit("Snooze")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    snooze_calls: list[tuple[int, date]] = []

    def _fake_snooze_handoff(handoff_id: int, *, to_date: date) -> None:
        snooze_calls.append((handoff_id, to_date))

    monkeypatch.setattr("handoff.pages.now.snooze_handoff", _fake_snooze_handoff)
    handoff = _make_fake_handoff(handoff_id=91, need_back="Snooze me")
    st_mock.session_state["now_action_custom_91"] = "not-a-date"

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=False,
    )

    assert snooze_calls == []
    assert st_mock.session_state["now_flash_error"] == "Select a valid snooze date."


def test_render_item_edit_save_validation_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid edit save keeps edit mode active and sets flash error."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    update_calls: list[tuple[int, dict[str, object]]] = []

    def _fake_update_handoff(handoff_id: int, **changes) -> None:
        update_calls.append((handoff_id, changes))

    monkeypatch.setattr("handoff.pages.now.update_handoff", _fake_update_handoff)
    handoff = _make_fake_handoff(handoff_id=92, need_back="Original")
    st_mock.session_state["now_editing_handoff_id"] = 92
    edit_prefix = "now_action_edit_92"
    st_mock.session_state[f"{edit_prefix}_project"] = "Work"
    st_mock.session_state[f"{edit_prefix}_who"] = "Alice"
    st_mock.session_state[f"{edit_prefix}_need"] = "   "
    st_mock.session_state[f"{edit_prefix}_next"] = date(2026, 3, 21)
    st_mock.session_state[f"{edit_prefix}_deadline"] = None
    st_mock.session_state[f"{edit_prefix}_context"] = ""

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=True,
    )

    assert update_calls == []
    assert st_mock.session_state["now_flash_error"] == "Need back is required."
    assert st_mock.session_state["now_editing_handoff_id"] == 92


def test_render_item_edit_save_success_clears_editing_and_sets_flash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid edit save updates the handoff and clears editing state."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    update_calls: list[tuple[int, dict[str, object]]] = []

    def _fake_update_handoff(handoff_id: int, **changes) -> None:
        update_calls.append((handoff_id, changes))

    monkeypatch.setattr("handoff.pages.now.update_handoff", _fake_update_handoff)
    handoff = _make_fake_handoff(handoff_id=93, need_back="Original")
    st_mock.session_state["now_editing_handoff_id"] = 93
    edit_prefix = "now_action_edit_93"
    st_mock.session_state[f"{edit_prefix}_project"] = "Work"
    st_mock.session_state[f"{edit_prefix}_who"] = "Alex"
    st_mock.session_state[f"{edit_prefix}_need"] = "Updated need back"
    st_mock.session_state[f"{edit_prefix}_next"] = date(2026, 3, 22)
    st_mock.session_state[f"{edit_prefix}_deadline"] = date(2026, 3, 30)
    st_mock.session_state[f"{edit_prefix}_context"] = "  context note  "

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=True,
    )

    assert len(update_calls) == 1
    assert update_calls[0][0] == 93
    assert update_calls[0][1]["project_id"] == 1
    assert update_calls[0][1]["need_back"] == "Updated need back"
    assert update_calls[0][1]["pitchman"] == "Alex"
    assert update_calls[0][1]["next_check"] == date(2026, 3, 22)
    assert update_calls[0][1]["deadline"] == date(2026, 3, 30)
    assert update_calls[0][1]["notes"] == "context note"
    assert "now_editing_handoff_id" not in st_mock.session_state
    assert st_mock.session_state["now_flash_success"] == "Saved."


def test_render_item_keeps_expander_open_when_check_in_mode_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active check-in mode keeps the handoff expander open across reruns."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=88, need_back="Needs check-in")
    project_by_name = {"Work": SimpleNamespace(id=1, name="Work")}
    st_mock.session_state["now_action_check_in_mode_88"] = "on_track"

    _render_item(
        handoff,
        key_prefix="now_action",
        project_by_name=project_by_name,
        show_check_in_controls=True,
        allow_actions=True,
    )

    assert st_mock.expander.call_args.kwargs["expanded"] is True


def test_render_item_keeps_expander_open_when_reopen_mode_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active reopen mode keeps concluded handoff expander open."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=89, need_back="Closed")
    project_by_name = {"Work": SimpleNamespace(id=1, name="Work")}
    st_mock.session_state["now_concluded_reopen_mode_89"] = "reopen"

    _render_item(
        handoff,
        key_prefix="now_concluded",
        project_by_name=project_by_name,
        allow_actions=False,
        allow_reopen=True,
    )

    assert st_mock.expander.call_args.kwargs["expanded"] is True


def test_render_add_form_submit_calls_create_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Submitting Add persists a handoff using callback-driven state values."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    create_calls: list[dict[str, object]] = []

    def _fake_create_handoff(**kwargs) -> None:
        create_calls.append(kwargs)

    monkeypatch.setattr("handoff.pages.now.create_handoff", _fake_create_handoff)
    st_mock.session_state["now_add_project"] = "Work"
    st_mock.session_state["now_add_who"] = "  Alex  "
    st_mock.session_state["now_add_need"] = "  Ship release notes  "
    st_mock.session_state["now_add_next"] = date(2026, 3, 25)
    st_mock.session_state["now_add_deadline"] = date(2026, 3, 31)
    st_mock.session_state["now_add_context"] = "  include PR links  "

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    assert len(create_calls) == 1
    assert create_calls[0]["project_id"] == 7
    assert create_calls[0]["need_back"] == "Ship release notes"
    assert create_calls[0]["next_check"] == date(2026, 3, 25)
    assert create_calls[0]["deadline"] == date(2026, 3, 31)
    assert create_calls[0]["pitchman"] == "Alex"
    assert create_calls[0]["notes"] == "include PR links"
    assert st_mock.session_state["now_flash_success"] == "Added."
    assert _NOW_ADD_EXPANDED_KEY not in st_mock.session_state


def test_render_add_form_missing_need_back_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Submitting Add with empty need-back fails validation and does not persist."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    create_calls: list[dict[str, object]] = []

    def _fake_create_handoff(**kwargs) -> None:
        create_calls.append(kwargs)

    monkeypatch.setattr("handoff.pages.now.create_handoff", _fake_create_handoff)
    st_mock.session_state["now_add_project"] = "Work"
    st_mock.session_state["now_add_who"] = "Alex"
    st_mock.session_state["now_add_need"] = "   "
    st_mock.session_state["now_add_next"] = date(2026, 3, 25)
    st_mock.session_state["now_add_deadline"] = None
    st_mock.session_state["now_add_context"] = ""

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    assert create_calls == []
    assert st_mock.session_state["now_flash_error"] == "Need back is required."
    assert "now_flash_success" not in st_mock.session_state


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


def test_render_check_in_flow_mode_button_updates_state_without_explicit_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking a mode button updates mode state without calling st.rerun()."""
    st_mock = _build_streamlit_mock()
    st_mock.button.side_effect = _simulate_widget_submit("On-track")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=77, next_check=date(2026, 3, 9))

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert st_mock.session_state["now_action_check_in_mode_77"] == "on_track"
    st_mock.rerun.assert_not_called()


def test_render_check_in_flow_cancel_clears_mode_without_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel in check-in flow clears mode state and avoids explicit rerun."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Cancel")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=78, next_check=date(2026, 3, 9))
    st_mock.session_state["now_action_check_in_mode_78"] = "on_track"

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert "now_action_check_in_mode_78" not in st_mock.session_state
    st_mock.rerun.assert_not_called()


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
    monkeypatch.setattr(
        "handoff.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            concluded=[_make_fake_handoff(handoff_id=15, need_back="Closed item")]
        ),
    )

    render_now_page()

    labels = [call[0][0] for call in st_mock.button.call_args_list if call[0]]
    assert "Reopen" in labels


def test_render_reopen_flow_save_calls_reopen_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saving reopen appends a reopen check-in and shows updated feedback."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save reopen")
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
    st_mock.session_state["now_concluded_reopen_form_19_note"] = "  reopened  "
    st_mock.session_state["now_concluded_reopen_form_19_next_check"] = date(2026, 3, 11)

    _render_reopen_flow(handoff, key_prefix="now_concluded")

    assert len(calls) == 1
    assert calls[0]["handoff_id"] == 19
    assert "Checked in today; next check set to" in st_mock.session_state["now_flash_success"]


def test_render_reopen_flow_invalid_next_check_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid reopen date is rejected before calling reopen service."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save reopen")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    reopen_calls: list[dict[str, object]] = []

    def _fake_reopen_handoff(handoff_id: int, *, note: str | None, next_check_date: date) -> None:
        reopen_calls.append(
            {
                "handoff_id": handoff_id,
                "note": note,
                "next_check_date": next_check_date,
            }
        )

    monkeypatch.setattr("handoff.pages.now.reopen_handoff", _fake_reopen_handoff)
    handoff = _make_fake_handoff(handoff_id=20, need_back="Closed")
    st_mock.session_state["now_concluded_reopen_mode_20"] = "reopen"
    st_mock.session_state["now_concluded_reopen_form_20_note"] = "reason"
    st_mock.session_state["now_concluded_reopen_form_20_next_check"] = "tomorrow"

    _render_reopen_flow(handoff, key_prefix="now_concluded")

    assert reopen_calls == []
    assert st_mock.session_state["now_flash_error"] == "Select a valid next check-in date."
    assert st_mock.session_state["now_concluded_reopen_mode_20"] == "reopen"


def test_render_check_in_flow_save_sets_flash_message(monkeypatch: pytest.MonkeyPatch) -> None:
    """Saving a non-concluded check-in sets post-rerun success feedback."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save check-in")
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
    st_mock.session_state["now_action_check_in_form_41_on_track_note"] = "  shipped  "
    st_mock.session_state["now_action_check_in_form_41_on_track_next_check"] = date(2026, 3, 13)

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
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save conclude check-in")
    monkeypatch.setattr("handoff.pages.now.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_conclude_handoff(handoff_id: int, note: str | None = None) -> None:
        calls.append({"handoff_id": handoff_id, "note": note})

    monkeypatch.setattr("handoff.pages.now.conclude_handoff", _fake_conclude_handoff)
    handoff = _make_fake_handoff(handoff_id=42, next_check=date(2026, 3, 12))
    st_mock.session_state["now_action_check_in_mode_42"] = "concluded"
    st_mock.session_state["now_action_check_in_form_42_concluded_note"] = "  wrapped up  "

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
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save check-in")
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
    st_mock.session_state["now_action_check_in_form_43_delayed_note"] = "  waiting on dependency  "
    st_mock.session_state["now_action_check_in_form_43_delayed_next_check"] = date(2026, 3, 20)

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert len(calls) == 1
    assert calls[0]["check_in_type"] is CheckInType.DELAYED
    assert calls[0]["note"] == "waiting on dependency"
    assert calls[0]["next_check_date"] == date(2026, 3, 20)


@pytest.mark.parametrize(
    ("mode", "expected_label"),
    [
        ("on_track", "Current progress (optional)"),
        ("delayed", "Why delayed? (optional)"),
        ("concluded", "Conclusion (optional)"),
    ],
)
def test_render_check_in_flow_note_label_per_mode(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_label: str,
) -> None:
    """Each check-in mode shows the correct distinct label on its note text area."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=50, next_check=date(2026, 3, 20))
    st_mock.session_state["now_action_check_in_mode_50"] = mode

    _render_check_in_flow(handoff, key_prefix="now_action")

    text_area_labels = [call[0][0] for call in st_mock.text_area.call_args_list if call[0]]
    assert expected_label in text_area_labels


def test_render_reopen_flow_save_value_error_shows_message(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Validation errors from reopen are shown and keep form state active."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save reopen")
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
    st_mock.session_state["now_concluded_reopen_form_19_note"] = "reason"
    st_mock.session_state["now_concluded_reopen_form_19_next_check"] = date(2026, 3, 11)

    _render_reopen_flow(handoff, key_prefix="now_concluded")

    assert st_mock.session_state["now_flash_error"] == "Can only reopen concluded handoffs"
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
