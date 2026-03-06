import pandas as pd
import pytest

from handoff.models import Project
from handoff.pages.projects import (
    _execute_changes,
    _get_pending_changes,
    _get_projects_to_delete,
)


@pytest.fixture
def mock_projects():
    return [
        Project(id=1, name="Work", is_archived=False),
        Project(id=2, name="Home", is_archived=False),
        Project(id=3, name="Old Project", is_archived=True),
    ]


def test_get_projects_to_delete(mock_projects):
    df = pd.DataFrame(
        [
            {"__project_id": 1, "confirm_delete": True},
            {"__project_id": 2, "confirm_delete": False},
            {"__project_id": 99, "confirm_delete": True},  # Non-existent
        ]
    )
    to_delete = _get_projects_to_delete(df, mock_projects)

    assert len(to_delete) == 1
    assert to_delete[0] == (1, "Work")


def test_get_pending_changes_rename_and_archive(mock_projects):
    df = pd.DataFrame(
        [
            {
                "__project_id": 1,
                "name": "Work Updated",
                "is_archived": False,
                "confirm_delete": False,
            },
            {"__project_id": 2, "name": "Home", "is_archived": True, "confirm_delete": False},
        ]
    )
    valid, errors, changes = _get_pending_changes(df, mock_projects)

    assert valid is True
    assert len(errors) == 0
    assert len(changes) == 2
    assert changes[0] == {"type": "rename", "id": 1, "new_name": "Work Updated"}
    assert changes[1] == {"type": "archive", "id": 2, "archive": True}


def test_get_pending_changes_validation_error(mock_projects):
    df = pd.DataFrame(
        [
            {"__project_id": 1, "name": "  ", "is_archived": False, "confirm_delete": False},
        ]
    )
    valid, errors, changes = _get_pending_changes(df, mock_projects)

    assert valid is False
    assert "Project name cannot be empty" in errors[0]
    assert len(changes) == 0


def test_get_pending_changes_delete_priority(mock_projects):
    # If confirm_delete is True, other changes (like rename) should be ignored for that row
    df = pd.DataFrame(
        [
            {"__project_id": 1, "name": "New Name", "confirm_delete": True},
        ]
    )
    valid, errors, changes = _get_pending_changes(df, mock_projects)

    assert len(changes) == 1
    assert changes[0]["type"] == "delete"
    assert changes[0]["id"] == 1


def test_execute_changes_calls_data_functions(monkeypatch):
    calls = []

    def mock_rename(pid, name):
        calls.append(("rename", pid, name))

    def mock_archive(pid):
        calls.append(("archive", pid))

    def mock_delete(pid):
        calls.append(("delete", pid))
        return True

    monkeypatch.setattr("handoff.pages.projects.rename_project", mock_rename)
    monkeypatch.setattr("handoff.pages.projects.archive_project", mock_archive)
    monkeypatch.setattr("handoff.pages.projects.delete_project", mock_delete)

    changes = [
        {"type": "rename", "id": 10, "new_name": "Renamed"},
        {"type": "archive", "id": 11, "archive": True},
        {"type": "delete", "id": 12, "name": "To Die"},
    ]

    deleted, updated, errors = _execute_changes(changes)

    assert deleted == 1
    assert updated == 2
    assert len(errors) == 0
    assert ("rename", 10, "Renamed") in calls
    assert ("archive", 11) in calls
    assert ("delete", 12) in calls


def test_execute_changes_handles_exceptions(monkeypatch):
    def mock_rename(pid, name):
        raise Exception("DB Error")

    monkeypatch.setattr("handoff.pages.projects.rename_project", mock_rename)

    changes = [{"type": "rename", "id": 1, "new_name": "Fail"}]
    deleted, updated, errors = _execute_changes(changes)

    assert updated == 0
    assert len(errors) == 1
    assert "Could not rename project 1: DB Error" in errors[0]
