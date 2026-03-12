"""Import/export helpers for backup and restore."""

from __future__ import annotations

from typing import Any

from loguru import logger
from sqlmodel import select

from handoff.backup_schema import BackupPayload
from handoff.db import get_db_path, session_context
from handoff.models import CheckIn, Handoff, Project


def import_payload(data_payload: dict[str, Any]) -> None:
    """Replace all projects, handoffs and check-ins with the contents of *data_payload*.

    Accepts both the new format (``"handoffs"`` + ``"check_ins"``) and the legacy
    format (``"todos"``). The operation runs inside a single transaction.

    Args:
        data_payload: Dict with ``"projects"`` and ``"handoffs"``/``"check_ins"`` lists.

    Raises:
        KeyError: If required keys are missing.
        ValueError: If a record cannot be parsed.
    """
    payload = BackupPayload.from_dict(data_payload)

    with session_context() as session:
        session.exec(select(CheckIn)).all()
        session.exec(select(Handoff)).all()
        session.execute(CheckIn.__table__.delete())
        session.execute(Handoff.__table__.delete())
        session.execute(Project.__table__.delete())

        for p in payload.projects:
            project = Project(
                id=p.id,
                name=p.name,
                created_at=p.created_at,
                is_archived=p.is_archived,
            )
            session.add(project)

        for h in payload.handoffs:
            handoff = Handoff(
                id=h.id,
                project_id=h.project_id,
                need_back=h.need_back,
                pitchman=h.pitchman,
                next_check=h.next_check,
                deadline=h.deadline,
                notes=h.notes,
                created_at=h.created_at,
            )
            session.add(handoff)

        for c in payload.check_ins:
            check_in = CheckIn(
                id=c.id,
                handoff_id=c.handoff_id,
                check_in_date=c.check_in_date,
                note=c.note,
                check_in_type=c.check_in_type,
                created_at=c.created_at,
            )
            session.add(check_in)

        session.commit()
        logger.info(
            "data_import action=complete db_path={db_path} project_count={project_count} "
            "handoff_count={handoff_count} check_in_count={check_in_count}",
            db_path=str(get_db_path()),
            project_count=len(payload.projects),
            handoff_count=len(payload.handoffs),
            check_in_count=len(payload.check_ins),
        )


def get_export_payload() -> dict[str, Any]:
    """Return JSON-serializable snapshot of projects, handoffs, and check-ins.

    Returns:
        Dict with "projects", "handoffs", and "check_ins" keys.
    """
    with session_context() as session:
        projects = list(session.exec(select(Project).order_by(Project.created_at.asc())).all())
        handoffs = list(session.exec(select(Handoff).order_by(Handoff.created_at.asc())).all())
        check_ins = list(session.exec(select(CheckIn).order_by(CheckIn.created_at.asc())).all())
        return BackupPayload.from_models(projects, handoffs, check_ins).to_dict()
