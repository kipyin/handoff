"""Tests for project service layer (create, list, rename, delete, archive, unarchive)."""

from __future__ import annotations

from contextlib import contextmanager

from sqlmodel import select

import handoff.data as data
from handoff.models import Project
from handoff.services import project_service


def _patch_session_context(monkeypatch, session) -> None:
    """Patch data module session context to reuse the test session."""

    @contextmanager
    def _session_context():
        yield session

    monkeypatch.setattr(data, "session_context", _session_context)


def test_create_project_via_service(session, monkeypatch) -> None:
    """create_project creates a project through the service boundary."""
    _patch_session_context(monkeypatch, session)
    p = project_service.create_project("Service Project")
    assert p.id is not None
    assert p.name == "Service Project"


def test_list_projects_via_service(session, monkeypatch) -> None:
    """list_projects returns projects through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="A"))
    session.add(Project(name="B"))
    session.commit()
    projects = project_service.list_projects()
    assert len(projects) == 2
    names = {p.name for p in projects}
    assert names == {"A", "B"}


def test_rename_project_via_service_success(session, monkeypatch) -> None:
    """rename_project renames a project through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="Old"))
    session.commit()
    project = next(session.exec(select(Project).where(Project.name == "Old")), None)
    assert project is not None
    updated = project_service.rename_project(project.id, "New")
    assert updated is not None
    assert updated.name == "New"


def test_rename_project_via_service_invalid_id_returns_none(session, monkeypatch) -> None:
    """rename_project returns None for non-existent project."""
    _patch_session_context(monkeypatch, session)
    result = project_service.rename_project(99999, "No")
    assert result is None


def test_delete_project_via_service_success(session, monkeypatch) -> None:
    """delete_project deletes a project through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="To Delete"))
    session.commit()
    project = next(session.exec(select(Project).where(Project.name == "To Delete")), None)
    assert project is not None
    ok = project_service.delete_project(project.id)
    assert ok is True
    assert session.get(Project, project.id) is None


def test_delete_project_via_service_invalid_id_returns_false(session, monkeypatch) -> None:
    """delete_project returns False for non-existent project."""
    _patch_session_context(monkeypatch, session)
    result = project_service.delete_project(99999)
    assert result is False


def test_archive_project_via_service_success(session, monkeypatch) -> None:
    """archive_project archives a project through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="To Archive", is_archived=False))
    session.commit()
    project = next(session.exec(select(Project).where(Project.name == "To Archive")), None)
    assert project is not None
    ok = project_service.archive_project(project.id)
    assert ok is True
    session.refresh(project)
    assert project.is_archived is True


def test_archive_project_via_service_invalid_id_returns_false(session, monkeypatch) -> None:
    """archive_project returns False for non-existent project."""
    _patch_session_context(monkeypatch, session)
    result = project_service.archive_project(99999)
    assert result is False


def test_unarchive_project_via_service_success(session, monkeypatch) -> None:
    """unarchive_project unarchives a project through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="To Unarchive", is_archived=True))
    session.commit()
    project = next(session.exec(select(Project).where(Project.name == "To Unarchive")), None)
    assert project is not None
    ok = project_service.unarchive_project(project.id)
    assert ok is True
    session.refresh(project)
    assert project.is_archived is False


def test_unarchive_project_via_service_invalid_id_returns_false(session, monkeypatch) -> None:
    """unarchive_project returns False for non-existent project."""
    _patch_session_context(monkeypatch, session)
    result = project_service.unarchive_project(99999)
    assert result is False


def test_get_projects_with_todo_summary_via_service(session, monkeypatch) -> None:
    """get_projects_with_todo_summary returns summary rows through the service boundary."""
    _patch_session_context(monkeypatch, session)
    session.add(Project(name="P"))
    session.commit()
    rows = project_service.get_projects_with_todo_summary()
    assert isinstance(rows, list)
    assert len(rows) >= 1
