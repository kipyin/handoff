"""Unit/integration tests for internal todos helpers not covered by existing tests.

This file adds tests for:
- _apply_native_filters: unit-style test by stubbing out Streamlit widgets.
- _render_editable_table: integration-style test by stubbing out dependencies and simulating a
persisted edit.
"""

import pandas as pd

from handoff.models import TodoStatus
from handoff.page_models import TodoQuery
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


def test_render_editable_table_uses_autosave_editor(monkeypatch):
    monkeypatch.setattr(
        "handoff.pages.todos._apply_native_filters",
        lambda key_prefix, project_by_name, helper_options: (
            TodoQuery(),
            {"project_filters": ["Work"], "status_filters": ["handoff"], "helper_filters": []},
        ),
    )
    monkeypatch.setattr(
        "handoff.pages.todos.query_todos",
        lambda query=None, **kwargs: [],
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

    class FakeCol:
        def __enter__(self):
            return self

        def __exit__(self, exc_type, exc, tb):
            return False

    monkeypatch.setattr(
        "handoff.pages.todos.st.columns", lambda widths: [FakeCol() for _ in range(5)]
    )
    monkeypatch.setattr("handoff.pages.todos.st.caption", lambda *args, **kwargs: None)
    monkeypatch.setattr("streamlit.session_state", {})

    captured: dict = {}

    def fake_autosave_editor(display_df, *, key, persist_fn, **kwargs):
        captured["key"] = key
        captured["persist_fn"] = persist_fn
        captured["display_df"] = display_df

    monkeypatch.setattr("handoff.pages.todos.autosave_editor", fake_autosave_editor)

    p1 = type("P", (), {"id": 1, "name": "Work"})()

    _render_editable_table(
        projects=[p1],
        helper_options=[],
        key_prefix="test",
        context_label="view=todos_page",
    )

    assert "persist_fn" in captured
    assert captured["key"] == "test_table_editor"
    assert callable(captured["persist_fn"])


def test_render_editable_table_shows_counts_and_no_results(monkeypatch):
    source_df = pd.DataFrame(
        [
            {
                "id": 1,
                "name": "Task",
                "project": "Work",
                "status": "handoff",
                "helper": "",
                "deadline": None,
                "notes": "",
                "created_at": None,
            }
        ]
    )
    empty_filtered_df = source_df.iloc[0:0].copy()
    filtered_query = TodoQuery(search_text="zzz-no-match")

    monkeypatch.setattr(
        "handoff.pages.todos._apply_native_filters",
        lambda key_prefix, project_by_name, helper_options: (
            filtered_query,
            {"project_filters": [], "status_filters": ["handoff"], "helper_filters": []},
        ),
    )
    monkeypatch.setattr(
        "handoff.pages.todos.query_todos",
        lambda query=None, **kwargs: [] if query == filtered_query else [object()],
    )
    monkeypatch.setattr(
        "handoff.pages.todos._build_todo_dataframe",
        lambda rows: empty_filtered_df if not rows else source_df,
    )
    monkeypatch.setattr(
        "handoff.pages.todos._sort_and_build_display_df",
        lambda df: (df, df.copy()),
    )

    captions: list[str] = []
    info_messages: list[str] = []
    monkeypatch.setattr("handoff.pages.todos.st.caption", captions.append)
    monkeypatch.setattr("handoff.pages.todos.st.info", info_messages.append)
    monkeypatch.setattr("handoff.pages.todos.autosave_editor", lambda *args, **kwargs: None)
    monkeypatch.setattr("streamlit.session_state", {})

    p1 = type("P", (), {"id": 1, "name": "Work"})()

    _render_editable_table(
        projects=[p1],
        helper_options=[],
        key_prefix="test",
        context_label="view=todos_page",
    )

    assert captions == ["Showing 0 of 1 todo. Changes are saved automatically as you edit."]
    assert info_messages == [
        "No todos match the current filters. Clear or adjust them to see results."
    ]
