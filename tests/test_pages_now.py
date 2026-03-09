"""Tests for the Now page."""

from __future__ import annotations

from datetime import date
from types import SimpleNamespace
from unittest.mock import MagicMock

import pytest

from handoff.pages.now import render_now_page


def _make_fake_todo(
    todo_id: int = 1,
    project_name: str = "Work",
    helper: str | None = "Alice",
    name: str = "Need back",
    next_check: date | None = None,
    deadline: date | None = None,
    notes: str = "",
) -> SimpleNamespace:
    """Build a minimal todo-like object for Now page render tests."""
    proj = SimpleNamespace(id=1, name=project_name)
    return SimpleNamespace(
        id=todo_id,
        project=proj,
        helper=helper,
        name=name,
        next_check=next_check or date(2026, 1, 15),
        deadline=deadline,
        notes=notes,
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
    monkeypatch.setattr("handoff.pages.now.list_helpers_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    query_calls: list[dict] = []

    def capture_query(**kwargs):
        query_calls.append(kwargs)
        return []

    monkeypatch.setattr("handoff.pages.now.query_now_items", capture_query)
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kwargs: [])
    monkeypatch.setattr("handoff.pages.now.query_todos", lambda **kwargs: [])
    render_now_page()
    assert len(query_calls) == 1
    assert "project_ids" in query_calls[0]
    assert "helper_names" in query_calls[0]


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
    monkeypatch.setattr("handoff.pages.now.list_helpers_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    todo_action = _make_fake_todo(todo_id=1, name="Action item")
    todo_upcoming = _make_fake_todo(todo_id=2, name="Upcoming item")
    monkeypatch.setattr(
        "handoff.pages.now.query_now_items",
        lambda **kw: [(todo_action, False)],
    )
    monkeypatch.setattr(
        "handoff.pages.now.query_upcoming_handoffs",
        lambda **kw: [todo_upcoming],
    )
    monkeypatch.setattr("handoff.pages.now.query_todos", lambda **kw: [])
    render_now_page()
    assert st_mock.expander.call_count >= 2
    button_labels = [c[0][0] for c in st_mock.button.call_args_list if c[0]]
    assert any(label == "Snooze" for label in button_labels)
    assert any(label == "Edit" for label in button_labels)
    assert any(label == "✓ Close" for label in button_labels)


def test_render_now_page_closed_expander_queries_todos(monkeypatch: pytest.MonkeyPatch) -> None:
    """When the page renders, the Closed expander queries closed handoffs (done/canceled)."""
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
    st_mock.dataframe.return_value = {"selection": {"rows": []}}

    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_helpers_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    monkeypatch.setattr("handoff.pages.now.query_now_items", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])

    query_todos_calls: list[dict] = []

    def capture_query_todos(**kwargs):
        query_todos_calls.append(kwargs)
        return []

    monkeypatch.setattr("handoff.pages.now.query_todos", capture_query_todos)
    render_now_page()

    assert len(query_todos_calls) == 1
    assert query_todos_calls[0]["statuses"] == ["done", "canceled"]
    st_mock.expander.assert_called()
    closed_call = [c for c in st_mock.expander.call_args_list if c[0][0] == "Closed >"]
    assert len(closed_call) == 1


def test_render_now_page_reopen_calls_update_todo(monkeypatch: pytest.MonkeyPatch) -> None:
    """When Reopen selected is clicked with rows selected, update_todo is called."""
    st_mock = MagicMock()
    st_mock.session_state = {}
    st_mock.multiselect.return_value = []
    st_mock.text_input.return_value = ""
    st_mock.text_area.return_value = ""
    st_mock.button.side_effect = lambda *a, **kw: kw.get("key") == "now_reopen_btn"
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

    closed_todo = _make_fake_todo(todo_id=42, name="Closed item")
    closed_todo.status = "done"
    closed_todo.completed_at = None
    closed_todo.created_at = MagicMock()

    event_mock = {"selection": {"rows": [0]}}

    st_mock.dataframe.return_value = event_mock

    monkeypatch.setattr("handoff.pages.now.st", st_mock)
    mock_project = SimpleNamespace(id=1, name="Work")
    monkeypatch.setattr("handoff.pages.now.list_projects", lambda: [mock_project])
    monkeypatch.setattr("handoff.pages.now.list_helpers_with_open_handoffs", lambda: ["Alice"])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    monkeypatch.setattr("handoff.pages.now.query_now_items", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])

    update_calls: list[tuple] = []

    def capture_update(todo_id: int, **kwargs):
        update_calls.append((todo_id, kwargs))

    monkeypatch.setattr(
        "handoff.pages.now.query_todos",
        lambda **kw: [closed_todo],
    )
    monkeypatch.setattr("handoff.pages.now.update_todo", capture_update)
    monkeypatch.setattr("handoff.pages.now.st.rerun", lambda: None)

    render_now_page()

    assert len(update_calls) == 1
    assert update_calls[0][0] == 42
    assert update_calls[0][1]["status"] == "handoff"


def test_render_now_page_with_editing_shows_form(monkeypatch: pytest.MonkeyPatch) -> None:
    """When session_state now_editing_todo_id is set, edit form is rendered."""
    st_mock = MagicMock()
    st_mock.session_state = {"now_editing_todo_id": 1}
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
    monkeypatch.setattr("handoff.pages.now.list_helpers_with_open_handoffs", lambda: [])
    monkeypatch.setattr("handoff.pages.now.get_deadline_near_days", lambda: 1)
    todo_action = _make_fake_todo(todo_id=1, name="Edit me")
    monkeypatch.setattr(
        "handoff.pages.now.query_now_items",
        lambda **kw: [(todo_action, False)],
    )
    monkeypatch.setattr("handoff.pages.now.query_upcoming_handoffs", lambda **kw: [])
    monkeypatch.setattr("handoff.pages.now.query_todos", lambda **kw: [])
    render_now_page()
    st_mock.form.assert_called()
    assert any("edit" in str(c).lower() for c in st_mock.form.call_args_list)
