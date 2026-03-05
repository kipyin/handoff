import pandas as pd
from datetime import date, datetime, UTC
from handoff.models import TodoStatus, Project, Todo
from handoff.pages.todos import (
    _build_todo_dataframe,
    _apply_dataframe_filters,
    _compute_defaults_from_filters,
    _deadline_preset_bounds,
    _sort_and_build_display_df,
    _persist_changes,
)

def test_compute_defaults_from_filters():
    from handoff.pages.todos import _compute_defaults_from_filters

    p1 = Project(id=1, name="Work")
    p2 = Project(id=2, name="Home")
    project_by_name = {"Work": p1, "Home": p2}
    projects = [p1, p2]

    # Case 1: Single project filter should set default project
    filter_state = {"project_filters": ["Home"], "status_filters": ["done"]}
    pid, pname, status, helper = _compute_defaults_from_filters(filter_state, project_by_name, projects)
    assert pid == 2
    assert pname == "Home"
    assert status == "done"

    # Case 2: Multiple filters or no filters should fallback to first project and DELEGATED
    filter_state = {"project_filters": ["Work", "Home"], "status_filters": []}
    pid, pname, status, helper = _compute_defaults_from_filters(filter_state, project_by_name, projects)
    assert pid == 1
    assert status == TodoStatus.DELEGATED.value


def test_apply_dataframe_filters_multi_select():
    df = pd.DataFrame([
        {"name": "T1", "status": "handoff", "project": "P1", "helper": "Alice", "notes": ""},
        {"name": "T2", "status": "done", "project": "P2", "helper": "Bob", "notes": ""},
        {"name": "T3", "status": "handoff", "project": "P2", "helper": " ", "notes": ""},
    ])

    # Filter by multiple statuses
    filtered = _apply_dataframe_filters(df, "", ["done"], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "T2"

    # Filter by project
    filtered = _apply_dataframe_filters(df, "", [], ["P1"], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "T1"

    # Filter by helper (should handle empty/whitespace)
    filtered = _apply_dataframe_filters(df, "", [], [], ["Alice"], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["helper"] == "Alice"


def test_persist_changes_updates(monkeypatch):
    updated_calls = []

    def mock_update(tid, **kwargs):
        updated_calls.append((tid, kwargs))
        return None

    monkeypatch.setattr("handoff.pages.todos.update_todo", mock_update)

    # Setup a display DF with internal IDs
    display_df = pd.DataFrame([
        {
            "__todo_id": 100,
            "name": "Old Name",
            "status": "handoff",
            "project": "Work",
            "deadline": None,
            "helper": "Alice",
            "notes": ""
        },
    ])

    p1 = Project(id=1, name="Work")
    p2 = Project(id=2, name="Personal")

    # Simulate changing name and project in row 0
    state = {
        "edited_rows": {
            "0": {"name": "New Name", "project": "Personal"}
        }
    }

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
    assert kwargs["project_id"] == 2  # Resolved from name "Personal"
    assert kwargs["status"] == TodoStatus.DELEGATED  # Preserved from current_row


def test_build_todo_dataframe_populated():
    proj = Project(name="Project A")
    todo = Todo(
        id=5,
        name="Task",
        status=TodoStatus.DONE,
        project=proj,
        deadline=date(2024, 1, 1),
        created_at=datetime(2024, 1, 1, tzinfo=UTC)
    )

    df = _build_todo_dataframe([todo])
    assert len(df) == 1
    assert df.iloc[0]["id"] == 5
    assert df.iloc[0]["project"] == "Project A"
    assert df.iloc[0]["status"] == "done"
    assert df.iloc[0]["deadline"] == date(2024, 1, 1)
