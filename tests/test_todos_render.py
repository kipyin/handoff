"""Tests for pages/todos.py render-level and custom deadline code paths."""

from __future__ import annotations

from datetime import date, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd

from handoff.models import TodoStatus
from handoff.page_models import TodoMutationDefaults
from handoff.pages.todos import (
    DEADLINE_CUSTOM,
    _apply_native_filters,
    _persist_changes,
    _render_editable_table,
    render_todos_page,
)


class FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class TestCustomDeadlineRange:
    """Test the DEADLINE_CUSTOM branch in _apply_native_filters."""

    def test_valid_custom_range(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)]
        )
        monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "")

        def fake_multiselect(label, options=None, default=None, key=None):
            if "Statuses" in label:
                return ["handoff"]
            return []

        monkeypatch.setattr("handoff.pages.todos.st.multiselect", fake_multiselect)
        monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_CUSTOM)

        today = date.today()
        next_week = today + timedelta(days=7)
        monkeypatch.setattr(
            "handoff.pages.todos.st.date_input", lambda *a, **kw: (today, next_week)
        )
        monkeypatch.setattr("handoff.pages.todos.st.error", lambda msg: None)

        query, state = _apply_native_filters(
            key_prefix="test", project_by_name={}, helper_options=[]
        )
        assert state["start_date"] == today
        assert state["end_date"] == next_week

    def test_inverted_custom_range_shows_error(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)]
        )
        monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "")

        def fake_multiselect(label, options=None, default=None, key=None):
            return []

        monkeypatch.setattr("handoff.pages.todos.st.multiselect", fake_multiselect)
        monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_CUSTOM)

        today = date.today()
        monkeypatch.setattr(
            "handoff.pages.todos.st.date_input",
            lambda *a, **kw: (today + timedelta(days=7), today),
        )
        error_calls = []
        monkeypatch.setattr("handoff.pages.todos.st.error", lambda msg: error_calls.append(msg))

        query, state = _apply_native_filters(
            key_prefix="test", project_by_name={}, helper_options=[]
        )
        assert state["start_date"] is None
        assert state["end_date"] is None
        assert any("before" in msg.lower() for msg in error_calls)

    def test_incomplete_custom_range(self, monkeypatch) -> None:
        """Single-value date_input result sets dates to None."""
        monkeypatch.setattr(
            "handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)]
        )
        monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "")

        def fake_multiselect(label, options=None, default=None, key=None):
            return []

        monkeypatch.setattr("handoff.pages.todos.st.multiselect", fake_multiselect)
        monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_CUSTOM)
        monkeypatch.setattr(
            "handoff.pages.todos.st.date_input",
            lambda *a, **kw: (date.today(),),
        )

        query, state = _apply_native_filters(
            key_prefix="test", project_by_name={}, helper_options=[]
        )
        assert state["start_date"] is None
        assert state["end_date"] is None


class TestRenderTodosPageNoProjects:
    def test_no_projects_shows_info(self, monkeypatch) -> None:
        st_mock = MagicMock()
        monkeypatch.setattr("handoff.pages.todos.st", st_mock)
        monkeypatch.setattr("handoff.pages.todos.list_projects", lambda: [])

        render_todos_page()

        st_mock.info.assert_called_once()
        assert "No projects" in st_mock.info.call_args[0][0]


class TestRememberedDefaults:
    """Test that remembered project_id and helper from session_state are applied."""

    def test_remembered_project_and_helper(self, monkeypatch) -> None:
        p1 = type("P", (), {"id": 1, "name": "Work"})()

        monkeypatch.setattr(
            "handoff.pages.todos._apply_native_filters",
            lambda key_prefix, project_by_name, helper_options: (
                type(
                    "Q",
                    (),
                    {
                        "search_text": "",
                        "statuses": (),
                        "project_ids": (),
                        "helper_names": (),
                        "deadline_start": None,
                        "deadline_end": None,
                        "include_archived": False,
                    },
                )(),
                {"project_filters": [], "status_filters": ["handoff"], "helper_filters": []},
            ),
        )
        monkeypatch.setattr("handoff.pages.todos.query_todos", lambda query: [])
        monkeypatch.setattr(
            "handoff.pages.todos._build_todo_dataframe",
            lambda rows: pd.DataFrame(
                columns=[
                    "id",
                    "name",
                    "project",
                    "status",
                    "deadline",
                    "notes",
                    "created_at",
                    "helper",
                ]
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.todos._sort_and_build_display_df",
            lambda df: (df.copy(), df.copy()),
        )
        monkeypatch.setattr("handoff.pages.todos.st.caption", lambda *a, **kw: None)

        editor_calls = []

        def capture_data_editor(*args, **kwargs):
            editor_calls.append(kwargs)

        monkeypatch.setattr("handoff.pages.todos.st.data_editor", capture_data_editor)

        monkeypatch.setattr(
            "streamlit.session_state",
            {
                "test_last_new_project_id": 1,
                "test_last_new_helper": "Bob",
            },
        )

        _render_editable_table(
            projects=[p1], helper_options=[], key_prefix="test", context_label="test"
        )

        assert len(editor_calls) == 1
        column_config = editor_calls[0]["column_config"]
        project_col = column_config["project"]
        helper_col = column_config["helper"]
        assert project_col["default"] == "Work"
        assert helper_col["default"] == "Bob"


class TestPersistChangesAddition:
    """Test the addition code path in _persist_changes (line 409+)."""

    def test_addition_skipped_when_no_name(self, monkeypatch) -> None:
        """Added row with empty name is skipped."""
        created = []
        monkeypatch.setattr(
            "handoff.pages.todos.create_todo",
            lambda **kw: created.append(kw),
        )
        monkeypatch.setattr("streamlit.session_state", {})

        p1 = SimpleNamespace(id=1, name="Work")
        display_df = pd.DataFrame(columns=["__todo_id"])
        state = {"added_rows": [{"name": "", "project": "Work"}]}

        _persist_changes(
            state=state,
            display_df=display_df,
            projects=[p1],
            defaults=TodoMutationDefaults(
                project_id=1, project_name="Work", status=TodoStatus.HANDOFF, helper=""
            ),
            key_prefix="test",
        )
        assert created == []
