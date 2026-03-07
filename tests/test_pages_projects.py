import pandas as pd
import pytest

from handoff.models import Project
from handoff.pages.projects import (
    _apply_project_changes,
    _build_projects_display_rows,
    _execute_changes,
    _get_pending_changes,
    _get_projects_to_delete,
    _reset_projects_table_state,
    render_projects_page,
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


def test_get_pending_changes_unarchive(mock_projects):
    """Verify that changing is_archived from True to False is detected."""
    # Project 3 in mock_projects starts as is_archived=True
    df = pd.DataFrame(
        [
            {
                "__project_id": 3,
                "name": "Old Project",
                "is_archived": False,
                "confirm_delete": False,
            },
        ]
    )
    valid, errors, changes = _get_pending_changes(df, mock_projects)

    assert valid is True
    assert len(changes) == 1
    assert changes[0] == {"type": "archive", "id": 3, "archive": False}


def test_execute_changes_unarchive(monkeypatch):
    """Verify that archive=False calls unarchive_project."""
    calls = []

    def mock_unarchive(pid):
        calls.append(pid)

    monkeypatch.setattr("handoff.pages.projects.unarchive_project", mock_unarchive)

    changes = [{"type": "archive", "id": 3, "archive": False}]
    deleted, updated, errors = _execute_changes(changes)

    assert updated == 1
    assert 3 in calls


def test_apply_project_changes_orchestration(mock_projects, monkeypatch):
    """Verify the full flow from DataFrame to success result."""
    monkeypatch.setattr("handoff.pages.projects.rename_project", lambda pid, name: None)

    df = pd.DataFrame(
        [
            {"__project_id": 1, "name": "Renamed", "is_archived": False, "confirm_delete": False},
        ]
    )
    success, errors, deleted, updated = _apply_project_changes(df, mock_projects)

    assert success is True
    assert updated == 1
    assert len(errors) == 0


def test_apply_project_changes_validation_failure(mock_projects):
    """Verify that validation errors prevent execution."""
    df = pd.DataFrame(
        [
            {"__project_id": 1, "name": "", "is_archived": False, "confirm_delete": False},
        ]
    )
    success, errors, deleted, updated = _apply_project_changes(df, mock_projects)

    assert success is False
    assert "Project name cannot be empty" in errors[0]
    assert updated == 0


def test_build_projects_display_rows(mock_projects):
    """_build_projects_display_rows returns one row per summary item with expected keys."""
    summary_list = [
        {"project": mock_projects[0], "handoff": 2, "done": 1, "canceled": 0},
        {"project": mock_projects[1], "handoff": 0, "done": 0, "canceled": 1},
    ]
    rows = _build_projects_display_rows(summary_list)
    assert len(rows) == 2
    assert rows[0]["__project_id"] == 1
    assert rows[0]["name"] == "Work"
    assert rows[0]["is_archived"] is False
    assert rows[0]["handoff"] == 2
    assert rows[0]["done"] == 1
    assert rows[0]["canceled"] == 0
    assert rows[0]["confirm_delete"] is False
    assert rows[1]["__project_id"] == 2
    assert rows[1]["name"] == "Home"
    assert rows[1]["is_archived"] is False


def test_get_pending_changes_skips_row_with_missing_project_id(mock_projects):
    """Rows with __project_id missing or NaN produce no change for that row."""
    df = pd.DataFrame(
        [
            {"__project_id": None, "name": "X", "is_archived": False, "confirm_delete": False},
            {"name": "Y", "is_archived": False, "confirm_delete": False},
        ]
    )
    valid, errors, changes = _get_pending_changes(df, mock_projects)
    assert valid is True
    assert len(changes) == 0


def test_get_pending_changes_skips_unknown_project_id(mock_projects):
    """Rows with __project_id not in projects are skipped."""
    df = pd.DataFrame(
        [
            {"__project_id": 999, "name": "Unknown", "is_archived": False, "confirm_delete": False},
        ]
    )
    valid, errors, changes = _get_pending_changes(df, mock_projects)
    assert valid is True
    assert len(changes) == 0


def test_render_projects_page_can_include_archived(monkeypatch):
    """The archived-project toggle passes include_archived=True to the data layer."""
    seen = {}
    info_messages = []

    monkeypatch.setattr("handoff.pages.projects._render_create_project_form", lambda: None)
    monkeypatch.setattr("handoff.pages.projects.st.subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr("handoff.pages.projects.st.checkbox", lambda *args, **kwargs: True)

    def fake_get_projects_with_todo_summary(*, include_archived):
        seen["include_archived"] = include_archived
        return []

    monkeypatch.setattr(
        "handoff.pages.projects.get_projects_with_todo_summary",
        fake_get_projects_with_todo_summary,
    )
    monkeypatch.setattr("handoff.pages.projects.st.info", info_messages.append)

    render_projects_page()

    assert seen["include_archived"] is True
    assert info_messages == ["No projects yet. Use the form above to create the first project."]


def test_render_projects_page_empty_state_mentions_archived_toggle(monkeypatch):
    """The empty state hints at archived projects when only active projects are shown."""
    info_messages = []

    monkeypatch.setattr("handoff.pages.projects._render_create_project_form", lambda: None)
    monkeypatch.setattr("handoff.pages.projects.st.subheader", lambda *args, **kwargs: None)
    monkeypatch.setattr("handoff.pages.projects.st.checkbox", lambda *args, **kwargs: False)
    monkeypatch.setattr(
        "handoff.pages.projects.get_projects_with_todo_summary",
        lambda *, include_archived: [],
    )
    monkeypatch.setattr("handoff.pages.projects.st.info", info_messages.append)

    render_projects_page()

    assert info_messages == [
        'No active projects yet. Create one above or enable "Show archived projects" to '
        "manage archived ones."
    ]


def test_reset_projects_table_state_clears_editor_and_pending_delete(monkeypatch):
    session_state = {
        "projects_table_active": {"edited_rows": {"0": {"name": "Renamed"}}},
        "projects_table_all": {"edited_rows": {"1": {"confirm_delete": True}}},
        "projects_pending_deletion": {"names": ["Work"]},
        "projects_show_archived": True,
    }
    monkeypatch.setattr("streamlit.session_state", session_state)

    _reset_projects_table_state()

    assert "projects_table_active" not in session_state
    assert "projects_table_all" not in session_state
    assert "projects_pending_deletion" not in session_state
    assert session_state["projects_show_archived"] is True


@pytest.mark.parametrize(
    ("show_archived", "expected_key", "expected_caption"),
    [
        (
            False,
            "projects_table_active",
            "Edit names and archive state below. Show archived projects to review or "
            'unarchive hidden items. Check "Confirm delete" for projects to remove, then '
            "click Save changes.",
        ),
        (
            True,
            "projects_table_all",
            "Edit names and archive state below. Archived projects are visible here and can "
            'be unarchived. Check "Confirm delete" for projects to remove, then click Save '
            "changes.",
        ),
    ],
)
def test_render_projects_page_uses_toggle_specific_editor_state(
    monkeypatch, show_archived, expected_key, expected_caption
):
    captured = {}
    project = Project(id=1, name="Work", is_archived=False)

    monkeypatch.setattr("handoff.pages.projects._render_create_project_form", lambda: None)
    monkeypatch.setattr("handoff.pages.projects.st.subheader", lambda *args, **kwargs: None)

    def fake_checkbox(*args, **kwargs):
        captured["checkbox_on_change"] = kwargs.get("on_change")
        return show_archived

    monkeypatch.setattr("handoff.pages.projects.st.checkbox", fake_checkbox)
    monkeypatch.setattr(
        "handoff.pages.projects.get_projects_with_todo_summary",
        lambda *, include_archived: [
            {"project": project, "handoff": 0, "done": 0, "canceled": 0},
        ],
    )

    def fake_caption(message):
        captured["caption"] = message

    monkeypatch.setattr("handoff.pages.projects.st.caption", fake_caption)

    def fake_data_editor(df, **kwargs):
        captured["editor_key"] = kwargs["key"]
        return df

    monkeypatch.setattr("handoff.pages.projects.st.data_editor", fake_data_editor)
    monkeypatch.setattr("handoff.pages.projects.st.button", lambda *args, **kwargs: False)
    monkeypatch.setattr("streamlit.session_state", {})

    render_projects_page()

    assert captured["editor_key"] == expected_key
    assert captured["caption"] == expected_caption
    assert captured["checkbox_on_change"] is _reset_projects_table_state
