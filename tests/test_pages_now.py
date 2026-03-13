"""Tests for the Now page."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handoff.core.models import CheckIn, CheckInType
from handoff.core.page_models import NowSnapshot
from handoff.interfaces.streamlit.pages.now import (
    _render_filters,
    render_now_page,
)
from handoff.interfaces.streamlit.pages.now_forms import (
    _render_add_form,
    _render_check_in_flow,
    _render_delete_confirmation,
    _render_edit_form,
    _render_item,
    _render_reopen_flow,
    _save_add_submission,
    _save_check_in_submission,
    _save_edit_submission,
    _save_reopen_submission,
)
from handoff.interfaces.streamlit.pages.now_helpers import (
    _NOW_ADD_EXPANDED_KEY,
    _build_project_options,
    _check_in_header,
    _is_check_in_due,
    _project_option_label_for_id,
    _render_check_in_trail,
)


def _make_fake_snapshot(
    *,
    risk: list | None = None,
    action: list | None = None,
    custom_sections: list | None = None,
    upcoming: list | None = None,
    upcoming_section_id: str = "upcoming",
    concluded: list | None = None,
    projects: list | None = None,
    pitchmen: list | None = None,
    section_explanations: dict | None = None,
) -> NowSnapshot:
    """Build a minimal NowSnapshot for Now page tests."""
    mock_project = SimpleNamespace(id=1, name="Work")
    return NowSnapshot(
        risk=risk or [],
        action=action or [],
        custom_sections=custom_sections or [],
        upcoming=upcoming or [],
        upcoming_section_id=upcoming_section_id,
        concluded=concluded or [],
        projects=projects or [mock_project],
        pitchmen=pitchmen or [],
        section_explanations=section_explanations or {},
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
    st_mock.toggle.return_value = False
    st_mock.button.return_value = False
    st_mock.form_submit_button.return_value = False
    st_mock.date_input.return_value = date(2026, 3, 10)
    st_mock.selectbox.return_value = "Work"
    st_mock.segmented_control.return_value = None
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


def test_build_project_options_disambiguates_duplicate_names() -> None:
    """Duplicate project names gain stable labels so widgets stay unambiguous."""
    projects = [
        SimpleNamespace(id=1, name="Work"),
        SimpleNamespace(id=2, name="Work"),
        SimpleNamespace(id=3, name="Ops"),
    ]

    project_options = _build_project_options(projects)

    assert list(project_options) == ["Work (#1)", "Work (#2)", "Ops"]
    assert project_options["Work (#2)"].id == 2
    assert _project_option_label_for_id(project_options, 2) == "Work (#2)"


def test_render_filters_duplicate_project_label_returns_selected_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Project filters keep duplicate names distinct by mapping labels back to ids."""
    st_mock = _build_streamlit_mock()
    st_mock.multiselect.side_effect = [["Work (#2)"], []]
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    project_ids, pitchman_names, search_text = _render_filters(
        project_options={
            "Work (#1)": SimpleNamespace(id=1, name="Work"),
            "Work (#2)": SimpleNamespace(id=2, name="Work"),
        },
        pitchmen=["Alice"],
        key_prefix="now",
    )

    assert project_ids == [2]
    assert pitchman_names is None
    assert search_text is None


def test_render_now_page_no_projects_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    """When there are no projects, the Now page shows an info message."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [])
    render_now_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]


def test_render_now_page_flash_error_message_is_rendered_once(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Flash errors are displayed once and cleared from session state."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state["now_flash_error"] = "Invalid form submission"
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [])

    render_now_page()

    st_mock.error.assert_called_once_with("Invalid form submission")
    assert "now_flash_error" not in st_mock.session_state


def test_render_now_page_archived_only_projects_shows_toggle_hint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When only archived projects exist, the page suggests enabling archived visibility."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    archived_project = SimpleNamespace(id=2, name="Archived")
    list_project_calls: list[bool] = []

    def _list_projects(**kwargs):
        include_archived = kwargs["include_archived"]
        list_project_calls.append(include_archived)
        return [archived_project] if include_archived else []

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", _list_projects)

    render_now_page()

    assert list_project_calls == [False, True]
    st_mock.info.assert_called_once()
    info_msg = st_mock.info.call_args[0][0]
    assert "No active projects." in info_msg
    assert "Include archived projects" in info_msg


def test_render_now_page_include_archived_falls_back_to_checkbox(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When st.toggle is unavailable, Now page falls back to checkbox."""
    st_mock = _build_streamlit_mock()
    st_mock.toggle = None
    st_mock.checkbox.return_value = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    list_project_calls: list[bool] = []

    def _list_projects(**kwargs):
        include_archived = kwargs["include_archived"]
        list_project_calls.append(include_archived)
        return []

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", _list_projects)

    render_now_page()

    st_mock.checkbox.assert_called_once_with(
        "Include archived projects",
        value=False,
        key="now_include_archived_projects",
    )
    assert list_project_calls == [True]


def test_render_now_page_include_archived_toggle_value_is_coerced_to_bool(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page coerces include-archived widget values to bool."""
    st_mock = _build_streamlit_mock()
    st_mock.toggle.return_value = "yes"
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    list_project_calls: list[bool] = []

    def _list_projects(**kwargs):
        include_archived = kwargs["include_archived"]
        list_project_calls.append(include_archived)
        return []

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", _list_projects)

    render_now_page()

    assert len(list_project_calls) == 1
    assert list_project_calls[0] is True


def test_render_now_page_calls_get_now_snapshot(monkeypatch: pytest.MonkeyPatch) -> None:
    """Now page calls get_now_snapshot with filters from the UI."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    prefetched_projects = [mock_project]
    prefetched_pitchmen = ["Alice"]
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: prefetched_projects
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: prefetched_pitchmen,
    )

    snapshot_calls: list[dict] = []

    def _capture_snapshot(**kwargs):
        snapshot_calls.append(kwargs)
        return _make_fake_snapshot()

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot", _capture_snapshot
    )

    render_now_page()

    assert len(snapshot_calls) == 1
    assert snapshot_calls[0]["include_archived_projects"] is False
    assert "project_ids" in snapshot_calls[0]
    assert "pitchman_names" in snapshot_calls[0]
    assert "search_text" in snapshot_calls[0]
    assert snapshot_calls[0]["projects"] is prefetched_projects
    assert snapshot_calls[0]["pitchmen"] is prefetched_pitchmen


def test_render_now_page_add_button_has_shortcut_when_collapsed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add handoff trigger button has shortcut 'a' when Streamlit supports it."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
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


