"""Tests for the shared autosave_editor helper and page-level persist callbacks."""

from __future__ import annotations

import pandas as pd

from handoff.interfaces.streamlit.autosave import autosave_editor
from handoff.interfaces.streamlit.pages.projects import _persist_project_edits

# ---------------------------------------------------------------------------
# autosave_editor
# ---------------------------------------------------------------------------


class TestAutosaveEditor:
    """Test the shared autosave data_editor wrapper."""

    def test_registers_callback_and_stores_context_copy(self, monkeypatch):
        session: dict = {}
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        captured: dict = {}
        returned_df = pd.DataFrame([{"name": "edited"}])

        def fake_data_editor(df, *, key, on_change, **kwargs):
            captured["df"] = df
            captured["key"] = key
            captured["on_change"] = on_change
            captured["kwargs"] = kwargs
            return returned_df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor", fake_data_editor
        )
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.rerun", lambda: None)

        display_df = pd.DataFrame([{"name": "original"}])
        result = autosave_editor(
            display_df,
            key="todos_table",
            persist_fn=lambda state, prev_df: False,
            num_rows="dynamic",
        )

        assert result is returned_df
        assert captured["key"] == "todos_table"
        assert captured["kwargs"]["num_rows"] == "dynamic"
        assert callable(captured["on_change"])

        ctx_df = session["__todos_table_autosave_ctx"]["display_df"]
        assert ctx_df.equals(display_df)
        assert ctx_df is not display_df

    def test_on_change_persists_edit_state_with_snapshot(self, monkeypatch):
        session = {
            "todos_table": {
                "edited_rows": {"0": {"name": "new"}},
                "added_rows": [],
                "deleted_rows": [],
            }
        }
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        captured: dict = {}

        def fake_data_editor(df, *, key, on_change, **kwargs):
            captured["on_change"] = on_change
            return df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor", fake_data_editor
        )
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.rerun", lambda: None)

        calls: list[pd.DataFrame] = []

        def persist_fn(state, prev_df):
            calls.append(prev_df.copy())
            return False

        display_df = pd.DataFrame([{"name": "original"}])
        autosave_editor(display_df, key="todos_table", persist_fn=persist_fn)
        display_df.loc[0, "name"] = "mutated-after-render"

        captured["on_change"]()

        assert len(calls) == 1
        assert calls[0].iloc[0]["name"] == "original"
        assert "__todos_table_needs_rerun" not in session

    def test_on_change_skips_empty_editor_state(self, monkeypatch):
        session = {
            "todos_table": {
                "edited_rows": {},
                "added_rows": [],
                "deleted_rows": [],
            }
        }
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        captured: dict = {}

        def fake_data_editor(df, *, key, on_change, **kwargs):
            captured["on_change"] = on_change
            return df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor",
            fake_data_editor,
        )
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.rerun", lambda: None)

        called = {"persist": 0}

        def persist_fn(state, prev_df):
            called["persist"] += 1
            return False

        autosave_editor(pd.DataFrame([{"name": "x"}]), key="todos_table", persist_fn=persist_fn)
        captured["on_change"]()

        assert called["persist"] == 0

    def test_on_change_skips_when_widget_state_is_missing(self, monkeypatch):
        session: dict = {}
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        captured: dict = {}

        def fake_data_editor(df, *, key, on_change, **kwargs):
            captured["on_change"] = on_change
            return df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor", fake_data_editor
        )
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.rerun", lambda: None)

        called = {"persist": 0}

        def persist_fn(state, prev_df):
            called["persist"] += 1
            return False

        autosave_editor(pd.DataFrame([{"name": "x"}]), key="todos_table", persist_fn=persist_fn)
        captured["on_change"]()

        assert called["persist"] == 0

    def test_on_change_sets_deferred_rerun_flag(self, monkeypatch):
        session = {"todos_table": {"edited_rows": {"0": {"name": "x"}}}}
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        captured: dict = {}

        def fake_data_editor(df, *, key, on_change, **kwargs):
            captured["on_change"] = on_change
            return df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor",
            fake_data_editor,
        )
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.rerun", lambda: None)

        autosave_editor(
            pd.DataFrame([{"name": "x"}]),
            key="todos_table",
            persist_fn=lambda state, prev_df: True,
        )
        captured["on_change"]()

        assert session["__todos_table_needs_rerun"] is True

    def test_next_render_consumes_rerun_flag(self, monkeypatch):
        session = {"__todos_table_needs_rerun": True}
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        def fake_data_editor(df, *, key, on_change, **kwargs):
            return df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor", fake_data_editor
        )
        rerun_calls: list[str] = []
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.rerun", lambda: rerun_calls.append("rerun")
        )

        autosave_editor(
            pd.DataFrame([{"name": "x"}]),
            key="todos_table",
            persist_fn=lambda state, prev_df: False,
        )

        assert rerun_calls == ["rerun"]
        assert "__todos_table_needs_rerun" not in session

    def test_on_change_with_missing_context_logs_warning(self, monkeypatch):
        session = {"todos_table": {"edited_rows": {"0": {"name": "x"}}}}
        monkeypatch.setattr("streamlit.session_state", session)
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.session_state", session)

        captured: dict = {}

        def fake_data_editor(df, *, key, on_change, **kwargs):
            captured["on_change"] = on_change
            return df

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.st.data_editor",
            fake_data_editor,
        )
        monkeypatch.setattr("handoff.interfaces.streamlit.autosave.st.rerun", lambda: None)

        warnings: list[tuple[str, str]] = []
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.autosave.logger.warning",
            lambda message, key: warnings.append((message, key)),
        )

        persist_calls = {"count": 0}

        def persist_fn(state, prev_df):
            persist_calls["count"] += 1
            return False

        autosave_editor(
            pd.DataFrame([{"name": "x"}]),
            key="todos_table",
            persist_fn=persist_fn,
        )
        session.pop("__todos_table_autosave_ctx", None)
        captured["on_change"]()

        assert persist_calls["count"] == 0
        assert warnings == [("autosave_editor: missing context for key={}", "todos_table")]


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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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
            "handoff.interfaces.streamlit.pages.projects.archive_project",
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
            "handoff.interfaces.streamlit.pages.projects.unarchive_project",
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
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

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.pages.projects.rename_project", bad_rename
        )
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

        monkeypatch.setattr(
            "handoff.interfaces.streamlit.pages.projects.archive_project", bad_archive
        )
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
            "handoff.interfaces.streamlit.pages.projects.rename_project",
            lambda pid, name: rename_calls.append((pid, name)),
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.pages.projects.archive_project",
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
