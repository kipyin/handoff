"""Tests for pages/projects.py Streamlit render functions via mocking."""

from __future__ import annotations

from unittest.mock import MagicMock

import pandas as pd

from handoff.models import Project
from handoff.pages.projects import _render_create_project_form, render_projects_page


class FakeForm:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


class FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


def _make_st_mock(monkeypatch, *, session_state=None):
    st_mock = MagicMock()
    st_mock.form.return_value = FakeForm()
    st_mock.text_input.return_value = ""
    st_mock.form_submit_button.return_value = False
    st_mock.button.return_value = False
    st_mock.session_state = session_state if session_state is not None else {}
    st_mock.columns.return_value = [FakeCol(), FakeCol(), FakeCol()]
    monkeypatch.setattr("handoff.pages.projects.st", st_mock)
    return st_mock


def _mock_summary(monkeypatch, projects):
    """Set up get_projects_with_todo_summary to return given projects."""
    summary = [{"project": p, "handoff": 1, "done": 0, "canceled": 0} for p in projects]
    monkeypatch.setattr(
        "handoff.pages.projects.get_projects_with_todo_summary",
        lambda include_archived: summary,
    )
    return summary


class TestRenderCreateProjectForm:
    def _patch(self, monkeypatch, *, text_value="", submitted=False):
        st_mock = MagicMock()
        st_mock.text_input.return_value = text_value
        st_mock.form_submit_button.return_value = submitted
        st_mock.form.return_value = FakeForm()
        monkeypatch.setattr("handoff.pages.projects.st", st_mock)
        return st_mock

    def test_empty_name_shows_error(self, monkeypatch) -> None:
        st_mock = self._patch(monkeypatch, text_value="  ", submitted=True)
        _render_create_project_form()
        st_mock.error.assert_called_once_with("Project name cannot be empty.")

    def test_valid_name_creates_project(self, monkeypatch) -> None:
        st_mock = self._patch(monkeypatch, text_value="New Project", submitted=True)
        created = {"name": None}
        monkeypatch.setattr(
            "handoff.pages.projects.create_project",
            lambda n: created.__setitem__("name", n),
        )
        monkeypatch.setattr("handoff.pages.projects.st.rerun", lambda: None)
        _render_create_project_form()
        assert created["name"] == "New Project"
        st_mock.success.assert_called_once_with("Project created.")

    def test_not_submitted_does_nothing(self, monkeypatch) -> None:
        st_mock = self._patch(monkeypatch, text_value="Anything", submitted=False)
        _render_create_project_form()
        st_mock.error.assert_not_called()
        st_mock.success.assert_not_called()


