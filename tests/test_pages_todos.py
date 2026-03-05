from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace

import pandas as pd

from handoff.models import TodoStatus
from handoff.pages.todos import (
    DEADLINE_TODAY,
    _apply_dataframe_filters,
    _build_todo_dataframe,
    _compute_defaults_from_filters,
    _deadline_preset_bounds,
    _persist_changes,
    _sort_and_build_display_df,
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


def test_compute_defaults_from_filters():
    p1 = SimpleNamespace(id=1, name="Work")
    p2 = SimpleNamespace(id=2, name="Home")
    project_by_name = {"Work": p1, "Home": p2}
    projects = [p1, p2]

    # Case 1: Single project filter should set default project
    filter_state = {"project_filters": ["Home"], "status_filters": ["done"]}
    pid, pname, status, helper = _compute_defaults_from_filters(
        filter_state, project_by_name, projects
    )
    assert pid == 2
    assert pname == "Home"
    assert status == "done"

    # Case 2: Multiple filters or no filters should fallback to first project and DELEGATED
    filter_state = {"project_filters": ["Work", "Home"], "status_filters": []}
    pid, pname, status, helper = _compute_defaults_from_filters(
        filter_state, project_by_name, projects
    )
    assert pid == 1
    assert status == TodoStatus.DELEGATED.value


def test_apply_dataframe_filters_multi_select():
    df = pd.DataFrame(
        [
            {"name": "T1", "status": "handoff", "project": "P1", "helper": "Alice", "notes": ""},
            {"name": "T2", "status": "done", "project": "P2", "helper": "Bob", "notes": ""},
            {"name": "T3", "status": "handoff", "project": "P2", "helper": " ", "notes": ""},
        ]
    )

    # Filter by multiple statuses
    filtered = _apply_dataframe_filters(df, "", ["done"], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "T2"

    # Filter by project
    filtered = _apply_dataframe_filters(df, "", [], ["P1"], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "T1"

    # Filter by helper
    filtered = _apply_dataframe_filters(df, "", [], [], ["Alice"], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["helper"] == "Alice"


def test_persist_changes_updates(monkeypatch):
    updated_calls = []

    def mock_update(tid, **kwargs):
        updated_calls.append((tid, kwargs))
        return None

    monkeypatch.setattr("handoff.pages.todos.update_todo", mock_update)

    display_df = pd.DataFrame(
        [
            {
                "__todo_id": 100,
                "name": "Old Name",
                "status": "handoff",
                "project": "Work",
                "deadline": None,
                "helper": "Alice",
                "notes": "",
            },
        ]
    )

    p1 = SimpleNamespace(id=1, name="Work")
    p2 = SimpleNamespace(id=2, name="Personal")

    # Simulate changing name and project in row 0
    state = {"edited_rows": {"0": {"name": "New Name", "project": "Personal"}}}

    _persist_changes(
        state=state,
        display_df=display_df,
        projects=[p1, p2],
        default_project_id=1,
        key_prefix="test",
    )

    assert len(updated_calls) == 1
    tid, kwargs = updated_calls[0]
    assert tid == 100
    assert kwargs["name"] == "New Name"
    assert kwargs["project_id"] == 2
    assert kwargs["status"] == TodoStatus.DELEGATED


def test_build_todo_dataframe_populated():
    proj = SimpleNamespace(name="Project A")
    todo = SimpleNamespace(
        id=5,
        name="Task",
        status=TodoStatus.DONE,
        project=proj,
        helper="Alice",
        deadline=date(2024, 1, 1),
        notes="Some notes",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )

    df = _build_todo_dataframe([todo])
    assert len(df) == 1
    assert df.iloc[0]["id"] == 5
    assert df.iloc[0]["project"] == "Project A"
    assert df.iloc[0]["status"] == "done"
    assert df.iloc[0]["deadline"] == date(2024, 1, 1)
