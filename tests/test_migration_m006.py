"""Tests for migration 006: todo → handoff + check_in cutover."""

from __future__ import annotations

import sqlite3
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.engine import Connection


def _migrate(conn: Connection) -> None:
    from handoff.migrations.scripts.m006_todo_to_handoff import migrate

    migrate(conn)


def _make_old_schema_db(path: str) -> None:
    """Create a minimal 'old-schema' SQLite DB with just a project + todo table."""
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE project (
            id INTEGER PRIMARY KEY,
            name TEXT NOT NULL,
            is_archived INTEGER NOT NULL DEFAULT 0,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE todo (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES project(id),
            name TEXT NOT NULL,
            helper TEXT,
            status TEXT NOT NULL DEFAULT 'handoff',
            next_check DATE,
            deadline DATE,
            notes TEXT,
            completed_at TIMESTAMP,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO project (id, name) VALUES (1, 'Proj');
        INSERT INTO todo (id, project_id, name, helper, status)
            VALUES (1, 1, 'Need report', 'Alice', 'handoff');
        INSERT INTO todo (id, project_id, name, helper, status, completed_at)
            VALUES (2, 1, 'Done thing', 'Bob', 'done',
                    '2026-01-15 10:00:00');
        INSERT INTO todo (id, project_id, name, helper, status, completed_at)
            VALUES (3, 1, 'Canceled item', NULL, 'canceled',
                    '2026-02-01 09:00:00');
        """
    )
    conn.commit()
    conn.close()


def test_m006_no_op_when_no_todo_table(tmp_path: Path) -> None:
    """Migration is a no-op when the todo table does not exist (fresh DB)."""
    db_path = str(tmp_path / "fresh.db")
    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        # No todo table → migrate() should return without touching anything.
        _migrate(conn)
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn_check.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn_check.close()
    # No tables created by the migration when todo is absent.
    assert "todo" not in tables


def test_m006_creates_handoff_table_from_todo(tmp_path: Path) -> None:
    """Migration copies todo rows into handoff table when todo exists."""
    db_path = str(tmp_path / "old.db")
    _make_old_schema_db(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    rows = conn_check.execute("SELECT need_back, pitchman FROM handoff").fetchall()
    names = [r[0] for r in rows]
    conn_check.close()

    assert "Need report" in names
    assert "Done thing" in names
    assert "Canceled item" in names


def test_m006_creates_check_in_for_done_todos(tmp_path: Path) -> None:
    """Migration inserts a concluded check-in for each DONE todo."""
    db_path = str(tmp_path / "done.db")
    _make_old_schema_db(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    rows = conn_check.execute("SELECT handoff_id, check_in_type, note FROM check_in").fetchall()
    conn_check.close()

    check_in_types = [r[1] for r in rows]
    assert check_in_types.count("concluded") >= 1


def test_m006_creates_check_in_for_canceled_todos(tmp_path: Path) -> None:
    """Migration inserts a concluded check-in with note='canceled' for CANCELED todos."""
    db_path = str(tmp_path / "canceled.db")
    _make_old_schema_db(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    rows = conn_check.execute("SELECT note FROM check_in WHERE note='canceled'").fetchall()
    conn_check.close()

    assert len(rows) == 1


def test_m006_drops_todo_table_after_migration(tmp_path: Path) -> None:
    """Migration drops the todo table after copying data."""
    db_path = str(tmp_path / "drop.db")
    _make_old_schema_db(db_path)

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn_check.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn_check.close()

    assert "todo" not in tables
    assert "handoff" in tables
    assert "check_in" in tables


def test_m006_skips_creating_handoff_table_when_it_already_exists(
    tmp_path: Path,
) -> None:
    """Migration reuses an existing handoff table rather than recreating it."""
    db_path = str(tmp_path / "existing_handoff.db")
    _make_old_schema_db(db_path)

    # Pre-create the handoff table to exercise the 'already exists' branch.
    conn_pre = sqlite3.connect(db_path)
    conn_pre.executescript(
        """
        CREATE TABLE handoff (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES project(id),
            need_back TEXT NOT NULL,
            pitchman TEXT,
            next_check DATE,
            deadline DATE,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn_pre.commit()
    conn_pre.close()

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn_check.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn_check.close()
    assert "handoff" in tables
    assert "todo" not in tables


def test_m006_existing_handoff_rows_preserved_on_id_conflict(tmp_path: Path) -> None:
    """Existing handoff rows are kept when todo ids collide during copy."""
    db_path = str(tmp_path / "existing_handoff_rows.db")
    _make_old_schema_db(db_path)

    # Simulate partial migration state where handoff already has one copied row.
    conn_pre = sqlite3.connect(db_path)
    conn_pre.executescript(
        """
        CREATE TABLE handoff (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES project(id),
            need_back TEXT NOT NULL,
            pitchman TEXT,
            next_check DATE,
            deadline DATE,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        INSERT INTO handoff (
            id, project_id, need_back, pitchman, next_check, deadline, notes, created_at
        ) VALUES (
            1, 1, 'Preexisting handoff', 'Preset', '2026-01-20', NULL, 'keep', '2026-01-01 00:00:00'
        );
        """
    )
    conn_pre.commit()
    conn_pre.close()

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    rows = conn_check.execute("SELECT id, need_back, pitchman FROM handoff ORDER BY id").fetchall()
    conn_check.close()

    assert rows[0] == (1, "Preexisting handoff", "Preset")
    assert {row[0] for row in rows} == {1, 2, 3}
    assert any(row[0] == 2 and row[1] == "Done thing" for row in rows)


def test_m006_skips_creating_check_in_table_when_it_already_exists(
    tmp_path: Path,
) -> None:
    """Migration reuses an existing check_in table rather than recreating it."""
    db_path = str(tmp_path / "existing_checkin.db")
    _make_old_schema_db(db_path)

    conn_pre = sqlite3.connect(db_path)
    conn_pre.executescript(
        """
        CREATE TABLE handoff (
            id INTEGER PRIMARY KEY,
            project_id INTEGER NOT NULL REFERENCES project(id),
            need_back TEXT NOT NULL,
            pitchman TEXT,
            next_check DATE,
            deadline DATE,
            notes TEXT,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        CREATE TABLE check_in (
            id INTEGER PRIMARY KEY,
            handoff_id INTEGER NOT NULL REFERENCES handoff(id),
            check_in_date DATE NOT NULL,
            note TEXT,
            check_in_type TEXT NOT NULL,
            created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
        );
        """
    )
    conn_pre.commit()
    conn_pre.close()

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    tables = {
        r[0]
        for r in conn_check.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    conn_check.close()
    assert "check_in" in tables
    assert "handoff" in tables
    assert "todo" not in tables


def test_m006_status_is_case_insensitive_and_completed_at_falls_back_to_created_at(
    tmp_path: Path,
) -> None:
    """DONE/CANCELED with null completed_at still create concluded check-ins."""
    db_path = str(tmp_path / "status_case_and_fallback.db")
    _make_old_schema_db(db_path)

    conn_seed = sqlite3.connect(db_path)
    conn_seed.executescript(
        """
        INSERT INTO todo (id, project_id, name, helper, status, created_at, completed_at)
            VALUES (4, 1, 'Upper done', 'Casey', 'DONE', '2026-03-10 08:15:00', NULL);
        INSERT INTO todo (id, project_id, name, helper, status, created_at, completed_at)
            VALUES (5, 1, 'Upper canceled', 'Dana', 'CANCELED', '2026-03-11 09:45:00', NULL);
        """
    )
    conn_seed.commit()
    conn_seed.close()

    engine = create_engine(f"sqlite:///{db_path}")
    with engine.connect() as conn:
        _migrate(conn)
        conn.commit()
    engine.dispose()

    conn_check = sqlite3.connect(db_path)
    rows = conn_check.execute(
        """
        SELECT handoff_id, check_in_date, note, check_in_type, created_at
        FROM check_in
        WHERE handoff_id IN (4, 5)
        ORDER BY handoff_id
        """
    ).fetchall()
    conn_check.close()

    assert rows == [
        (4, "2026-03-10", None, "concluded", "2026-03-10 08:15:00"),
        (5, "2026-03-11", "canceled", "concluded", "2026-03-11 09:45:00"),
    ]
