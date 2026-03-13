"""Seed a database with deterministic demo data for local demos and UAT."""

from __future__ import annotations

from contextlib import contextmanager
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from sqlalchemy.engine import Engine
from sqlalchemy.orm import close_all_sessions
from sqlmodel import Session, SQLModel, create_engine

from handoff.dates import add_business_days


def _build_engine(db_path: Path) -> Engine:
    """Create and initialize an engine for the requested SQLite path."""
    from handoff.core import models as _models  # noqa: F401
    from handoff.migrations import run_pending_migrations

    engine = create_engine(f"sqlite:///{db_path}", echo=False)
    SQLModel.metadata.create_all(engine)
    run_pending_migrations(engine)
    return engine


@contextmanager
def _patch_data_session_context(engine: Engine):
    """Temporarily point handoff.data helpers at a specific engine."""
    import handoff.data as data
    import handoff.data.activity as data_activity
    import handoff.data.handoffs as data_handoffs
    import handoff.data.io as data_io
    import handoff.data.projects as data_projects
    import handoff.data.queries as data_queries

    modules: tuple[Any, ...] = (
        data_activity,
        data_handoffs,
        data_io,
        data_projects,
        data_queries,
    )
    original_contexts = {module: module.session_context for module in modules}

    @contextmanager
    def session_context():
        with Session(engine) as session:
            yield session

    for module in modules:
        module.session_context = session_context

    try:
        yield data
    finally:
        close_all_sessions()
        for module, original_context in original_contexts.items():
            module.session_context = original_context


def _seed_projects(data) -> dict[str, int]:
    """Create the demo projects and return their ids keyed by name."""
    acme = data.create_project("Acme Corp")
    personal = data.create_project("Personal")
    archived = data.create_project("Archived Project")
    assert acme.id is not None
    assert personal.id is not None
    assert archived.id is not None
    data.archive_project(archived.id)
    return {
        "acme": acme.id,
        "personal": personal.id,
        "archived": archived.id,
    }


def _seed_handoffs(data, *, project_ids: dict[str, int], reference_date: date) -> None:
    """Create representative demo handoffs and check-ins."""
    risk_overdue = data.create_handoff(
        project_id=project_ids["acme"],
        need_back="Overdue deliverable",
        pitchman="Alice",
        next_check=reference_date - timedelta(days=1),
        deadline=reference_date - timedelta(days=1),
        notes="Waiting on revised numbers before we can send the deck.",
    )
    assert risk_overdue.id is not None
    data.create_check_in(
        handoff_id=risk_overdue.id,
        check_in_type=data.CheckInType.DELAYED,
        check_in_date=reference_date - timedelta(days=1),
        note="Blocked on finance input.",
    )

    risk_today = data.create_handoff(
        project_id=project_ids["acme"],
        need_back="Due today",
        pitchman="Alice",
        next_check=reference_date,
        deadline=reference_date,
        notes="Customer review scheduled for this afternoon.",
    )
    assert risk_today.id is not None
    data.create_check_in(
        handoff_id=risk_today.id,
        check_in_type=data.CheckInType.DELAYED,
        check_in_date=reference_date,
        note="Needs a final legal sign-off.",
    )

    action_required = data.create_handoff(
        project_id=project_ids["acme"],
        need_back="Action required item",
        pitchman="Bob",
        next_check=reference_date,
        deadline=add_business_days(reference_date, 1),
        notes="Ask Bob to confirm the rollout checklist.",
    )
    assert action_required.id is not None
    data.create_check_in(
        handoff_id=action_required.id,
        check_in_type=data.CheckInType.ON_TRACK,
        check_in_date=reference_date - timedelta(days=1),
        note="Waiting for today's confirmation.",
    )

    data.create_handoff(
        project_id=project_ids["personal"],
        need_back="Upcoming task",
        pitchman="Carol",
        next_check=add_business_days(reference_date, 5),
        deadline=add_business_days(reference_date, 5),
        notes="Prep notes for next week's planning meeting.",
    )

    concluded = data.create_handoff(
        project_id=project_ids["personal"],
        need_back="Concluded task",
        pitchman="Bob",
        next_check=reference_date - timedelta(days=7),
        deadline=reference_date - timedelta(days=5),
        notes="Finished and ready to archive later.",
    )
    assert concluded.id is not None
    data.create_check_in(
        handoff_id=concluded.id,
        check_in_type=data.CheckInType.ON_TRACK,
        check_in_date=reference_date - timedelta(days=7),
        note="In progress.",
    )
    data.create_check_in(
        handoff_id=concluded.id,
        check_in_type=data.CheckInType.CONCLUDED,
        check_in_date=reference_date - timedelta(days=5),
        note="Wrapped up last week.",
    )

    reopened = data.create_handoff(
        project_id=project_ids["personal"],
        need_back="Reopened handoff",
        pitchman="Alice",
        next_check=reference_date,
        deadline=add_business_days(reference_date, 1),
        notes="This was reopened after a follow-up question.",
    )
    assert reopened.id is not None
    data.create_check_in(
        handoff_id=reopened.id,
        check_in_type=data.CheckInType.CONCLUDED,
        check_in_date=reference_date - timedelta(days=1),
        note="Originally thought done.",
    )
    data.create_check_in(
        handoff_id=reopened.id,
        check_in_type=data.CheckInType.ON_TRACK,
        check_in_date=reference_date,
        note="Follow-up requested after reopen.",
        next_check_date=reference_date,
    )

    data.create_handoff(
        project_id=project_ids["personal"],
        need_back="No pitchman, no dates",
        notes="Useful edge case for blank optional fields.",
    )

    data.create_handoff(
        project_id=project_ids["personal"],
        need_back=(
            "Long description for a cross-team migration handoff that spans multiple "
            "milestones and needs a realistic amount of wrapping text in the UI."
        ),
        pitchman="Dave",
        next_check=add_business_days(reference_date, 20),
        deadline=add_business_days(reference_date, 20),
        notes="Keep this visible as a long-text layout example.",
    )

    data.create_handoff(
        project_id=project_ids["personal"],
        need_back="Notes with markdown",
        pitchman="Carol",
        notes="Review the [draft brief](https://example.com/demo-brief) before Friday.",
    )

    data.create_handoff(
        project_id=project_ids["archived"],
        need_back="Archived project follow-up",
        pitchman="Eve",
        next_check=reference_date,
        deadline=add_business_days(reference_date, 2),
        notes="Hidden by default unless archived projects are included.",
    )


def seed_demo_db(
    db_path: str | Path,
    *,
    force: bool = False,
    reference_date: date | None = None,
) -> Path:
    """Seed the requested SQLite database with demo data.

    When ``force`` is false, an already-seeded DB is left unchanged.
    """
    resolved_path = Path(db_path).expanduser().resolve()
    resolved_path.parent.mkdir(parents=True, exist_ok=True)
    effective_date = reference_date or date.today()

    if force and resolved_path.exists():
        resolved_path.unlink()

    engine = _build_engine(resolved_path)
    try:
        with _patch_data_session_context(engine) as data:
            if not force and data.list_projects(include_archived=True):
                return resolved_path
            project_ids = _seed_projects(data)
            _seed_handoffs(data, project_ids=project_ids, reference_date=effective_date)
            return resolved_path
    finally:
        close_all_sessions()
        engine.dispose()