def test_render_now_page_expanded_add_button_fallback_when_shortcut_unsupported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expanded add button retries without shortcut if Streamlit rejects it."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True

    def button_raising_shortcut(*args, **kwargs):
        if "shortcut" in kwargs:
            raise TypeError("got an unexpected keyword argument 'shortcut'")
        return False

    st_mock.button.side_effect = button_raising_shortcut
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )
    add_form_called: list[bool] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now._render_add_form",
        lambda *args, **kwargs: add_form_called.append(True),
    )

    render_now_page()

    collapse_calls = [
        c
        for c in st_mock.button.call_args_list
        if c.kwargs.get("key") == "now_add_handoff_collapse"
    ]
    assert len(collapse_calls) >= 1
    assert any("shortcut" not in call.kwargs for call in collapse_calls)
    assert add_form_called == [True]


def test_expand_add_form_sets_session_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Expand add form callback sets now_add_expanded in session state."""
    from handoff.interfaces.streamlit.pages.now_helpers import _expand_add_form

    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    _expand_add_form()

    assert st_mock.session_state[_NOW_ADD_EXPANDED_KEY] is True


def test_collapse_add_form_clears_session_state(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Collapse add form callback removes now_add_expanded from session state."""
    from handoff.interfaces.streamlit.pages.now_helpers import _collapse_add_form

    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    _collapse_add_form()

    assert _NOW_ADD_EXPANDED_KEY not in st_mock.session_state


def test_render_now_page_trigger_button_not_shown_when_form_expanded(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When the add form is expanded, the trigger button is not rendered."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

    render_now_page()

    trigger_btn_calls = [
        c for c in st_mock.button.call_args_list if c[1].get("key") == "now_add_handoff_trigger"
    ]
    assert len(trigger_btn_calls) == 0


def test_render_now_page_add_form_expands_when_add_expanded_true(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When now_add_expanded is True, the add form is rendered instead of the trigger button."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )
    add_form_called = []

    def _track_add_form(*args, **kwargs):
        add_form_called.append(True)

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now._render_add_form", _track_add_form)
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(pitchmen=["Bob", "Carol"]),
    )
    add_form_calls: list[dict] = []

    def _capture_add_form(project_options, pitchmen, key_prefix):
        add_form_calls.append(
            {
                "project_options": project_options,
                "pitchmen": pitchmen,
                "key_prefix": key_prefix,
            }
        )

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now._render_add_form", _capture_add_form
    )

    render_now_page()

    assert len(add_form_calls) == 1
    assert add_form_calls[0]["pitchmen"] == ["Bob", "Carol"]
    assert add_form_calls[0]["key_prefix"] == "now"


def test_render_now_page_include_archived_projects_passed_to_snapshot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page passes the include-archived toggle to get_now_snapshot."""
    st_mock = _build_streamlit_mock()
    st_mock.toggle.return_value = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )

    snapshot_calls: list[dict] = []

    def _capture_snapshot(**kwargs):
        snapshot_calls.append(kwargs)
        return _make_fake_snapshot()

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot", _capture_snapshot
    )

    render_now_page()

    assert len(snapshot_calls) == 1
    assert snapshot_calls[0]["include_archived_projects"] is True


def test_render_now_page_include_archived_passed_to_list_pitchmen(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Now page forwards include-archived toggle to list_pitchmen_with_open_handoffs."""
    st_mock = _build_streamlit_mock()
    st_mock.toggle.return_value = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    pitchmen_calls: list[dict] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: pitchmen_calls.append(kwargs) or ["Alice"],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(),
    )

    render_now_page()

    assert len(pitchmen_calls) == 1
    assert pitchmen_calls[0]["include_archived_projects"] is True


def test_render_now_page_action_item_shows_check_in_segmented_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Action items render On-track/Delayed/Conclude and Edit|Delete via segmented_control."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.date", FixedDate)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.date", FixedDate)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: ["Alice"],
    )

    action_handoff = _make_fake_handoff(
        handoff_id=1,
        need_back="Due now",
        next_check=date(2026, 3, 9),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(action=[action_handoff]),
    )

    render_now_page()

    assert st_mock.segmented_control.called
    seg_calls = [c for c in st_mock.segmented_control.call_args_list if c[0]]
    assert len(seg_calls) >= 2
    check_in_options = seg_calls[0].kwargs.get(
        "options", seg_calls[0].args[1] if len(seg_calls[0].args) > 1 else []
    )
    assert list(check_in_options) == ["on_track", "delayed", "concluded"]
    action_options = seg_calls[1].kwargs.get(
        "options", seg_calls[1].args[1] if len(seg_calls[1].args) > 1 else []
    )
    assert list(action_options) == ["edit", "delete"]


def test_render_now_page_risk_item_shows_check_in_segmented_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Risk items also render On-track/Delayed/Conclude and Edit|Delete via segmented_control."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    risk_handoff = _make_fake_handoff(
        handoff_id=22,
        need_back="Risk check",
        next_check=date(2026, 3, 12),
        deadline=date(2026, 3, 10),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(risk=[risk_handoff]),
    )

    render_now_page()

    assert st_mock.segmented_control.called
    seg_calls = [c for c in st_mock.segmented_control.call_args_list if c[0]]
    assert len(seg_calls) >= 2
    assert list(seg_calls[0].kwargs.get("options", [])) == ["on_track", "delayed", "concluded"]
    assert list(seg_calls[1].kwargs.get("options", [])) == ["edit", "delete"]


def test_render_now_page_upcoming_item_shows_check_in_segmented_control(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upcoming items render check-in and Edit|Delete via segmented_control."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    upcoming_handoff = _make_fake_handoff(
        handoff_id=23,
        need_back="Upcoming check",
        next_check=date(2026, 4, 1),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(upcoming=[upcoming_handoff]),
    )

    render_now_page()

    assert st_mock.segmented_control.called
    seg_calls = [c for c in st_mock.segmented_control.call_args_list if c[0]]
    assert len(seg_calls) >= 2
    assert list(seg_calls[0].kwargs.get("options", [])) == ["on_track", "delayed", "concluded"]
    assert list(seg_calls[1].kwargs.get("options", [])) == ["edit", "delete"]


def test_render_now_page_concluded_section_renders_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Concluded handoffs are rendered as item expanders with no dataframe."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    risk_handoff = _make_fake_handoff(
        handoff_id=2,
        need_back="At risk",
        deadline=date(2026, 3, 9),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(risk=[risk_handoff]),
    )

    render_now_page()

    expander_headers = [str(call[0][0]) for call in st_mock.expander.call_args_list]
    assert any("At risk" in h for h in expander_headers)


