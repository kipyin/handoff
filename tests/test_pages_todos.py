import pandas as pd
import pytest
from datetime import date, timedelta
from types import SimpleNamespace

from handoff.pages.todos import (
    _build_todo_dataframe,
    _apply_dataframe_filters,
    _sort_and_build_display_df,
    _persist_changes,
    _deadline_preset_bounds,
    DEADLINE_TODAY,
)


def test_build_todo_dataframe_empty():
    df = _build_todo_dataframe([])
    assert list(df.columns) == [
        "id",
        "project",
        "name",
        "status",
        "helper",
        "deadline",
        "notes",
        "created_at",
    ]
    assert len(df) == 0


def test_deadline_preset_bounds_today():
    start, end = _deadline_preset_bounds(DEADLINE_TODAY)
    assert start == end == date.today()


def test_apply_dataframe_filters_search():
    df = pd.DataFrame(
        [
            {
                "name": "Buy milk",
                "notes": "Low fat",
                "helper": "Alice",
                "project": "Home",
                "status": "Delegated",
                "deadline": None,
            },
            {
                "name": "Fix sink",
                "notes": "",
                "helper": "Bob",
                "project": "Home",
                "status": "Delegated",
                "deadline": None,
            },
        ]
    )
    # Search by name
    filtered = _apply_dataframe_filters(df, "milk", [], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Buy milk"

    # Search by helper
    filtered = _apply_dataframe_filters(df, "Bob", [], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Fix sink"

    # Date range filtering (include today)
    df_with_dates = pd.DataFrame(
        [
            {
                "name": "Task A",
                "deadline": date.today(),
                "project": "P",
                "notes": "",
                "helper": "",
                "status": "Delegated",
            },
            {
                "name": "Task B",
                "deadline": date.today() + timedelta(days=1),
                "project": "P",
                "notes": "",
                "helper": "",
                "status": "Delegated",
            },
        ]
    )
    filtered = _apply_dataframe_filters(
        df_with_dates,
        "",
        [],
        [],
        [],
        date.today(),
        date.today(),
    )
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Task A"


def test_sort_and_build_display_df():
    df = pd.DataFrame(
        [
            {"id": 1, "name": "B", "created_at": date(2023, 1, 2)},
            {"id": 2, "name": "A", "created_at": date(2023, 1, 1)},
        ]
    )
    working, display = _sort_and_build_display_df(df)
    # Should be sorted by created_at
    assert working.iloc[0]["id"] == 2
    assert "__todo_id" in working.columns
    assert "id" not in display.columns
    assert "created_at" not in display.columns


def test_persist_changes_deletions(monkeypatch):
    deleted_ids = []

    def mock_delete(tid):
        deleted_ids.append(tid)

    monkeypatch.setattr("handoff.pages.todos.delete_todo", mock_delete)

    display_df = pd.DataFrame(
        [
            {"__todo_id": 10, "name": "Task 1"},
            {"__todo_id": 20, "name": "Task 2"},
        ]
    )
    state = {"deleted_rows": [0]}  # Delete Task 1

    _persist_changes(
        state=state,
        display_df=display_df,
        projects=[],
        default_project_id=None,
        key_prefix="test",
    )
    assert deleted_ids == [10]


def test_persist_changes_additions(monkeypatch):
    created_rows = []

    def mock_create(**kwargs):
        created_rows.append(kwargs)
        # Return an object with an id to simulate created todo
        from types import SimpleNamespace

        return SimpleNamespace(id=999, **kwargs)

    monkeypatch.setattr("handoff.pages.todos.create_todo", mock_create)

    # Mock session_state to avoid NoSessionContext errors
    monkeypatch.setattr("streamlit.session_state", {})

    p1 = SimpleNamespace(id=1, name="Work")
    display_df = pd.DataFrame(columns=["__todo_id"])

    state = {
        "added_rows": [
            {
                "name": "New Task",
                "project": "Work",
                "deadline": "2025-01-01",
                "notes": "note",
                "helper": None,
                "status": None,
            }
        ]
    }

    _persist_changes(
        state=state,
        display_df=display_df,
        projects=[p1],
        default_project_id=1,
        key_prefix="test",
    )

    assert len(created_rows) == 1
    kwargs = created_rows[0]
    assert kwargs["name"] == "New Task"
    assert kwargs["deadline"] == date(2025, 1, 1)
    assert kwargs["project_id"] == 1
