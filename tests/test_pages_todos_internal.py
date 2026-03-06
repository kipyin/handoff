"""Unit/integration tests for internal todos helpers not covered by existing tests.

This file adds tests for:
- _apply_native_filters: unit-style test by stubbing out Streamlit widgets.
- _render_editable_table: integration-style test by stubbing out dependencies and simulating a persisted edit.
"""
import pandas as pd
from handoff.pages.todos import _apply_native_filters, _render_editable_table, DEADLINE_ANY


def test_apply_native_filters_unit(monkeypatch):
    df = pd.DataFrame(
        [
            {
                "name": "Milk Task",
                "project": "P1",
                "status": "done",
                "helper": "Alice",
                "deadline": None,
                "notes": "",
                "id": 1,
            },
            {
                "name": "Other Task",
                "project": "P1",
                "status": "handoff",
                "helper": "",
                "deadline": None,
                "notes": "",
                "id": 2,
            },
        ]
    )

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

    monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda label, options=None, key=None: DEADLINE_ANY)
    monkeypatch.setattr("handoff.pages.todos.st.date_input", lambda *args, **kwargs: None)

    filtered_df, filter_state = _apply_native_filters(
        df, key_prefix="test", project_names=["P1"], helper_options=["Alice"]
    )

    assert len(filtered_df) == 1
    assert filtered_df.iloc[0]["name"] == "Milk Task"
    assert filter_state["project_filters"] == ["P1"]
    assert filter_state["status_filters"] == ["done"]
    assert filter_state["helper_filters"] == ["Alice"]


def test_render_editable_table_calls_persist_and_rerun(monkeypatch):
    # Prepare a tiny filtered dataframe and mock the downstream helpers
    df_filtered = pd.DataFrame(
        [
            {"__todo_id": 0, "id": 1, "name": "N", "project": "Work", "status": "handoff", "deadline": None, "notes": ""},
        ]
    )

    monkeypatch.setattr(
        "handoff.pages.todos._apply_native_filters",
        lambda source_df, key_prefix, project_names, helper_options: (df_filtered, {"project_filters": ["Work"], "status_filters": ["handoff"], "helper_filters": []}),
    )
    monkeypatch.setattr("handoff.pages.todos._sort_and_build_display_df", lambda df: (df, df.copy()))
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
    monkeypatch.setattr("streamlit.session_state", {"test_table_editor": {"edited_rows": {"0": {"name": "New Name"}}}})

    persisted = {}

    def fake_persist_changes(state, display_df=None, projects=None, default_project_id=None, key_prefix=None):
        persisted["state"] = state
        persisted["display_df"] = display_df
        persisted["projects"] = projects
        persisted["default_project_id"] = default_project_id
        persisted["key_prefix"] = key_prefix

    monkeypatch.setattr("handoff.pages.todos._persist_changes", fake_persist_changes)

    ran = {"rerun": False}
    monkeypatch.setattr("streamlit.rerun", lambda: ran.__setitem__("rerun", True))

    # Minimal project to satisfy _render_editable_table
    p1 = type("P", (), {"id": 1, "name": "Work"})()

    _source_df = pd.DataFrame([{"__todo_id": 0, "id": 1, "name": "N", "project": "Work", "status": "handoff", "deadline": None, "notes": ""}])

    _render_editable_table(
        source_df=_source_df,
        projects=[p1],
        helper_options=[],
        key_prefix="test",
        context_label="view=todos_page",
    )

    assert "state" in persisted
    assert persisted["state"] == {"edited_rows": {"0": {"name": "New Name"}}}
    assert ran["rerun"] is True
