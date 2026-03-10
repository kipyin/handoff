"""Project data access helpers."""

from __future__ import annotations

from loguru import logger
from sqlmodel import select

from handoff.data_activity import log_activity
from handoff.db import session_context
from handoff.models import Project


def create_project(name: str) -> Project:
    """Create a new project.

    Args:
        name: Display name of the project.

    Returns:
        The created Project.
    """
    with session_context() as session:
        project = Project(name=name)
        session.add(project)
        session.commit()
        session.refresh(project)
        logger.info(
            "Created project {project_id}: {name}", project_id=project.id, name=project.name
        )
        log_activity("project", project.id, "created", {"name": project.name})
        return project


def list_projects(*, include_archived: bool = False) -> list[Project]:
    """Return all projects ordered by creation (newest first).

    Args:
        include_archived: When True, include archived projects.

    Returns:
        List of projects, newest first.
    """
    with session_context() as session:
        stmt = select(Project).order_by(Project.created_at.desc())
        if not include_archived:
            stmt = stmt.where(Project.is_archived.is_(False))
        return list(session.exec(stmt).all())


def get_project(project_id: int) -> Project | None:
    """Return a project by id with its handoffs loaded.

    Args:
        project_id: Id of the project.

    Returns:
        The project with handoffs eagerly loaded, or None if not found.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if project:
            _ = project.handoffs
        return project


def rename_project(project_id: int, name: str) -> Project | None:
    """Rename an existing project.

    Args:
        project_id: Id of the project to rename.
        name: New project name.

    Returns:
        Updated project, or None when not found.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for rename", project_id=project_id)
            return None
        project.name = name
        session.add(project)
        session.commit()
        session.refresh(project)
        logger.info("Renamed project {project_id} to {name}", project_id=project_id, name=name)
        log_activity("project", project_id, "updated", {"name": name})
        return project


def delete_project(project_id: int) -> bool:
    """Delete a project and its handoffs.

    Args:
        project_id: Id of the project to delete.

    Returns:
        True when deleted, otherwise False.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for delete", project_id=project_id)
            return False
        handoff_count = len(project.handoffs)
        proj_name = project.name
        session.delete(project)
        session.commit()
        logger.info(
            "Deleted project {project_id} and {handoff_count} handoffs",
            project_id=project_id,
            handoff_count=handoff_count,
        )
        log_activity(
            "project", project_id, "deleted", {"name": proj_name, "handoff_count": handoff_count}
        )
        return True


def archive_project(project_id: int) -> bool:
    """Archive a project. Handoffs are hidden via project filtering.

    Args:
        project_id: Id of the project to archive.

    Returns:
        True when archived, otherwise False.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for archive", project_id=project_id)
            return False
        project.is_archived = True
        session.add(project)
        session.commit()
        logger.info("Archived project {project_id}", project_id=project_id)
        log_activity("project", project_id, "archived", {})
        return True


def unarchive_project(project_id: int) -> bool:
    """Unarchive a project.

    Args:
        project_id: Id of the project to unarchive.

    Returns:
        True when unarchived, otherwise False.
    """
    with session_context() as session:
        project = session.get(Project, project_id)
        if not project:
            logger.warning("Project {project_id} not found for unarchive", project_id=project_id)
            return False
        project.is_archived = False
        session.add(project)
        session.commit()
        logger.info("Unarchived project {project_id}", project_id=project_id)
        log_activity("project", project_id, "unarchived", {})
        return True