def test_render_now_page_upcoming_section_renders_items(monkeypatch: pytest.MonkeyPatch) -> None:
    """Upcoming items appear in the Upcoming section with their expanders."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    upcoming_handoff = _make_fake_handoff(
        handoff_id=3,
        need_back="Check later",
        next_check=date(2026, 4, 1),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    handoff_with_notes = _make_fake_handoff(
        handoff_id=4,
        need_back="Has notes",
        notes="Important context here",
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(upcoming=[handoff_with_notes]),
    )

    render_now_page()

    markdown_calls = [str(c) for c in st_mock.markdown.call_args_list]
    assert any("Important context here" in c for c in markdown_calls)


def test_render_now_page_section_explanations_rendered_for_open_sections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Rule-based explanations appear for Risk, Action, and Upcoming items."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    risk_handoff = _make_fake_handoff(
        handoff_id=10,
        need_back="At risk item",
        deadline=date(2026, 3, 9),
    )
    action_handoff = _make_fake_handoff(
        handoff_id=11,
        need_back="Action item",
        next_check=date(2026, 3, 9),
    )
    upcoming_handoff = _make_fake_handoff(
        handoff_id=12,
        need_back="Upcoming item",
        next_check=date(2026, 3, 20),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            risk=[risk_handoff],
            action=[action_handoff],
            upcoming=[upcoming_handoff],
            section_explanations={
                "risk": "Deadline is near and latest check-in is delayed.",
                "action_required": "Next check date is due today.",
                "upcoming": "No risk or action rules matched.",
            },
        ),
    )

    render_now_page()

    caption_calls = [str(c) for c in st_mock.caption.call_args_list]
    assert any("Deadline is near and latest check-in is delayed" in c for c in caption_calls)
    assert any("Next check date is due today" in c for c in caption_calls)
    assert any("No risk or action rules matched" in c for c in caption_calls)


def test_render_now_page_upcoming_caption_uses_upcoming_section_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upcoming caption lookup uses snapshot.upcoming_section_id instead of fixed key."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            upcoming_section_id="manual_triage",
            section_explanations={
                "upcoming": "Wrong explanation for this test.",
                "manual_triage": "Manual triage explanation.",
            },
        ),
    )

    render_now_page()

    caption_calls = [str(c) for c in st_mock.caption.call_args_list]
    assert any("Manual triage explanation." in c for c in caption_calls)
    assert not any("Wrong explanation for this test." in c for c in caption_calls)


def test_render_now_page_custom_sections_rendered_between_action_and_upcoming(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom sections from snapshot are rendered between Action and Upcoming."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    custom_handoff = _make_fake_handoff(
        handoff_id=20,
        need_back="Blocked item",
        next_check=date(2026, 3, 20),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            risk=[],
            action=[],
            custom_sections=[("blocked", [custom_handoff])],
            upcoming=[],
            section_explanations={"blocked": "Latest check-in is delayed."},
        ),
    )

    render_now_page()

    markdown_calls = [str(c) for c in st_mock.markdown.call_args_list]
    assert any("Blocked" in c for c in markdown_calls)
    assert any("Blocked item" in c or "blocked" in c.lower() for c in markdown_calls)
    caption_calls = [str(c) for c in st_mock.caption.call_args_list]
    assert any("Latest check-in is delayed" in c for c in caption_calls)


def test_render_now_page_empty_custom_section_shows_no_handoffs_caption(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Empty custom sections render with 'No handoffs in X' info message."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            risk=[],
            action=[],
            custom_sections=[("waiting_on_input", [])],
            upcoming=[],
        ),
    )

    render_now_page()

    info_calls = [str(c) for c in st_mock.info.call_args_list]
    assert any("No handoffs" in c and "Waiting On Input" in c for c in info_calls)


def test_render_now_page_empty_custom_section_still_shows_explanation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Custom section explanation is shown even when the section has no handoffs."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(
            custom_sections=[("waiting_on_input", [])],
            section_explanations={"waiting_on_input": "Waiting on upstream dependency."},
        ),
    )

    render_now_page()

    caption_calls = [str(c) for c in st_mock.caption.call_args_list]
    assert any("Waiting on upstream dependency." in c for c in caption_calls)


def test_render_item_edit_save_validation_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Invalid edit save keeps edit mode active and sets flash error."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    update_calls: list[tuple[int, dict[str, object]]] = []

    def _fake_update_handoff(handoff_id: int, **changes) -> None:
        update_calls.append((handoff_id, changes))

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.update_handoff", _fake_update_handoff
    )
    handoff = _make_fake_handoff(handoff_id=92, need_back="Original")
    st_mock.session_state["now_action_action_mode_92"] = "edit"
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
        project_options={"Work": SimpleNamespace(id=1, name="Work")},
        allow_actions=True,
        show_check_in_controls=True,
    )

    assert update_calls == []
    assert st_mock.session_state["now_flash_error"] == "Need back is required."
    assert st_mock.session_state["now_action_action_mode_92"] == "edit"


def test_render_item_edit_save_success_clears_editing_and_sets_flash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Valid edit save updates the handoff and clears editing state."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    update_calls: list[tuple[int, dict[str, object]]] = []

    def _fake_update_handoff(handoff_id: int, **changes) -> None:
        update_calls.append((handoff_id, changes))

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.update_handoff", _fake_update_handoff
    )
    handoff = _make_fake_handoff(handoff_id=93, need_back="Original")
    st_mock.session_state["now_action_action_mode_93"] = "edit"
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
        project_options={"Work": SimpleNamespace(id=1, name="Work")},
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
    assert "now_action_action_mode_93" not in st_mock.session_state
    assert st_mock.session_state["now_flash_success"] == "Saved."


def test_render_edit_form_defaults_to_current_duplicate_project(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit form keeps the handoff on its current duplicate-named project by default."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    handoff = _make_fake_handoff(handoff_id=94, project_name="Work")
    handoff.project = SimpleNamespace(id=2, name="Work")

    _render_edit_form(
        handoff,
        {
            "Work (#1)": SimpleNamespace(id=1, name="Work"),
            "Work (#2)": SimpleNamespace(id=2, name="Work"),
        },
        key_prefix="now_action_edit_94",
        action_mode_key="now_action_action_mode_94",
    )

    assert st_mock.selectbox.call_args.kwargs["options"] == ["Work (#1)", "Work (#2)"]
    assert st_mock.selectbox.call_args.kwargs["index"] == 1


def test_render_delete_confirmation_shows_irreversible_warning(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delete mode shows irreversible warning and Confirm delete button."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=94, need_back="Item to delete")

    _render_delete_confirmation(handoff, key_prefix="now_action")

    st_mock.warning.assert_called_once_with("This action is irreversible.")
    labels = [call[0][0] for call in st_mock.button.call_args_list if call[0]]
    assert "Confirm delete" in labels
    assert "Cancel" in labels


def test_render_delete_confirmation_confirm_calls_delete_handoff(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Confirm delete button calls delete_handoff and clears action mode."""
    st_mock = _build_streamlit_mock()

    def _simulate_confirm_click(*args, **kwargs):
        if args and args[0] == "Confirm delete":
            on_click = kwargs.get("on_click")
            if callable(on_click):
                on_click(**kwargs.get("kwargs", {}))
        return False

    st_mock.button.side_effect = _simulate_confirm_click
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    delete_calls: list[int] = []

    def _fake_delete(handoff_id: int) -> bool:
        delete_calls.append(handoff_id)
        return True

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.delete_handoff", _fake_delete)
    handoff = _make_fake_handoff(handoff_id=95, need_back="Delete me")
    st_mock.session_state["now_action_action_mode_95"] = "delete"

    _render_delete_confirmation(handoff, key_prefix="now_action")

    assert delete_calls == [95]
    assert "now_action_action_mode_95" not in st_mock.session_state
    assert st_mock.session_state["now_flash_success"] == "Handoff deleted."


