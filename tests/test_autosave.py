"""Tests for the shared autosave_editor helper and page-level persist callbacks."""

from __future__ import annotations

from types import SimpleNamespace

import pandas as pd
import pytest

from handoff.models import TodoStatus
from handoff.page_models import TodoMutationDefaults
from handoff.pages.projects import _persist_project_edits
from handoff.pages.todos import _make_todos_persist_fn

# ---------------------------------------------------------------------------
# _make_todos_persist_fn
# ---------------------------------------------------------------------------


class TestMakeTodosPersistFn:
    """Test the closure returned by _make_todos_persist_fn."""

    @pytest.fixture
    def projects(self):
        return [SimpleNamespace(id=1, name="Work"), SimpleNamespace(id=2, name="Home")]

    @pytest.fixture
    def defaults(self):
        return TodoMutationDefaults(
            project_id=1,
            project_name="Work",
            status=TodoStatus.HANDOFF,
            helper="",
        )

    def test_edit_returns_false(self, projects, defaults, monkeypatch):
        """Simple edits should NOT trigger a rerun."""
        monkeypatch.setattr("handoff.pages.todos.update_todo", lambda tid, **kw: None)
        persist_fn = _make_todos_persist_fn(projects, defaults, "test")

        display_df = pd.DataFrame(
            [
                {
                    "__todo_id": 10,
                    "name": "Old",
                    "status": "handoff",
                    "project": "Work",
                    "deadline": None,
                    "helper": "",
                    "notes": "",
                }
            ]
        )
        state = {"edited_rows": {"0": {"name": "New Name"}}, "added_rows": [], "deleted_rows": []}
        needs_rerun = persist_fn(state, display_df)
        assert needs_rerun is False

    def test_addition_returns_true(self, projects, defaults, monkeypatch):
        """Row additions should trigger a rerun."""
        monkeypatch.setattr(
            "handoff.pages.todos.create_todo",
            lambda **kw: SimpleNamespace(id=99, **kw),
        )
        monkeypatch.setattr("streamlit.session_state", {})
        persist_fn = _make_todos_persist_fn(projects, defaults, "test")

        display_df = pd.DataFrame(columns=["__todo_id"])
        state = {
            "edited_rows": {},
            "added_rows": [{"name": "New", "project": "Work"}],
            "deleted_rows": [],
        }
        needs_rerun = persist_fn(state, display_df)
        assert needs_rerun is True

    def test_deletion_returns_true(self, projects, defaults, monkeypatch):
        """Row deletions should trigger a rerun."""
        deleted_ids: list[int] = []
        monkeypatch.setattr("handoff.pages.todos.delete_todo", deleted_ids.append)
        persist_fn = _make_todos_persist_fn(projects, defaults, "test")

        display_df = pd.DataFrame([{"__todo_id": 5, "name": "Bye"}])
        state = {"edited_rows": {}, "added_rows": [], "deleted_rows": [0]}
        needs_rerun = persist_fn(state, display_df)
        assert needs_rerun is True
        assert deleted_ids == [5]

    def test_empty_state_returns_false(self, projects, defaults):
        """No changes → no persist, no rerun."""
        persist_fn = _make_todos_persist_fn(projects, defaults, "test")
        display_df = pd.DataFrame(columns=["__todo_id"])
        state = {"edited_rows": {}, "added_rows": [], "deleted_rows": []}
        needs_rerun = persist_fn(state, display_df)
        assert needs_rerun is False


# ---------------------------------------------------------------------------
# _persist_project_edits
# ---------------------------------------------------------------------------


