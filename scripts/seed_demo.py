"""Seed a demo database with representative handoffs and projects.

Used by `handoff run --demo` (auto-seed when empty) and `handoff seed-demo`.
Uses only handoff.data APIs. All dates derive from reference_date when
supplied; otherwise date.today().
"""

from __future__ import annotations

import os
from contextlib import contextmanager
from datetime import date
from pathlib import Path
from unittest.mock import patch

import handoff.data as data
import handoff.db as db
from handoff.dates import add_business_days


def seed_demo_db(
    db_path: Path | str,
    *,
    force: bool = False,
    reference_date: date | None = None,
) -> int:
    """Seed the database at db_path with demo projects and handoffs.

    Args:
        db_path: Path to the SQLite database file.
        force: When True, re-seed even if the DB already has projects.
        reference_date: Base date for all generated dates; uses date.today() if None.

    Returns:
        Number of handoffs created.
    """
    path = Path(db_path)
    path.parent.mkdir(parents=True, exist_ok=True)

    os.environ["HANDOFF_DB_PATH"] = str(path.resolve())
    db.dispose_db()
    db.init_db()

    projects = data.list_projects(include_archived=True)
    if projects and not force:
        return 0

    if force:
        for p in projects:
            if p.id is not None:
                data.delete_project(p.id)

    ref = reference_date or date.today()
    yesterday = add_business_days(ref, -1)
    tomorrow = add_business_days(ref, 1)
    next_week = add_business_days(ref, 5)
    next_month = add_business_days(ref, 22)
    last_week = add_business_days(ref, -5)

    acme = data.create_project("Acme Corp")
    personal = data.create_project("Personal")
    archived_proj = data.create_project("Archived Project")
    assert acme.id is not None
    assert personal.id is not None
    assert archived_proj.id is not None
    data.archive_project(archived_proj.id)

    data.create_handoff(
        project_id=archived_proj.id,
        need_back="Archived project handoff",
        next_check=next_week,
        pitchman="Eve",
    )
    count = 1

    risk_overdue = data.create_handoff(
        project_id=acme.id,
        need_back="Overdue deliverable",
        next_check=yesterday,
        deadline=yesterday,
        pitchman="Alice",
    )
    assert risk_overdue.id is not None
    data.create_check_in(
        handoff_id=risk_overdue.id,
        check_in_type=data.CheckInType.DELAYED,
        check_in_date=yesterday,
    )
    count += 1

    risk_due_today = data.create_handoff(
        project_id=acme.id,
        need_back="Due today",
        next_check=ref,
        deadline=ref,
        pitchman="Alice",
    )
    assert risk_due_today.id is not None
    data.create_check_in(
        handoff_id=risk_due_today.id,
        check_in_type=data.CheckInType.DELAYED,
        check_in_date=ref,
    )
    count += 1

    action_item = data.create_handoff(
        project_id=acme.id,
        need_back="Action required item",
        next_check=ref,
        deadline=tomorrow,
        pitchman="Bob",
    )
    assert action_item.id is not None
    data.create_check_in(
        handoff_id=action_item.id,
        check_in_type=data.CheckInType.ON_TRACK,
        check_in_date=ref,
    )
    count += 1

    data.create_handoff(
        project_id=personal.id,
        need_back="Upcoming task",
        next_check=next_week,
        deadline=next_week,
        pitchman="Carol",
    )
    count += 1

    concluded_h = data.create_handoff(
        project_id=acme.id,
        need_back="Concluded task",
        next_check=last_week,
        deadline=last_week,
        pitchman="Bob",
    )
    assert concluded_h.id is not None
    with _today_context(ref):
        data.conclude_handoff(concluded_h.id, note="Done")
    count += 1

    reopened_h = data.create_handoff(
        project_id=personal.id,
        need_back="Reopened handoff",
        next_check=ref,
        deadline=tomorrow,
        pitchman="Alice",
    )
    assert reopened_h.id is not None
    with _today_context(ref):
        data.conclude_handoff(reopened_h.id, note="Initial close")
    data.reopen_handoff(reopened_h.id, note="Reopened for follow-up", next_check_date=ref)
    count += 1

    data.create_handoff(
        project_id=personal.id,
        need_back="No pitchman, no dates",
        next_check=None,
        deadline=None,
        pitchman=None,
    )
    count += 1

    data.create_handoff(
        project_id=acme.id,
        need_back=(
            "Long description that goes on and on to test truncation and layout "
            "in the UI when the need_back text is very lengthy"
        ),
        next_check=next_month,
        deadline=next_month,
        pitchman="Dave",
    )
    count += 1

    data.create_handoff(
        project_id=personal.id,
        need_back="Notes with [markdown](url)",
        next_check=None,
        deadline=None,
        pitchman="Carol",
        notes="See [documentation](https://example.com) for details.",
    )
    count += 1

    return count


@contextmanager
def _today_context(ref: date):
    """Context manager that patches date.today() to return ref in handoff.data.handoffs."""
    from datetime import date as real_date

    with patch("handoff.data.handoffs.date") as mock_date:
        mock_date.today.return_value = ref
        mock_date.side_effect = lambda *a, **k: real_date(*a, **k)
        yield