def test_render_delete_confirmation_cancel_clears_action_mode_without_delete(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Cancel in delete confirmation clears mode and does not call delete service."""
    st_mock = _build_streamlit_mock()

    def _simulate_cancel_click(*args, **kwargs):
        if args and args[0] == "Cancel":
            on_click = kwargs.get("on_click")
            if callable(on_click):
                on_click(**kwargs.get("kwargs", {}))
        return False

    st_mock.button.side_effect = _simulate_cancel_click
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    delete_calls: list[int] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.delete_handoff",
        lambda handoff_id: delete_calls.append(handoff_id) or True,
    )
    handoff = _make_fake_handoff(handoff_id=96, need_back="Keep me")
    st_mock.session_state["now_action_action_mode_96"] = "delete"

    _render_delete_confirmation(handoff, key_prefix="now_action")

    assert delete_calls == []
    assert "now_action_action_mode_96" not in st_mock.session_state
    assert "now_flash_success" not in st_mock.session_state
    assert "now_flash_error" not in st_mock.session_state


def test_render_delete_confirmation_confirm_failure_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed delete keeps mode active and sets an actionable error message."""
    st_mock = _build_streamlit_mock()

    def _simulate_confirm_click(*args, **kwargs):
        if args and args[0] == "Confirm delete":
            on_click = kwargs.get("on_click")
            if callable(on_click):
                on_click(**kwargs.get("kwargs", {}))
        return False

    st_mock.button.side_effect = _simulate_confirm_click
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    delete_calls: list[int] = []

    def _fake_delete(handoff_id: int) -> bool:
        delete_calls.append(handoff_id)
        return False

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.delete_handoff", _fake_delete)
    handoff = _make_fake_handoff(handoff_id=97, need_back="Delete fails")
    st_mock.session_state["now_action_action_mode_97"] = "delete"

    _render_delete_confirmation(handoff, key_prefix="now_action")

    assert delete_calls == [97]
    assert st_mock.session_state["now_action_action_mode_97"] == "delete"
    assert st_mock.session_state["now_flash_error"] == "Could not delete handoff."
    assert "now_flash_success" not in st_mock.session_state


def test_render_item_keeps_expander_open_when_check_in_mode_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active check-in mode keeps the handoff expander open across reruns."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=88, need_back="Needs check-in")
    project_options = {"Work": SimpleNamespace(id=1, name="Work")}
    st_mock.session_state["now_action_check_in_mode_88"] = "on_track"

    _render_item(
        handoff,
        key_prefix="now_action",
        project_options=project_options,
        show_check_in_controls=True,
        allow_actions=True,
    )

    assert st_mock.expander.call_args.kwargs["expanded"] is True


def test_render_item_keeps_expander_open_when_reopen_mode_active(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Active reopen mode keeps concluded handoff expander open."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=89, need_back="Closed")
    project_options = {"Work": SimpleNamespace(id=1, name="Work")}
    st_mock.session_state["now_concluded_reopen_mode_89"] = "reopen"

    _render_item(
        handoff,
        key_prefix="now_concluded",
        project_options=project_options,
        allow_actions=False,
        allow_reopen=True,
    )

    assert st_mock.expander.call_args.kwargs["expanded"] is True


def test_render_add_form_submit_calls_create_handoff(monkeypatch: pytest.MonkeyPatch) -> None:
    """Submitting Add persists a handoff using callback-driven state values."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []

    def _fake_create_handoff(**kwargs) -> None:
        create_calls.append(kwargs)

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff", _fake_create_handoff
    )
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


def test_render_add_form_duplicate_project_label_calls_create_handoff_for_selected_id(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add form uses the selected duplicate-name label's project id."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff",
        lambda **kw: create_calls.append(kw),
    )
    st_mock.session_state["now_add_project"] = "Work (#2)"
    st_mock.session_state["now_add_who"] = "Alex"
    st_mock.session_state["now_add_need"] = "Ship release notes"
    st_mock.session_state["now_add_next"] = date(2026, 3, 25)
    st_mock.session_state["now_add_deadline"] = None
    st_mock.session_state["now_add_context"] = ""

    _render_add_form(
        {
            "Work (#1)": SimpleNamespace(id=1, name="Work"),
            "Work (#2)": SimpleNamespace(id=2, name="Work"),
        },
        [],
        key_prefix="now",
    )

    assert len(create_calls) == 1
    assert create_calls[0]["project_id"] == 2


def test_render_add_form_sets_clear_on_submit_false(monkeypatch: pytest.MonkeyPatch) -> None:
    """Add form keeps widget values after failed submits by disabling auto-clear."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    st_mock.form.assert_called_once_with(key="now_add_form", clear_on_submit=False)


def test_render_add_form_marks_required_field_labels(monkeypatch: pytest.MonkeyPatch) -> None:
    """Required add-form fields include visual indicators in their labels."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    selectbox_labels = [call.args[0] for call in st_mock.selectbox.call_args_list if call.args]
    text_input_labels = [call.args[0] for call in st_mock.text_input.call_args_list if call.args]
    date_input_labels = [call.args[0] for call in st_mock.date_input.call_args_list if call.args]

    assert "Project *" in selectbox_labels
    assert "Need back *" in text_input_labels
    assert "Next check *" in date_input_labels


def test_render_add_form_missing_need_back_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Submitting Add with empty need-back fails validation and does not persist."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []

    def _fake_create_handoff(**kwargs) -> None:
        create_calls.append(kwargs)

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff", _fake_create_handoff
    )
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


def test_render_add_form_validation_failure_does_not_collapse_form(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Failed add submission does not collapse the add form so the user can correct input."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff",
        lambda **kw: create_calls.append(kw),
    )
    st_mock.session_state["now_add_project"] = "Work"
    st_mock.session_state["now_add_who"] = "Alex"
    st_mock.session_state["now_add_need"] = "   "
    st_mock.session_state["now_add_next"] = date(2026, 3, 25)
    st_mock.session_state["now_add_deadline"] = None
    st_mock.session_state["now_add_context"] = ""

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    assert create_calls == []
    assert _NOW_ADD_EXPANDED_KEY in st_mock.session_state


def test_render_add_form_close_button_collapses_form_without_save(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Clicking Close dismisses the add form without persisting any handoff."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Close")
    st_mock.session_state[_NOW_ADD_EXPANDED_KEY] = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff",
        lambda **kw: create_calls.append(kw),
    )
    st_mock.session_state["now_add_project"] = "Work"
    st_mock.session_state["now_add_who"] = "Alex"
    st_mock.session_state["now_add_need"] = "Some deliverable"
    st_mock.session_state["now_add_next"] = date(2026, 3, 25)
    st_mock.session_state["now_add_deadline"] = None
    st_mock.session_state["now_add_context"] = ""

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    assert create_calls == []
    assert _NOW_ADD_EXPANDED_KEY not in st_mock.session_state


def test_render_add_form_invalid_project_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add form with an unknown project name rejects the submission."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff",
        lambda **kw: create_calls.append(kw),
    )
    st_mock.session_state["now_add_project"] = "DoesNotExist"
    st_mock.session_state["now_add_who"] = "Alex"
    st_mock.session_state["now_add_need"] = "Ship release notes"
    st_mock.session_state["now_add_next"] = date(2026, 3, 25)
    st_mock.session_state["now_add_deadline"] = None
    st_mock.session_state["now_add_context"] = ""

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    assert create_calls == []
    assert st_mock.session_state["now_flash_error"] == "Select a project."


def test_render_add_form_invalid_next_check_sets_flash_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add form with a non-date next_check value rejects the submission."""
    st_mock = _build_streamlit_mock()
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Add")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_calls: list[dict[str, object]] = []
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.create_handoff",
        lambda **kw: create_calls.append(kw),
    )
    st_mock.session_state["now_add_project"] = "Work"
    st_mock.session_state["now_add_who"] = "Alex"
    st_mock.session_state["now_add_need"] = "Ship release notes"
    st_mock.session_state["now_add_next"] = "not-a-date"
    st_mock.session_state["now_add_deadline"] = None
    st_mock.session_state["now_add_context"] = ""

    _render_add_form({"Work": SimpleNamespace(id=7, name="Work")}, [], key_prefix="now")

    assert create_calls == []
    assert st_mock.session_state["now_flash_error"] == "Select a valid next check date."


@pytest.mark.parametrize(
    ("mode", "expected_label"),
    [
        ("on_track", "Current progress (optional)"),
        ("delayed", "Why? (optional)"),
    ],
)
def test_render_check_in_flow_note_label_matches_mode(
    monkeypatch: pytest.MonkeyPatch,
    mode: str,
    expected_label: str,
) -> None:
    """Check-in note text_area uses the correct label for on_track and delayed modes."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=50, next_check=date(2026, 3, 9))
    st_mock.session_state["now_action_check_in_mode_50"] = mode

    _render_check_in_flow(handoff, key_prefix="now_action")

    text_area_labels = [call[0][0] for call in st_mock.text_area.call_args_list if call[0]]
    assert expected_label in text_area_labels


def test_render_check_in_flow_conclude_uses_conclusion_label(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conclude mode uses 'Conclusion (optional)' label for the note field."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=51, next_check=date(2026, 3, 9))
    st_mock.session_state["now_action_check_in_mode_51"] = "concluded"

    _render_check_in_flow(handoff, key_prefix="now_action")

    text_area_labels = [call[0][0] for call in st_mock.text_area.call_args_list if call[0]]
    assert "Conclusion (optional)" in text_area_labels


def test_render_check_in_flow_due_shows_due_caption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Due handoffs keep due-state check-in messaging."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=31, next_check=date(2000, 1, 1))

    _render_check_in_flow(handoff, key_prefix="now_action")

    captions = [call[0][0] for call in st_mock.caption.call_args_list if call[0]]
    assert any("Check-in due now" in text for text in captions)


def test_render_check_in_flow_non_due_shows_early_caption(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-due handoffs offer optional early check-in messaging."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=32, next_check=date(2099, 1, 1))

    _render_check_in_flow(handoff, key_prefix="now_upcoming")

    captions = [call[0][0] for call in st_mock.caption.call_args_list if call[0]]
    assert any("Optional early check-in" in text for text in captions)


def test_render_check_in_flow_mode_segmented_control_updates_state_without_rerun(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Selecting a check-in mode via segmented_control updates state without st.rerun()."""
    st_mock = _build_streamlit_mock()

    def _seg_effect(*args, key=None, **kwargs):
        if key:
            st_mock.session_state[key] = "on_track"
        return "on_track"

    st_mock.segmented_control.side_effect = _seg_effect
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=35, next_check=date(2099, 1, 5))
    st_mock.session_state["now_action_check_in_mode_35"] = mode

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert st_mock.date_input.call_count == 1
    assert st_mock.date_input.call_args.kwargs["value"] == date(2099, 1, 5)


