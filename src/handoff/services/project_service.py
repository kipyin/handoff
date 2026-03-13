"""Project service boundary between UI pages and the data layer."""

from __future__ import annotations

from handoff.core.models import Project
from handoff.data import archive_project as _archive_project
from handoff.data import create_project as _create_project
from handoff.data import delete_project as _delete_project
from handoff.data import get_projects_with_handoff_summary as _get_projects_with_handoff_summary
from handoff.data import list_projects as _list_projects
from handoff.data import rename_project as _rename_project
from handoff.data import unarchive_project as _unarchive_project


def create_project(name: str) -> Project:
    """Create a project through the service boundary."""
    return _create_project(name)


def list_projects(*, include_archived: bool = False) -> list[Project]:
    """List projects through the service boundary."""
    return _list_projects(include_archived=include_archived)


def rename_project(project_id: int, name: str) -> Project | None:
    """Rename a project through the service boundary."""
    return _rename_project(project_id, name)


def delete_project(project_id: int) -> bool:
    """Delete a project through the service boundary."""
    return _delete_project(project_id)


def archive_project(project_id: int) -> bool:
    """Archive a project through the service boundary."""
    return _archive_project(project_id)


def unarchive_project(project_id: int) -> bool:
    """Unarchive a project through the service boundary."""
    return _unarchive_project(project_id)


def get_projects_with_handoff_summary(*, include_archived: bool = False) -> list[dict]:
    """Return project summary rows through the service boundary."""
    return _get_projects_with_handoff_summary(include_archived=include_archived)
