"""Consolidated tests for pages/todos.py."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import MagicMock

import pandas as pd
import pytest

from handoff.models import Project, TodoStatus
from handoff.page_models import TodoMutationDefaults, TodoQuery, TodoRow
from handoff.pages.todos import (
    DEADLINE_ANY,
    DEADLINE_CUSTOM,
    DEADLINE_OVERDUE,
    DEADLINE_THIS_WEEK,
    DEADLINE_TODAY,
    DEADLINE_TOMORROW,
    _apply_dataframe_filters,
    _apply_native_filters,
    _build_create_input,
    _build_todo_dataframe,
    _build_update_input,
    _compute_defaults_from_filters,
    _deadline_preset_bounds,
    _normalize_deadline,
    _persist_changes,
    _render_editable_table,
    _sort_and_build_display_df,
    render_todos_page,
)


class FakeCol:
    def __enter__(self):
        return self

    def __exit__(self, *a):
        return False


# --- _build_todo_dataframe ---


def test_build_todo_dataframe_empty() -> None:
    df = _build_todo_dataframe([])
    assert list(df.columns) == [
        "id",
        "project",
        "name",
        "status",
        "next_check",
        "helper",
        "deadline",
        "notes",
        "created_at",
    ]
    assert len(df) == 0


def test_build_todo_dataframe_populated() -> None:
    row = TodoRow(
        todo_id=5,
        project_id=1,
        project_name="Project A",
        name="Task",
        status=TodoStatus.DONE,
        next_check=None,
        helper="",
        deadline=date(2024, 1, 1),
        notes="",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    df = _build_todo_dataframe([row])
    assert len(df) == 1
    assert df.iloc[0]["id"] == 5
    assert df.iloc[0]["project"] == "Project A"
    assert df.iloc[0]["status"] == "done"
    assert df.iloc[0]["deadline"] == date(2024, 1, 1)


# --- _deadline_preset_bounds ---


def test_deadline_preset_bounds_today() -> None:
    start, end = _deadline_preset_bounds(DEADLINE_TODAY)
    assert start == end == date.today()


def test_deadline_preset_bounds_any() -> None:
    assert _deadline_preset_bounds(DEADLINE_ANY) == (None, None)


def test_deadline_preset_bounds_tomorrow() -> None:
    tomorrow = date.today() + timedelta(days=1)
    start, end = _deadline_preset_bounds(DEADLINE_TOMORROW)
    assert start == end == tomorrow


def test_deadline_preset_bounds_this_week() -> None:
    today = date.today()
    start, end = _deadline_preset_bounds(DEADLINE_THIS_WEEK)
    assert start is not None and end is not None
    assert start.weekday() == 0
    assert end.weekday() == 6
    assert start <= today <= end


def test_deadline_preset_bounds_custom_returns_none() -> None:
    assert _deadline_preset_bounds(DEADLINE_CUSTOM) == (None, None)


def test_deadline_preset_bounds_overdue() -> None:
    start, end = _deadline_preset_bounds(DEADLINE_OVERDUE)
    assert start == date.min
    assert end == date.today() - timedelta(days=1)


def test_deadline_preset_bounds_unknown_returns_none() -> None:
    assert _deadline_preset_bounds("nonexistent") == (None, None)


# --- _normalize_deadline ---


class TestNormalizeDeadline:
    def test_none_returns_none(self) -> None:
        assert _normalize_deadline(None) is None

    def test_empty_string_returns_none(self) -> None:
        assert _normalize_deadline("") is None

    def test_nat_returns_none(self) -> None:
        assert _normalize_deadline(pd.NaT) is None

    def test_date_returns_date(self) -> None:
        d = date(2026, 5, 1)
        assert _normalize_deadline(d) == d

    def test_datetime_returns_date(self) -> None:
        dt = datetime(2026, 5, 1, 14, 30)
        assert _normalize_deadline(dt) == date(2026, 5, 1)

    def test_iso_string_returns_date(self) -> None:
        assert _normalize_deadline("2026-05-01") == date(2026, 5, 1)

    def test_whitespace_string_returns_none(self) -> None:
        assert _normalize_deadline("   ") is None

    def test_non_convertible_returns_none(self) -> None:
        assert _normalize_deadline(12345) is None


# --- _apply_dataframe_filters ---


def test_apply_dataframe_filters_search() -> None:
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
    filtered = _apply_dataframe_filters(df, "milk", [], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Buy milk"
    filtered = _apply_dataframe_filters(df, "Bob", [], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Fix sink"


def test_apply_dataframe_filters_date_range() -> None:
    df = pd.DataFrame(
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
    filtered = _apply_dataframe_filters(df, "", [], [], [], date.today(), date.today())
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "Task A"


def test_apply_dataframe_filters_multi_select() -> None:
    df = pd.DataFrame(
        [
            {"name": "T1", "status": "handoff", "project": "P1", "helper": "Alice", "notes": ""},
            {"name": "T2", "status": "done", "project": "P2", "helper": "Bob", "notes": ""},
            {"name": "T3", "status": "handoff", "project": "P2", "helper": " ", "notes": ""},
        ]
    )
    filtered = _apply_dataframe_filters(df, "", ["done"], [], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "T2"
    filtered = _apply_dataframe_filters(df, "", [], ["P1"], [], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["name"] == "T1"
    filtered = _apply_dataframe_filters(df, "", [], [], ["Alice"], None, None)
    assert len(filtered) == 1
    assert filtered.iloc[0]["helper"] == "Alice"


# --- _sort_and_build_display_df ---


def test_sort_and_build_display_df() -> None:
    df = pd.DataFrame(
        [
            {"id": 1, "name": "B", "created_at": date(2023, 1, 2)},
            {"id": 2, "name": "A", "created_at": date(2023, 1, 1)},
        ]
    )
    working, display = _sort_and_build_display_df(df)
    assert working.iloc[0]["id"] == 2
    assert "__todo_id" in working.columns
    assert "id" not in display.columns
    assert "created_at" not in display.columns


# --- _compute_defaults_from_filters ---


def test_compute_defaults_from_filters() -> None:
    p1 = Project(id=1, name="Work")
    p2 = Project(id=2, name="Home")
    project_by_name = {"Work": p1, "Home": p2}
    projects = [p1, p2]
    filter_state = {"project_filters": ["Home"], "status_filters": ["done"]}
    defaults = _compute_defaults_from_filters(filter_state, project_by_name, projects)
    assert defaults.project_id == 2
    assert defaults.project_name == "Home"
    assert defaults.status == TodoStatus.DONE
    filter_state = {"project_filters": ["Work", "Home"], "status_filters": []}
    defaults = _compute_defaults_from_filters(filter_state, project_by_name, projects)
    assert defaults.project_id == 1
    assert defaults.status == TodoStatus.HANDOFF


# --- _build_update_input, _build_create_input ---


class TestBuildUpdateInput:
    def test_basic_update(self) -> None:
        result = _build_update_input(
            todo_id=42,
            row_changes={"name": "New Name", "status": "done"},
            current_row={
                "project": "Work",
                "name": "Old Name",
                "status": "handoff",
                "deadline": None,
                "helper": "Alice",
                "notes": "",
            },
            project_by_name={"Work": 1},
        )
        assert result.todo_id == 42
        assert result.name == "New Name"
        assert result.status == TodoStatus.DONE
        assert result.project_id == 1
        assert result.helper == "Alice"

    def test_update_with_deadline_string(self) -> None:
        result = _build_update_input(
            todo_id=10,
            row_changes={"deadline": "2026-06-15"},
            current_row={
                "project": "P",
                "name": "T",
                "status": "handoff",
                "helper": "",
                "notes": "",
            },
            project_by_name={"P": 1},
        )
        assert result.deadline == date(2026, 6, 15)


class TestBuildCreateInput:
    def test_basic_create(self) -> None:
        defaults = TodoMutationDefaults(
            project_id=1, project_name="Work", status=TodoStatus.HANDOFF, helper=""
        )
        result = _build_create_input(
            {"name": "New Task", "project": "Work", "status": "done"},
            project_by_name={"Work": 1},
            defaults=defaults,
        )
        assert result is not None
        assert result.name == "New Task"
        assert result.project_id == 1
        assert result.status == TodoStatus.DONE

    def test_empty_name_returns_none(self) -> None:
        defaults = TodoMutationDefaults(
            project_id=1, project_name="Work", status=TodoStatus.HANDOFF, helper=""
        )
        result = _build_create_input(
            {"name": "  ", "project": "Work"},
            project_by_name={"Work": 1},
            defaults=defaults,
        )
        assert result is None

    def test_no_project_returns_none(self) -> None:
        defaults = TodoMutationDefaults(
            project_id=None, project_name=None, status=TodoStatus.HANDOFF, helper=""
        )
        result = _build_create_input(
            {"name": "Task", "project": "Unknown"},
            project_by_name={"Work": 1},
            defaults=defaults,
        )
        assert result is None

    def test_uses_default_project_when_no_project_in_row(self) -> None:
        defaults = TodoMutationDefaults(
            project_id=5, project_name="Default", status=TodoStatus.HANDOFF, helper=""
        )
        result = _build_create_input(
            {"name": "Task"},
            project_by_name={"Default": 5},
            defaults=defaults,
        )
        assert result is not None
        assert result.project_id == 5

    def test_uses_default_status_when_no_status_in_row(self) -> None:
        defaults = TodoMutationDefaults(
            project_id=1, project_name="Work", status=TodoStatus.DONE, helper=""
        )
        result = _build_create_input(
            {"name": "Task", "project": "Work"},
            project_by_name={"Work": 1},
            defaults=defaults,
        )
        assert result is not None
        assert result.status == TodoStatus.DONE


# --- _persist_changes ---


def test_persist_changes_deletions(monkeypatch: pytest.MonkeyPatch) -> None:
    deleted_ids: list[int] = []
    monkeypatch.setattr("handoff.pages.todos.delete_todo", lambda tid: deleted_ids.append(tid))
    display_df = pd.DataFrame(
        [{"__todo_id": 10, "name": "Task 1"}, {"__todo_id": 20, "name": "Task 2"}]
    )
    state = {"deleted_rows": [0]}
    _persist_changes(
        state=state,
        display_df=display_df,
        projects=[],
        defaults=TodoMutationDefaults(
            project_id=None, project_name=None, status=TodoStatus.HANDOFF, helper=""
        ),
        key_prefix="test",
    )
    assert deleted_ids == [10]


def test_persist_changes_additions(monkeypatch: pytest.MonkeyPatch) -> None:
    created_rows: list[dict] = []

    def mock_create(**kwargs):
        created_rows.append(kwargs)
        return SimpleNamespace(id=999, **kwargs)

    monkeypatch.setattr("handoff.pages.todos.create_todo", mock_create)
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
        defaults=TodoMutationDefaults(
            project_id=1, project_name="Work", status=TodoStatus.HANDOFF, helper=""
        ),
        key_prefix="test",
    )
    assert len(created_rows) == 1
    assert created_rows[0]["name"] == "New Task"
    assert created_rows[0]["deadline"] == date(2025, 1, 1)
    assert created_rows[0]["project_id"] == 1


def test_persist_changes_updates(monkeypatch: pytest.MonkeyPatch) -> None:
    updated_calls: list[tuple[int, dict]] = []
    monkeypatch.setattr(
        "handoff.pages.todos.update_todo", lambda tid, **kwargs: updated_calls.append((tid, kwargs))
    )
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
            }
        ]
    )
    p1, p2 = Project(id=1, name="Work"), Project(id=2, name="Personal")
    state = {"edited_rows": {"0": {"name": "New Name", "project": "Personal"}}}
    _persist_changes(
        state=state,
        display_df=display_df,
        projects=[p1, p2],
        defaults=TodoMutationDefaults(
            project_id=1, project_name="Work", status=TodoStatus.HANDOFF, helper=""
        ),
        key_prefix="test",
    )
    assert len(updated_calls) == 1
    tid, kwargs = updated_calls[0]
    assert tid == 100
    assert kwargs["name"] == "New Name"
    assert kwargs["project_id"] == 2
    assert kwargs["status"] == TodoStatus.HANDOFF


def test_build_todo_dataframe_populated_with_next_check() -> None:
    """Dataframe includes next_check when provided."""
    row = TodoRow(
        todo_id=5,
        project_id=1,
        project_name="Project A",
        name="Task",
        status=TodoStatus.DONE,
        next_check=date(2024, 1, 2),
        helper="Alice",
        deadline=date(2024, 1, 1),
        notes="Some notes",
        created_at=datetime(2024, 1, 1, tzinfo=UTC),
    )
    df = _build_todo_dataframe([row])
    assert len(df) == 1
    assert df.iloc[0]["id"] == 5
    assert df.iloc[0]["project"] == "Project A"
    assert df.iloc[0]["status"] == "done"
    assert df.iloc[0]["next_check"] == date(2024, 1, 2)
    assert df.iloc[0]["deadline"] == date(2024, 1, 1)


class TestPersistChangesEdgeCases:
    def test_deletion_out_of_bounds_ignored(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr("handoff.pages.todos.delete_todo", lambda tid: None)
        display_df = pd.DataFrame([{"__todo_id": 10, "name": "Task 1"}])
        state = {"deleted_rows": [5]}
        _persist_changes(
            state=state,
            display_df=display_df,
            projects=[],
            defaults=TodoMutationDefaults(
                project_id=None, project_name=None, status=TodoStatus.HANDOFF, helper=""
            ),
            key_prefix="test",
        )

    def test_edit_with_nan_todo_id_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[int] = []
        monkeypatch.setattr("handoff.pages.todos.update_todo", lambda tid, **kw: calls.append(tid))
        display_df = pd.DataFrame(
            [
                {
                    "__todo_id": float("nan"),
                    "name": "N",
                    "project": "P",
                    "status": "handoff",
                    "deadline": None,
                    "helper": "",
                    "notes": "",
                }
            ]
        )
        state = {"edited_rows": {"0": {"name": "X"}}}
        _persist_changes(
            state=state,
            display_df=display_df,
            projects=[],
            defaults=TodoMutationDefaults(
                project_id=None, project_name=None, status=TodoStatus.HANDOFF, helper=""
            ),
            key_prefix="test",
        )
        assert calls == []

    def test_edit_out_of_bounds_skipped(self, monkeypatch: pytest.MonkeyPatch) -> None:
        calls: list[int] = []
        monkeypatch.setattr("handoff.pages.todos.update_todo", lambda tid, **kw: calls.append(tid))
        display_df = pd.DataFrame([{"__todo_id": 10, "name": "N"}])
        state = {"edited_rows": {"5": {"name": "X"}}}
        _persist_changes(
            state=state,
            display_df=display_df,
            projects=[],
            defaults=TodoMutationDefaults(
                project_id=None, project_name=None, status=TodoStatus.HANDOFF, helper=""
            ),
            key_prefix="test",
        )
        assert calls == []

    def test_addition_skipped_when_no_name(self, monkeypatch: pytest.MonkeyPatch) -> None:
        created: list[dict] = []
        monkeypatch.setattr("handoff.pages.todos.create_todo", lambda **kw: created.append(kw))
        monkeypatch.setattr("streamlit.session_state", {})
        p1 = SimpleNamespace(id=1, name="Work")
        display_df = pd.DataFrame(columns=["__todo_id"])
        state = {"added_rows": [{"name": "", "project": "Work"}]}
        _persist_changes(
            state=state,
            display_df=display_df,
            projects=[p1],
            defaults=TodoMutationDefaults(
                project_id=1, project_name="Work", status=TodoStatus.HANDOFF, helper=""
            ),
            key_prefix="test",
        )
        assert created == []


# --- _apply_native_filters ---


class TestCustomDeadlineRange:
    def test_valid_custom_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)]
        )
        monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "")

        def fake_multiselect(label, options=None, default=None, key=None):
            return ["handoff"] if "Statuses" in label else []

        monkeypatch.setattr("handoff.pages.todos.st.multiselect", fake_multiselect)
        monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_CUSTOM)
        today, next_week = date.today(), date.today() + timedelta(days=7)
        monkeypatch.setattr(
            "handoff.pages.todos.st.date_input", lambda *a, **kw: (today, next_week)
        )
        monkeypatch.setattr("handoff.pages.todos.st.error", lambda msg: None)
        query, state = _apply_native_filters(
            key_prefix="test", project_by_name={}, helper_options=[]
        )
        assert state["start_date"] == today
        assert state["end_date"] == next_week

    def test_inverted_custom_range_shows_error(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)]
        )
        monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "")
        monkeypatch.setattr("handoff.pages.todos.st.multiselect", lambda *a, **kw: [])
        monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_CUSTOM)
        today = date.today()
        monkeypatch.setattr(
            "handoff.pages.todos.st.date_input",
            lambda *a, **kw: (today + timedelta(days=7), today),
        )
        error_calls: list[str] = []
        monkeypatch.setattr("handoff.pages.todos.st.error", lambda msg: error_calls.append(msg))
        query, state = _apply_native_filters(
            key_prefix="test", project_by_name={}, helper_options=[]
        )
        assert state["start_date"] is None
        assert state["end_date"] is None
        assert any("before" in msg.lower() for msg in error_calls)

    def test_incomplete_custom_range(self, monkeypatch: pytest.MonkeyPatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)]
        )
        monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "")
        monkeypatch.setattr("handoff.pages.todos.st.multiselect", lambda *a, **kw: [])
        monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_CUSTOM)
        monkeypatch.setattr("handoff.pages.todos.st.date_input", lambda *a, **kw: (date.today(),))
        query, state = _apply_native_filters(
            key_prefix="test", project_by_name={}, helper_options=[]
        )
        assert state["start_date"] is None
        assert state["end_date"] is None


def test_apply_native_filters_unit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)])
    monkeypatch.setattr("handoff.pages.todos.st.text_input", lambda *a, **kw: "milk")

    def fake_multiselect(label, options=None, default=None, key=None):
        if "Statuses" in label:
            return ["done"]
        if "Projects" in label:
            return ["P1"]
        if "Helper" in label:
            return ["Alice"]
        return []

    monkeypatch.setattr("handoff.pages.todos.st.multiselect", fake_multiselect)
    monkeypatch.setattr("handoff.pages.todos.st.selectbox", lambda *a, **kw: DEADLINE_ANY)
    monkeypatch.setattr("handoff.pages.todos.st.date_input", lambda *a, **kw: None)
    p1 = type("P", (), {"id": 1, "name": "P1"})()
    todo_query, filter_state = _apply_native_filters(
        key_prefix="test", project_by_name={"P1": p1}, helper_options=["Alice"]
    )
    assert todo_query.search_text == "milk"
    assert todo_query.project_ids == (1,)
    assert todo_query.helper_names == ("Alice",)
    assert todo_query.statuses == (TodoStatus.DONE,)
    assert filter_state["project_filters"] == ["P1"]
    assert filter_state["status_filters"] == ["done"]
    assert filter_state["helper_filters"] == ["Alice"]


# --- _render_editable_table ---


def test_render_editable_table_uses_autosave_editor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "handoff.pages.todos._apply_native_filters",
        lambda *a, **kw: (
            TodoQuery(),
            {"project_filters": ["Work"], "status_filters": ["handoff"], "helper_filters": []},
        ),
    )
    monkeypatch.setattr("handoff.pages.todos.query_todos", lambda *a, **kw: [])
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
                }
            ]
        ),
    )
    monkeypatch.setattr(
        "handoff.pages.todos._sort_and_build_display_df", lambda df: (df, df.copy())
    )
    monkeypatch.setattr("handoff.pages.todos.st.columns", lambda w: [FakeCol() for _ in range(5)])
    monkeypatch.setattr("handoff.pages.todos.st.caption", lambda *a, **kw: None)
    monkeypatch.setattr("streamlit.session_state", {})
    captured: dict = {}

    def fake_autosave_editor(display_df, *, key, persist_fn, **kwargs):
        captured["key"] = key
        captured["persist_fn"] = persist_fn

    monkeypatch.setattr("handoff.pages.todos.autosave_editor", fake_autosave_editor)
    p1 = type("P", (), {"id": 1, "name": "Work"})()
    _render_editable_table(
        projects=[p1], helper_options=[], key_prefix="test", context_label="view=todos_page"
    )
    assert captured["key"] == "test_table_editor"
    assert callable(captured["persist_fn"])


def test_render_editable_table_shows_counts_and_no_results(monkeypatch: pytest.MonkeyPatch) -> None:
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
    empty_filtered = source_df.iloc[0:0].copy()
    filtered_query = TodoQuery(search_text="zzz-no-match")
    monkeypatch.setattr(
        "handoff.pages.todos._apply_native_filters",
        lambda *a, **kw: (
            filtered_query,
            {"project_filters": [], "status_filters": ["handoff"], "helper_filters": []},
        ),
    )
    monkeypatch.setattr(
        "handoff.pages.todos.query_todos",
        lambda query=None, **kw: [] if query == filtered_query else [object()],
    )
    monkeypatch.setattr(
        "handoff.pages.todos._build_todo_dataframe",
        lambda rows: empty_filtered if not rows else source_df,
    )
    monkeypatch.setattr(
        "handoff.pages.todos._sort_and_build_display_df", lambda df: (df, df.copy())
    )
    captions: list[str] = []
    info_messages: list[str] = []
    monkeypatch.setattr("handoff.pages.todos.st.caption", captions.append)
    monkeypatch.setattr("handoff.pages.todos.st.info", info_messages.append)
    monkeypatch.setattr("handoff.pages.todos.autosave_editor", lambda *a, **kw: None)
    monkeypatch.setattr("streamlit.session_state", {})
    p1 = type("P", (), {"id": 1, "name": "Work"})()
    _render_editable_table(
        projects=[p1], helper_options=[], key_prefix="test", context_label="view=todos_page"
    )
    assert "Showing 0 of 1 todo" in captions[0]
    assert "No todos match" in info_messages[0]


class TestRememberedDefaults:
    def test_remembered_project_and_helper(self, monkeypatch: pytest.MonkeyPatch) -> None:
        p1 = type("P", (), {"id": 1, "name": "Work"})()
        monkeypatch.setattr(
            "handoff.pages.todos._apply_native_filters",
            lambda *a, **kw: (
                type(
                    "Q",
                    (),
                    {
                        "search_text": "",
                        "statuses": (),
                        "project_ids": (),
                        "helper_names": (),
                        "deadline_start": None,
                        "deadline_end": None,
                        "include_archived": False,
                    },
                )(),
                {"project_filters": [], "status_filters": ["handoff"], "helper_filters": []},
            ),
        )
        monkeypatch.setattr("handoff.pages.todos.query_todos", lambda *a, **kw: [])
        monkeypatch.setattr(
            "handoff.pages.todos._build_todo_dataframe",
            lambda rows: pd.DataFrame(
                columns=[
                    "id",
                    "name",
                    "project",
                    "status",
                    "deadline",
                    "notes",
                    "created_at",
                    "helper",
                ]
            ),
        )
        monkeypatch.setattr(
            "handoff.pages.todos._sort_and_build_display_df", lambda df: (df.copy(), df.copy())
        )
        monkeypatch.setattr("handoff.pages.todos.st.caption", lambda *a, **kw: None)
        editor_calls: list[dict] = []
        monkeypatch.setattr(
            "handoff.pages.todos.st.data_editor", lambda *a, **kw: editor_calls.append(kw)
        )
        monkeypatch.setattr(
            "streamlit.session_state",
            {"test_last_new_project_id": 1, "test_last_new_helper": "Bob"},
        )
        _render_editable_table(
            projects=[p1], helper_options=[], key_prefix="test", context_label="test"
        )
        assert len(editor_calls) == 1
        cfg = editor_calls[0]["column_config"]
        assert cfg["project"]["default"] == "Work"
        assert cfg["helper"]["default"] == "Bob"


# --- render_todos_page ---


def test_render_todos_page_no_projects_shows_info(monkeypatch: pytest.MonkeyPatch) -> None:
    st_mock = MagicMock()
    monkeypatch.setattr("handoff.pages.todos.st", st_mock)
    monkeypatch.setattr("handoff.pages.todos.list_projects", lambda: [])
    render_todos_page()
    st_mock.info.assert_called_once()
    assert "No projects" in st_mock.info.call_args[0][0]