def test_render_check_in_flow_prefills_next_business_day_for_due_item(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Overdue next_check values default to the next business day when checking in."""
    from handoff.dates import add_business_days

    class _FrozenDate(date):
        @classmethod
        def today(cls) -> date:  # type: ignore[override]
            return cls(2030, 1, 1)

    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.date", _FrozenDate)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.date", _FrozenDate)
    handoff = _make_fake_handoff(handoff_id=36, next_check=date(2000, 1, 5))
    st_mock.session_state["now_action_check_in_mode_36"] = "on_track"

    _render_check_in_flow(handoff, key_prefix="now_action")

    expected_default = add_business_days(_FrozenDate.today(), 1)
    assert st_mock.date_input.call_count == 1
    assert st_mock.date_input.call_args.kwargs["value"] == expected_default


def test_render_now_page_concluded_item_shows_reopen_button(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Concluded section renders a dedicated Reopen action."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_reopen_handoff(handoff_id: int, *, note: str | None, next_check_date: date) -> None:
        calls.append(
            {
                "handoff_id": handoff_id,
                "note": note,
                "next_check_date": next_check_date,
            }
        )

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.reopen_handoff", _fake_reopen_handoff
    )
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    reopen_calls: list[dict[str, object]] = []

    def _fake_reopen_handoff(handoff_id: int, *, note: str | None, next_check_date: date) -> None:
        reopen_calls.append(
            {
                "handoff_id": handoff_id,
                "note": note,
                "next_check_date": next_check_date,
            }
        )

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.reopen_handoff", _fake_reopen_handoff
    )
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

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

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.add_check_in", _fake_add_check_in
    )
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    calls: list[dict[str, object]] = []

    def _fake_conclude_handoff(handoff_id: int, note: str | None = None) -> None:
        calls.append({"handoff_id": handoff_id, "note": note})

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.conclude_handoff", _fake_conclude_handoff
    )
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

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

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.add_check_in", _fake_add_check_in
    )
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
        ("delayed", "Why? (optional)"),
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    def _raise_value_error(
        handoff_id: int,
        *,
        note: str | None,
        next_check_date: date,
    ) -> None:
        raise ValueError("Can only reopen concluded handoffs")

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.reopen_handoff", _raise_value_error
    )
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
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    fake_handoff = SimpleNamespace(check_ins=[])
    _render_check_in_trail(fake_handoff)
    st_mock.caption.assert_called_once_with("No check-ins yet.")
    st_mock.expander.assert_not_called()


def test_render_check_in_trail_with_entry_no_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check-in without a note shows 'No note.' caption inside the expander."""
    st_mock = MagicMock()
    st_mock.expander.return_value = _Ctx()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    ci = _make_check_in(check_in_type=CheckInType.ON_TRACK, note=None)
    fake_handoff = SimpleNamespace(check_ins=[ci])
    _render_check_in_trail(fake_handoff)

    st_mock.expander.assert_called_once()
    st_mock.caption.assert_called_with("No note.")


def test_render_check_in_trail_with_entry_with_note(monkeypatch: pytest.MonkeyPatch) -> None:
    """A check-in with a note renders the note as markdown inside the expander."""
    st_mock = MagicMock()
    st_mock.expander.return_value = _Ctx()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

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


def test_save_check_in_submission_with_missing_next_check_key_sets_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check-in submission with missing next_check_key sets flash error."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    services_mock = MagicMock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.add_check_in", services_mock)

    st_mock.session_state["test_mode"] = "on_track"
    st_mock.session_state["test_note"] = "Going well"

    _save_check_in_submission(
        handoff_id=1,
        selected_mode="on_track",
        mode_key="test_mode",
        note_key="test_note",
        next_check_key=None,  # Missing
    )

    assert st_mock.session_state["now_flash_error"] == "Select a valid next check-in date."
    services_mock.assert_not_called()


