"""Tests for demo database seeding."""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

from scripts.seed_demo import seed_demo_db

_COUNTABLE_TABLES = {"project", "handoff", "check_in"}


def _count_rows(db_path: Path, table: str) -> int:
    assert table in _COUNTABLE_TABLES
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
    assert row is not None
    return int(row[0])


def _fetch_handoff_dates(db_path: Path, need_back: str) -> tuple[str | None, str | None]:
    with sqlite3.connect(db_path) as conn:
        row = conn.execute(
            "SELECT deadline, next_check FROM handoff WHERE need_back = ?",
            (need_back,),
        ).fetchone()
    assert row is not None
    return row[0], row[1]


def test_seed_demo_db_creates_expected_counts(tmp_path: Path) -> None:
    """Seeding a fresh DB creates representative demo projects and handoffs."""
    db_path = tmp_path / "demo.db"

    seed_demo_db(db_path)

    assert db_path.exists()
    assert _count_rows(db_path, "project") >= 3
    assert _count_rows(db_path, "handoff") >= 9
    assert _count_rows(db_path, "check_in") >= 6


def test_seed_demo_db_is_idempotent_without_force(tmp_path: Path) -> None:
    """Running the seed twice without force should not duplicate rows."""
    db_path = tmp_path / "demo.db"

    seed_demo_db(db_path)
    counts_after_first_seed = {
        "project": _count_rows(db_path, "project"),
        "handoff": _count_rows(db_path, "handoff"),
        "check_in": _count_rows(db_path, "check_in"),
    }

    seed_demo_db(db_path)

    assert counts_after_first_seed == {
        "project": _count_rows(db_path, "project"),
        "handoff": _count_rows(db_path, "handoff"),
        "check_in": _count_rows(db_path, "check_in"),
    }


def test_seed_demo_db_uses_reference_date_for_relative_items(tmp_path: Path) -> None:
    """Reference-date seeding should generate deterministic deadlines/check dates."""
    db_path = tmp_path / "demo.db"
    reference_date = date(2026, 3, 9)

    seed_demo_db(db_path, reference_date=reference_date)

    due_today_deadline, due_today_next_check = _fetch_handoff_dates(db_path, "Due today")
    upcoming_deadline, upcoming_next_check = _fetch_handoff_dates(db_path, "Upcoming task")

    assert due_today_deadline == "2026-03-09"
    assert due_today_next_check == "2026-03-09"
    assert upcoming_deadline == "2026-03-16"
    assert upcoming_next_check == "2026-03-16"
