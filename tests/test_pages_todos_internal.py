"""Unit/integration tests for internal todos helpers not covered by existing tests.

This file adds tests for:
- _apply_native_filters: unit-style test by stubbing out Streamlit widgets.
- _render_editable_table: integration-style test by stubbing out dependencies and simulating a
persisted edit.
"""

import pandas as pd

from handoff.models import TodoStatus
from handoff.pages.todos import DEADLINE_ANY, _apply_native_filters, _render_editable_table


def test_apply_native_filters_unit(monkeypatch):
    class FakeCol:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    # Patch columns to return five fake columns
    monkeypatch.setattr(
        "handoff.pages.todos.st.columns", lambda widths: [FakeCol() for _ in range(5)]
    )

    # Patch inputs to simulate user selections
    monkeypatch.setattr(
        "handoff.pages.todos.st.text_input",
        lambda label, placeholder=None, key=None: "milk",
    )

    def fake_multiselect(label, options=None, default=None, key=None):
        if "Statuses" in label:
            return ["done"]
        if "Projects" in label:
            return ["P1"]
        if "Helper" in label:
            return ["Alice"]
        return []

    monkeypatch.setattr("handoff.pages.todos.st.multiselect", fake_multiselect)

    monkeypatch.setattr(
        "handoff.pages.todos.st.selectbox", lambda label, options=None, key=None: DEADLINE_ANY
    )
    monkeypatch.setattr("handoff.pages.todos.st.date_input", lambda *args, **kwargs: None)

    p1 = type("P", (), {"id": 1, "name": "P1"})()
    todo_query, filter_state = _apply_native_filters(
        key_prefix="test",
        project_by_name={"P1": p1},
        helper_options=["Alice"],
    )

    assert todo_query.search_text == "milk"
    assert todo_query.project_ids == (1,)
    assert todo_query.helper_names == ("Alice",)
    assert todo_query.statuses == (TodoStatus.DONE,)
    assert filter_state["project_filters"] == ["P1"]
    assert filter_state["status_filters"] == ["done"]
    assert filter_state["helper_filters"] == ["Alice"]


def test_render_editable_table_calls_persist_and_rerun(monkeypatch):
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
            {"project_filters": ["Work"], "status_filters": ["handoff"], "helper_filters": []},
        ),
    )
    monkeypatch.setattr(
        "handoff.pages.todos.query_todos",
        lambda query: [],
    )
    monkeypatch.setattr(
        "handoff.pages.todos._build_todo_dataframe",
        lambda rows: pd.DataFrame(
            [
                {
                    "__todo_id": 0,
                    "id": 1,
                    "name": "N",
                    "project": "Work",
                    "status": "handoff",
                    "deadline": None,
                    "notes": "",
                },
            ]
        ),
    )
    monkeypatch.setattr(
        "handoff.pages.todos._sort_and_build_display_df", lambda df: (df, df.copy())
    )

    # Patch UI rendering and persistence hooks
    class FakeCol:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "handoff.pages.todos.st.columns", lambda widths: [FakeCol() for _ in range(5)]
    )
    monkeypatch.setattr("handoff.pages.todos.st.caption", lambda *args, **kwargs: None)
    monkeypatch.setattr("handoff.pages.todos.st.data_editor", lambda *args, **kwargs: None)

    # Simulate an edit in the editor state
    monkeypatch.setattr(
        "streamlit.session_state",
        {"test_table_editor": {"edited_rows": {"0": {"name": "New Name"}}}},
    )

    persisted = {}

    def fake_persist_changes(state, display_df=None, projects=None, defaults=None, key_prefix=None):
        persisted["state"] = state
        persisted["display_df"] = display_df
        persisted["projects"] = projects
        persisted["defaults"] = defaults
        persisted["key_prefix"] = key_prefix

    monkeypatch.setattr("handoff.pages.todos._persist_changes", fake_persist_changes)

    ran = {"rerun": False}
    monkeypatch.setattr("streamlit.rerun", lambda: ran.__setitem__("rerun", True))

    # Minimal project to satisfy _render_editable_table
    p1 = type("P", (), {"id": 1, "name": "Work"})()

    _render_editable_table(
        projects=[p1],
        helper_options=[],
        key_prefix="test",
        context_label="view=todos_page",
    )

    assert "state" in persisted
    assert persisted["state"] == {"edited_rows": {"0": {"name": "New Name"}}}
    assert ran["rerun"] is True