def test_save_check_in_submission_with_invalid_next_check_date_sets_error(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check-in submission with invalid next_check_date type sets flash error."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    services_mock = MagicMock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.add_check_in", services_mock)

    st_mock.session_state["test_mode"] = "on_track"
    st_mock.session_state["test_note"] = "Going well"
    st_mock.session_state["test_next_check"] = "2026-03-10"  # Invalid: not a date object

    _save_check_in_submission(
        handoff_id=1,
        selected_mode="on_track",
        mode_key="test_mode",
        note_key="test_note",
        next_check_key="test_next_check",
    )

    assert st_mock.session_state["now_flash_error"] == "Select a valid next check-in date."
    services_mock.assert_not_called()


def test_save_check_in_submission_conclude_logs_instrumentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Conclude action flow logs instrumentation with time_action."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    conclude_mock = MagicMock()
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.conclude_handoff", conclude_mock
    )

    logger_mock = MagicMock()
    monkeypatch.setattr("handoff.instrumentation.logger", logger_mock)

    st_mock.session_state["test_mode"] = "concluded"
    st_mock.session_state["test_note"] = "Done"

    _save_check_in_submission(
        handoff_id=1,
        selected_mode="concluded",
        mode_key="test_mode",
        note_key="test_note",
        next_check_key="test_next_check",
    )

    conclude_mock.assert_called_once_with(1, note="Done")
    logger_mock.info.assert_called_once()
    call_args = logger_mock.info.call_args[0]
    assert call_args[1] == "now_conclude"
    assert "elapsed_ms" in call_args[0]


def test_save_check_in_submission_on_track_logs_instrumentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On-track check-in logs instrumentation with time_action."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    check_in_mock = MagicMock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.add_check_in", check_in_mock)

    logger_mock = MagicMock()
    monkeypatch.setattr("handoff.instrumentation.logger", logger_mock)

    st_mock.session_state["test_mode"] = "on_track"
    st_mock.session_state["test_note"] = "Good progress"
    st_mock.session_state["test_next_check"] = date(2026, 3, 16)

    _save_check_in_submission(
        handoff_id=1,
        selected_mode="on_track",
        mode_key="test_mode",
        note_key="test_note",
        next_check_key="test_next_check",
    )

    check_in_mock.assert_called_once()
    logger_mock.info.assert_called_once()
    call_args = logger_mock.info.call_args[0]
    assert call_args[1] == "now_check_in"


def test_save_reopen_submission_logs_instrumentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopen action logs instrumentation with time_action."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    reopen_mock = MagicMock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.reopen_handoff", reopen_mock)

    logger_mock = MagicMock()
    monkeypatch.setattr("handoff.instrumentation.logger", logger_mock)

    st_mock.session_state["test_reopen_mode"] = "reopen"
    st_mock.session_state["test_reopen_note"] = "Reopening"
    st_mock.session_state["test_reopen_next_check"] = date(2026, 3, 16)

    _save_reopen_submission(
        handoff_id=1,
        mode_key="test_reopen_mode",
        note_key="test_reopen_note",
        next_check_key="test_reopen_next_check",
    )

    reopen_mock.assert_called_once()
    logger_mock.info.assert_called_once()
    call_args = logger_mock.info.call_args[0]
    assert call_args[1] == "now_reopen"