class TestPersistProjectEdits:
    """Test the autosave callback for the projects page."""

    def _make_display_df(self, rows: list[dict]) -> pd.DataFrame:
        return pd.DataFrame(rows)

    def test_rename_is_saved(self, monkeypatch):
        calls: list[tuple[int, str]] = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": 1, "name": "Old"}])
        state = {"edited_rows": {"0": {"name": "New Name"}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert calls == [(1, "New Name")]

    def test_archive_toggle_is_saved(self, monkeypatch):
        archived_ids: list[int] = []
        monkeypatch.setattr(
            "handoff.pages.projects.archive_project",
            archived_ids.append,
        )
        display_df = self._make_display_df(
            [{"__project_id": 2, "name": "Home", "is_archived": False}]
        )
        state = {"edited_rows": {"0": {"is_archived": True}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert archived_ids == [2]

    def test_unarchive_toggle_is_saved(self, monkeypatch):
        unarchived_ids: list[int] = []
        monkeypatch.setattr(
            "handoff.pages.projects.unarchive_project",
            unarchived_ids.append,
        )
        display_df = self._make_display_df(
            [{"__project_id": 3, "name": "Old", "is_archived": True}]
        )
        state = {"edited_rows": {"0": {"is_archived": False}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert unarchived_ids == [3]

    def test_confirm_delete_is_ignored(self, monkeypatch):
        """confirm_delete changes must NOT trigger data mutations."""
        rename_calls: list = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": 1, "name": "Work"}])
        state = {"edited_rows": {"0": {"confirm_delete": True}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == []

    def test_empty_name_is_skipped(self, monkeypatch):
        """Blank names should not be persisted."""
        rename_calls: list = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": 1, "name": "Work"}])
        state = {"edited_rows": {"0": {"name": "   "}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == []

    def test_empty_edited_rows_is_noop(self):
        """No edited rows → early return False."""
        display_df = self._make_display_df([{"__project_id": 1}])
        result = _persist_project_edits({"edited_rows": {}}, display_df)
        assert result is False

    def test_out_of_bounds_row_is_skipped(self, monkeypatch):
        """Row index beyond display_df length should be skipped safely."""
        rename_calls: list = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": 1, "name": "Work"}])
        state = {"edited_rows": {"5": {"name": "Ghost"}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == []

    def test_negative_row_index_is_skipped(self, monkeypatch):
        """Negative row indices must not index from the end."""
        rename_calls: list = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": 1, "name": "Work"}])
        state = {"edited_rows": {"-1": {"name": "Sneaky"}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == []

    def test_non_numeric_row_index_is_skipped(self, monkeypatch):
        """Non-numeric row index keys are skipped without crashing."""
        rename_calls: list = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": 1, "name": "Work"}])
        state = {"edited_rows": {"abc": {"name": "Bad"}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == []

    def test_missing_project_id_is_skipped(self, monkeypatch):
        """Rows with NaN __project_id are silently skipped."""
        rename_calls: list = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        display_df = self._make_display_df([{"__project_id": None, "name": "Ghost"}])
        state = {"edited_rows": {"0": {"name": "New"}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == []

    def test_rename_exception_surfaces_error(self, monkeypatch):
        """DB errors during rename are collected in session state for display."""
        session: dict = {}
        monkeypatch.setattr("streamlit.session_state", session)

        def bad_rename(pid, name):
            raise RuntimeError("DB locked")

        monkeypatch.setattr("handoff.pages.projects.rename_project", bad_rename)
        display_df = self._make_display_df([{"__project_id": 1, "name": "Work"}])
        state = {"edited_rows": {"0": {"name": "Kaboom"}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        errors = session.get("__projects_autosave_errors", [])
        assert len(errors) == 1
        assert "rename" in errors[0].lower() or "project 1" in errors[0]

    def test_archive_exception_surfaces_error(self, monkeypatch):
        """DB errors during archive toggle are collected in session state."""
        session: dict = {}
        monkeypatch.setattr("streamlit.session_state", session)

        def bad_archive(pid):
            raise RuntimeError("DB locked")

        monkeypatch.setattr("handoff.pages.projects.archive_project", bad_archive)
        display_df = self._make_display_df(
            [{"__project_id": 2, "name": "Home", "is_archived": False}]
        )
        state = {"edited_rows": {"0": {"is_archived": True}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        errors = session.get("__projects_autosave_errors", [])
        assert len(errors) == 1
        assert "archive" in errors[0].lower() or "project 2" in errors[0]

    def test_mixed_rename_and_archive(self, monkeypatch):
        """A single row edit with both rename and archive should apply both."""
        rename_calls: list[tuple[int, str]] = []
        archive_calls: list[int] = []
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        monkeypatch.setattr(
            "handoff.pages.projects.archive_project",
            archive_calls.append,
        )
        display_df = self._make_display_df(
            [{"__project_id": 1, "name": "Work", "is_archived": False}]
        )
        state = {"edited_rows": {"0": {"name": "Office", "is_archived": True}}}
        result = _persist_project_edits(state, display_df)
        assert result is False
        assert rename_calls == [(1, "Office")]
        assert archive_calls == [1]
