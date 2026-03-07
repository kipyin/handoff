"""Additional tests for pages/projects.py to improve coverage.

Covers: _execute_changes error paths (archive, delete), _apply_project_changes
no-changes case, delete_project returning False.
"""

from __future__ import annotations

import pandas as pd
import pytest

from handoff.models import Project
from handoff.pages.projects import (
    _apply_project_changes,
    _execute_changes,
)


@pytest.fixture
def mock_projects():
    return [
        Project(id=1, name="Work", is_archived=False),
        Project(id=2, name="Home", is_archived=False),
    ]


class TestExecuteChangesErrors:
    def test_archive_exception(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.projects.archive_project",
            lambda pid: (_ for _ in ()).throw(RuntimeError("Lock error")),
        )
        changes = [{"type": "archive", "id": 1, "archive": True}]
        deleted, updated, errors = _execute_changes(changes)
        assert updated == 0
        assert len(errors) == 1
        assert "Lock error" in errors[0]

    def test_unarchive_exception(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.projects.unarchive_project",
            lambda pid: (_ for _ in ()).throw(RuntimeError("Fail")),
        )
        changes = [{"type": "archive", "id": 1, "archive": False}]
        deleted, updated, errors = _execute_changes(changes)
        assert updated == 0
        assert len(errors) == 1

    def test_delete_returns_false(self, monkeypatch) -> None:
        monkeypatch.setattr("handoff.pages.projects.delete_project", lambda pid: False)
        changes = [{"type": "delete", "id": 1, "name": "Doomed"}]
        deleted, updated, errors = _execute_changes(changes)
        assert deleted == 0
        assert len(errors) == 1
        assert "Doomed" in errors[0]

    def test_delete_exception(self, monkeypatch) -> None:
        monkeypatch.setattr(
            "handoff.pages.projects.delete_project",
            lambda pid: (_ for _ in ()).throw(RuntimeError("DB locked")),
        )
        changes = [{"type": "delete", "id": 1, "name": "Fail"}]
        deleted, updated, errors = _execute_changes(changes)
        assert deleted == 0
        assert "DB locked" in errors[0]


class TestApplyProjectChangesOrchestration:
    def test_no_changes_detected(self, mock_projects) -> None:
        """When no changes are detected, returns success with zero counts."""
        df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Work",
                    "is_archived": False,
                    "confirm_delete": False,
                },
            ]
        )
        success, errors, deleted, updated = _apply_project_changes(df, mock_projects)
        assert success is True
        assert errors == []
        assert deleted == 0
        assert updated == 0

    def test_execution_errors_propagate(self, mock_projects, monkeypatch) -> None:
        """When execution errors occur, they are returned and success is False."""
        monkeypatch.setattr(
            "handoff.pages.projects.rename_project",
            lambda pid, name: (_ for _ in ()).throw(RuntimeError("nope")),
        )
        df = pd.DataFrame(
            [
                {
                    "__project_id": 1,
                    "name": "Changed",
                    "is_archived": False,
                    "confirm_delete": False,
                },
            ]
        )
        success, errors, deleted, updated = _apply_project_changes(df, mock_projects)
        assert success is False
        assert len(errors) > 0