def test_save_reopen_submission_with_error_logs_and_sets_flash(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Reopen error logs instrumentation and sets flash instead of raising."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    reopen_mock = MagicMock(side_effect=ValueError("Cannot reopen"))
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.reopen_handoff", reopen_mock)

    logger_mock = MagicMock()
    monkeypatch.setattr("handoff.instrumentation.logger", logger_mock)

    st_mock.session_state["test_reopen_mode"] = "reopen"
    st_mock.session_state["test_reopen_note"] = "Reopening"
    st_mock.session_state["test_reopen_next_check"] = date(2026, 3, 16)

    _save_reopen_submission(
        handoff_id=1,
        mode_key="test_reopen_mode",
        note_key="test_reopen_note",
        next_check_key="test_reopen_next_check",
    )

    logger_mock.info.assert_called_once()
    assert st_mock.session_state["now_flash_error"] == "Cannot reopen"


def test_save_edit_submission_logs_instrumentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit action logs instrumentation with time_action."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    update_mock = MagicMock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.update_handoff", update_mock)

    logger_mock = MagicMock()
    monkeypatch.setattr("handoff.instrumentation.logger", logger_mock)

    st_mock.session_state["test_project"] = "Work"
    st_mock.session_state["test_need"] = "Updated need"
    st_mock.session_state["test_who"] = "Bob"
    st_mock.session_state["test_next_check"] = date(2026, 3, 16)
    st_mock.session_state["test_deadline"] = date(2026, 3, 20)
    st_mock.session_state["test_context"] = "Context"

    _save_edit_submission(
        handoff_id=1,
        project_options={"Work": SimpleNamespace(id=1)},
        project_key="test_project",
        who_key="test_who",
        need_key="test_need",
        next_check_key="test_next_check",
        deadline_key="test_deadline",
        context_key="test_context",
    )

    update_mock.assert_called_once()
    logger_mock.info.assert_called_once()
    call_args = logger_mock.info.call_args[0]
    assert call_args[1] == "now_edit"


def test_save_add_submission_logs_instrumentation(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Add action logs instrumentation with time_action."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    create_mock = MagicMock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.create_handoff", create_mock)

    logger_mock = MagicMock()
    monkeypatch.setattr("handoff.instrumentation.logger", logger_mock)

    st_mock.session_state["test_project"] = "Work"
    st_mock.session_state["test_need"] = "New need"
    st_mock.session_state["test_who"] = "Alice"
    st_mock.session_state["test_next_check"] = date(2026, 3, 16)
    st_mock.session_state["test_deadline"] = None
    st_mock.session_state["test_context"] = "New context"

    _save_add_submission(
        project_options={"Work": SimpleNamespace(id=1)},
        project_key="test_project",
        who_key="test_who",
        need_key="test_need",
        next_check_key="test_next_check",
        deadline_key="test_deadline",
        context_key="test_context",
    )

    create_mock.assert_called_once()
    logger_mock.info.assert_called_once()
    call_args = logger_mock.info.call_args[0]
    assert call_args[1] == "now_add"


def test_render_now_page_flash_success_displays(monkeypatch: pytest.MonkeyPatch) -> None:
    """Flash success message is displayed when present in session state."""
    st_mock = _build_streamlit_mock()
    st_mock.session_state["now_flash_success"] = "Operation successful"
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", lambda **kw: [])

    render_now_page()

    st_mock.success.assert_called_once_with("Operation successful")