class TestRenderProjectsPage:
    def test_no_projects_shows_info(self, monkeypatch) -> None:
        st_mock = _make_st_mock(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.projects.get_projects_with_todo_summary",
            lambda include_archived: [],
        )
        render_projects_page()
        st_mock.info.assert_called_once()
        assert "No projects" in st_mock.info.call_args[0][0]

    def test_save_no_changes(self, monkeypatch) -> None:
        """Save button clicked with no changes shows 'No changes' info."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        st_mock = _make_st_mock(monkeypatch)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": False,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_save_button"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr(
            "handoff.pages.projects._get_projects_to_delete",
            lambda df, p: [],
        )
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (True, [], 0, 0),
        )

        render_projects_page()
        st_mock.info.assert_any_call("No changes to save.")

    def test_save_with_updates(self, monkeypatch) -> None:
        """Save button with rename shows success and triggers rerun."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        st_mock = _make_st_mock(monkeypatch)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Renamed",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": False,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_save_button"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr("handoff.pages.projects._get_projects_to_delete", lambda df, p: [])
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (True, [], 0, 1),
        )

        render_projects_page()
        st_mock.success.assert_called()
        st_mock.rerun.assert_called()

    def test_save_with_errors(self, monkeypatch) -> None:
        """Save button with errors shows error messages."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        st_mock = _make_st_mock(monkeypatch)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": False,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_save_button"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr("handoff.pages.projects._get_projects_to_delete", lambda df, p: [])
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (False, ["Name empty"], 0, 0),
        )

        render_projects_page()
        st_mock.error.assert_called_with("Name empty")

    def test_save_with_deletions_triggers_pending(self, monkeypatch) -> None:
        """Save with deletions sets session state and reruns for confirmation."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        session_state = {}
        st_mock = _make_st_mock(monkeypatch, session_state=session_state)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": True,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_save_button"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr(
            "handoff.pages.projects._get_projects_to_delete",
            lambda df, p: [(1, "Work")],
        )

        render_projects_page()
        assert "projects_pending_deletion" in session_state
        st_mock.rerun.assert_called()

    def test_pending_deletion_confirm(self, monkeypatch) -> None:
        """Confirm delete in pending state triggers apply and rerun."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        session_state = {"projects_pending_deletion": {"names": ["Work"]}}
        st_mock = _make_st_mock(monkeypatch, session_state=session_state)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": True,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_confirm_delete_btn"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr(
            "handoff.pages.projects._get_projects_to_delete",
            lambda df, p: [(1, "Work")],
        )
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (True, [], 1, 0),
        )

        render_projects_page()
        st_mock.success.assert_called()
        st_mock.rerun.assert_called()
        assert "projects_pending_deletion" not in session_state

    def test_pending_deletion_cancel(self, monkeypatch) -> None:
        """Cancel in pending state removes pending state and reruns."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        session_state = {"projects_pending_deletion": {"names": ["Work"]}}
        st_mock = _make_st_mock(monkeypatch, session_state=session_state)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": True,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_cancel_delete_btn"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr(
            "handoff.pages.projects._get_projects_to_delete",
            lambda df, p: [],
        )

        render_projects_page()
        assert "projects_pending_deletion" not in session_state
        st_mock.rerun.assert_called()

    def test_pending_deletion_with_errors(self, monkeypatch) -> None:
        """Confirm delete with errors shows error messages."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        session_state = {"projects_pending_deletion": {"names": ["Work"]}}
        st_mock = _make_st_mock(monkeypatch, session_state=session_state)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": True,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_confirm_delete_btn"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr(
            "handoff.pages.projects._get_projects_to_delete",
            lambda df, p: [(1, "Work")],
        )
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (False, ["Could not delete"], 0, 0),
        )

        render_projects_page()
        st_mock.error.assert_called_with("Could not delete")

    def test_save_with_deleted_and_updated(self, monkeypatch) -> None:
        """Save with both deletes and updates shows combined message."""
        projects = [
            Project(id=1, name="Work", is_archived=False),
            Project(id=2, name="Home", is_archived=False),
        ]
        st_mock = _make_st_mock(monkeypatch)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": False,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_save_button"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr("handoff.pages.projects._get_projects_to_delete", lambda df, p: [])
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (True, [], 1, 2),
        )

        render_projects_page()
        success_msg = st_mock.success.call_args[0][0]
        assert "Deleted" in success_msg
        assert "other changes" in success_msg

    def test_confirm_deleted_and_updated_message(self, monkeypatch) -> None:
        """Confirm delete with both deletes and updates shows combined message."""
        projects = [Project(id=1, name="Work", is_archived=False)]
        session_state = {"projects_pending_deletion": {"names": ["Work"]}}
        st_mock = _make_st_mock(monkeypatch, session_state=session_state)
        _mock_summary(monkeypatch, projects)

        edited_df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "handoff": 1,
                    "done": 0,
                    "canceled": 0,
                    "confirm_delete": True,
                },
            ]
        )
        st_mock.data_editor.return_value = edited_df

        def button_side_effect(*args, **kwargs):
            return kwargs.get("key") == "projects_confirm_delete_btn"

        st_mock.button.side_effect = button_side_effect
        monkeypatch.setattr(
            "handoff.pages.projects._get_projects_to_delete",
            lambda df, p: [(1, "Work")],
        )
        monkeypatch.setattr(
            "handoff.pages.projects._apply_project_changes",
            lambda df, p: (True, [], 1, 1),
        )

        render_projects_page()
        success_msg = st_mock.success.call_args[0][0]
        assert "Deleted" in success_msg
        assert "other changes" in success_msg
