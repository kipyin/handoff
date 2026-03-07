"""Additional tests for pages/todos.py to improve coverage.

Covers: _normalize_deadline, _build_update_input, _build_create_input,
_deadline_preset_bounds edge cases, _persist_changes edge cases.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

import pandas as pd

from handoff.models import TodoStatus
from handoff.page_models import TodoMutationDefaults
from handoff.pages.todos import (
    DEADLINE_ANY,
    DEADLINE_CUSTOM,
    DEADLINE_OVERDUE,
    DEADLINE_THIS_WEEK,
    DEADLINE_TOMORROW,
    _build_create_input,
    _build_update_input,
    _deadline_preset_bounds,
    _normalize_deadline,
    _persist_changes,
)


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


class TestDeadlinePresetBounds:
    def test_any_returns_none_none(self) -> None:
        assert _deadline_preset_bounds(DEADLINE_ANY) == (None, None)

    def test_custom_returns_none_none(self) -> None:
        assert _deadline_preset_bounds(DEADLINE_CUSTOM) == (None, None)

    def test_overdue(self) -> None:
        start, end = _deadline_preset_bounds(DEADLINE_OVERDUE)
        assert start == date.min
        assert end == date.today() - timedelta(days=1)

    def test_tomorrow(self) -> None:
        start, end = _deadline_preset_bounds(DEADLINE_TOMORROW)
        tomorrow = date.today() + timedelta(days=1)
        assert start == end == tomorrow

    def test_this_week(self) -> None:
        start, end = _deadline_preset_bounds(DEADLINE_THIS_WEEK)
        assert start is not None
        assert end is not None
        assert start.weekday() == 0  # Monday
        assert end.weekday() == 6  # Sunday
        assert start <= date.today() <= end

    def test_unknown_preset_returns_none(self) -> None:
        assert _deadline_preset_bounds("nonexistent") == (None, None)


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


class TestPersistChangesEdgeCases:
    def test_deletion_out_of_bounds_ignored(self, monkeypatch) -> None:
        """Deleted row index beyond dataframe length is silently ignored."""
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

    def test_edit_with_nan_todo_id_skipped(self, monkeypatch) -> None:
        """Rows with NaN __todo_id are skipped during edits."""
        calls = []
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

    def test_edit_out_of_bounds_skipped(self, monkeypatch) -> None:
        """Edits for row indices beyond the dataframe are skipped."""
        calls = []
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