def test_render_now_page_no_projects_with_include_archived_true_shows_create_info(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When include_archived=True and truly no projects, shows create info."""
    st_mock = _build_streamlit_mock()
    st_mock.toggle.return_value = True
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.list_projects", lambda **kw: [])

    render_now_page()

    info_calls = [c[0][0] for c in st_mock.info.call_args_list if c[0]]
    assert any("Create one on the Projects page" in str(call) for call in info_calls)


# --- Regression tests for PR #88: Snooze removal + segmented_control ---


def test_render_item_does_not_auto_expand_due_action_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Due action items start collapsed; user must expand to see check-in controls."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.date", FixedDate)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.date", FixedDate)

    due_handoff = _make_fake_handoff(
        handoff_id=100,
        need_back="Due now",
        next_check=date(2026, 3, 9),
    )
    project_options = {"Work": SimpleNamespace(id=1, name="Work")}

    _render_item(
        due_handoff,
        key_prefix="now_action",
        project_options=project_options,
        show_check_in_controls=True,
        allow_actions=True,
    )

    # Expander starts collapsed; user expands manually
    assert st_mock.expander.call_args.kwargs["expanded"] is False


def test_render_item_does_not_auto_expand_future_items(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Future action items do not auto-expand (unless check-in mode is active)."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    future_handoff = _make_fake_handoff(
        handoff_id=101,
        need_back="Future check",
        next_check=date(2099, 1, 1),
    )
    project_options = {"Work": SimpleNamespace(id=1, name="Work")}

    _render_item(
        future_handoff,
        key_prefix="now_action",
        project_options=project_options,
        show_check_in_controls=True,
        allow_actions=True,
    )

    # Expander starts collapsed (no active mode, not due)
    assert st_mock.expander.call_args.kwargs["expanded"] is False


def test_render_item_only_expands_handoff_with_active_check_in_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the handoff with active check-in mode should start expanded."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    class FixedDate(date):
        @classmethod
        def today(cls) -> date:
            return date(2026, 3, 9)

    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.date", FixedDate)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.date", FixedDate)

    first_handoff = _make_fake_handoff(
        handoff_id=201,
        need_back="First due item",
        next_check=date(2026, 3, 9),
    )
    second_handoff = _make_fake_handoff(
        handoff_id=202,
        need_back="Second due item",
        next_check=date(2026, 3, 9),
    )
    project_options = {"Work": SimpleNamespace(id=1, name="Work")}
    st_mock.session_state["now_action_check_in_mode_202"] = "on_track"

    _render_item(
        first_handoff,
        key_prefix="now_action",
        project_options=project_options,
        show_check_in_controls=True,
        allow_actions=True,
    )
    _render_item(
        second_handoff,
        key_prefix="now_action",
        project_options=project_options,
        show_check_in_controls=True,
        allow_actions=True,
    )

    expanded_states = [call.kwargs["expanded"] for call in st_mock.expander.call_args_list[-2:]]
    assert expanded_states == [False, True]


def test_render_item_only_expands_handoff_with_active_reopen_mode(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Only the handoff with active reopen mode should start expanded."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

    first_handoff = _make_fake_handoff(handoff_id=301, need_back="Closed first")
    second_handoff = _make_fake_handoff(handoff_id=302, need_back="Closed second")
    project_options = {"Work": SimpleNamespace(id=1, name="Work")}
    st_mock.session_state["now_concluded_reopen_mode_302"] = "reopen"

    _render_item(
        first_handoff,
        key_prefix="now_concluded",
        project_options=project_options,
        allow_actions=False,
        allow_reopen=True,
    )
    _render_item(
        second_handoff,
        key_prefix="now_concluded",
        project_options=project_options,
        allow_actions=False,
        allow_reopen=True,
    )

    expanded_states = [call.kwargs["expanded"] for call in st_mock.expander.call_args_list[-2:]]
    assert expanded_states == [False, True]


def test_render_check_in_flow_edit_button_visible_with_allow_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit|Delete segmented control is visible in check-in flow when allow_actions is True."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=102, next_check=date(2026, 3, 20))

    _render_check_in_flow(
        handoff,
        key_prefix="now_action",
        allow_actions=True,
    )

    seg_calls = st_mock.segmented_control.call_args_list
    action_seg = next(
        (c for c in seg_calls if c.kwargs.get("options") == ["edit", "delete"]),
        None,
    )
    assert action_seg is not None


def test_render_check_in_flow_edit_button_hidden_without_allow_actions(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Edit|Delete segmented control is not rendered when allow_actions is False."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=103, next_check=date(2026, 3, 20))

    _render_check_in_flow(
        handoff,
        key_prefix="now_concluded",
        allow_actions=False,
    )

    seg_calls = st_mock.segmented_control.call_args_list
    assert len(seg_calls) == 1  # Only check-in control, no action control


def test_render_check_in_flow_segmented_control_options_correct(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segmented control always shows on_track, delayed, concluded options."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=104, next_check=date(2026, 3, 20))

    _render_check_in_flow(handoff, key_prefix="now_action")

    seg_calls = st_mock.segmented_control.call_args_list
    assert len(seg_calls) >= 1
    options = seg_calls[0].kwargs.get(
        "options", seg_calls[0].args[1] if len(seg_calls[0].args) > 1 else []
    )
    assert list(options) == ["on_track", "delayed", "concluded"]


def test_render_check_in_flow_segmented_control_has_format_func(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segmented control uses format_func to display friendly labels."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=105, next_check=date(2026, 3, 20))

    _render_check_in_flow(handoff, key_prefix="now_action")

    seg_calls = st_mock.segmented_control.call_args_list
    assert len(seg_calls) >= 1
    format_func = seg_calls[0].kwargs.get("format_func")
    assert format_func is not None
    # Verify format_func produces correct labels
    assert format_func("on_track") == "On-track"
    assert format_func("delayed") == "Delayed"
    assert format_func("concluded") == "Conclude"


def test_render_check_in_flow_segmented_control_key_matches_prefix(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Segmented control key follows the naming pattern for state management."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=106, next_check=date(2026, 3, 20))

    _render_check_in_flow(handoff, key_prefix="now_risk")

    seg_calls = st_mock.segmented_control.call_args_list
    assert len(seg_calls) >= 1
    key = seg_calls[0].kwargs.get("key")
    assert key == "now_risk_check_in_mode_106"


def test_render_check_in_flow_note_label_on_track_unchanged(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """On-track mode shows 'Current progress (optional)' label."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=107, next_check=date(2026, 3, 20))
    st_mock.session_state["now_action_check_in_mode_107"] = "on_track"

    _render_check_in_flow(handoff, key_prefix="now_action")

    text_area_labels = [call[0][0] for call in st_mock.text_area.call_args_list if call[0]]
    assert "Current progress (optional)" in text_area_labels


def test_render_check_in_flow_note_label_delayed_changed_from_why_delayed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Delayed mode shows 'Why? (optional)' label (was 'Why delayed?')."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=108, next_check=date(2026, 3, 20))
    st_mock.session_state["now_action_check_in_mode_108"] = "delayed"

    _render_check_in_flow(handoff, key_prefix="now_action")

    text_area_labels = [call[0][0] for call in st_mock.text_area.call_args_list if call[0]]
    assert "Why? (optional)" in text_area_labels
    # Verify the old label is NOT used
    assert not any("Why delayed?" in label for label in text_area_labels)


def test_render_item_columns_layout_for_check_in_controls(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Check-in flow uses [3, 1] column layout for check-in and Edit|Delete segmented controls."""
    st_mock = _build_streamlit_mock()
    columns_calls: list = []

    def _capture_columns(spec):
        columns_calls.append(spec)
        return [_Ctx() for _ in range(2)]  # Return 2 contexts for [3, 1]

    st_mock.columns.side_effect = _capture_columns
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    handoff = _make_fake_handoff(handoff_id=109, next_check=date(2026, 3, 20))

    _render_check_in_flow(handoff, key_prefix="now_action")

    # Verify columns([3, 1]) was called for layout
    assert [3, 1] in columns_calls


def test_render_check_in_flow_upcoming_shows_controls_and_edit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Upcoming items render check-in segmented control with Edit|Delete control."""
    st_mock = _build_streamlit_mock()
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_projects", lambda **kwargs: [mock_project]
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.list_pitchmen_with_open_handoffs",
        lambda **kwargs: [],
    )
    upcoming_handoff = _make_fake_handoff(
        handoff_id=110,
        need_back="Upcoming item",
        next_check=date(2099, 4, 1),
    )
    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now.get_now_snapshot",
        lambda **kwargs: _make_fake_snapshot(upcoming=[upcoming_handoff]),
    )

    render_now_page()

    assert st_mock.segmented_control.called
    seg_calls = [c for c in st_mock.segmented_control.call_args_list if c[0]]
    action_seg = next(
        (c for c in seg_calls if list(c.kwargs.get("options", [])) == ["edit", "delete"]),
        None,
    )
    assert action_seg is not None


def test_render_check_in_flow_save_clears_mode_and_shows_success(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Saving check-in clears the mode state and shows success message."""
    st_mock = _build_streamlit_mock()
    st_mock.button.return_value = False
    st_mock.form_submit_button.side_effect = _simulate_widget_submit("Save check-in")
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_forms.st", st_mock)
    monkeypatch.setattr("handoff.interfaces.streamlit.pages.now_helpers.st", st_mock)

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

    monkeypatch.setattr(
        "handoff.interfaces.streamlit.pages.now_forms.add_check_in", _fake_add_check_in
    )
    handoff = _make_fake_handoff(handoff_id=111, next_check=date(2026, 3, 12))
    st_mock.session_state["now_action_check_in_mode_111"] = "on_track"
    st_mock.session_state["now_action_check_in_form_111_on_track_note"] = "done"
    st_mock.session_state["now_action_check_in_form_111_on_track_next_check"] = date(2026, 3, 13)

    _render_check_in_flow(handoff, key_prefix="now_action")

    assert len(calls) == 1
    assert calls[0]["handoff_id"] == 111
    assert calls[0]["check_in_type"] == CheckInType.ON_TRACK
    assert calls[0]["note"] == "done"
    assert calls[0]["next_check_date"] == date(2026, 3, 13)
    # Check that mode key was cleared after save
    assert "now_action_check_in_mode_111" not in st_mock.session_state
    # Check that success message was set
    assert "now_flash_success" in st_mock.session_state
    assert "Checked in today" in str(st_mock.session_state.get("now_flash_success", ""))
