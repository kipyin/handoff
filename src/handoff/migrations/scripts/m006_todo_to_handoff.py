"""Migration 006: atomic cutover from todo to handoff + check_in tables.

Steps:
1. Create ``handoff`` table with new column names (need_back, pitchman) — or
   use the one already created by ``create_all``.
2. Copy rows from ``todo`` → ``handoff`` (name→need_back, helper→pitchman).
3. Create ``check_in`` table — or use the one from ``create_all``.
4. For each DONE todo, insert a concluded check-in (date from completed_at).
5. For each CANCELED todo, insert a concluded check-in with note.
6. Drop the ``todo`` table.

On a fresh database (no ``todo`` table), this migration is a no-op because
``create_all`` already created the new tables.
"""

from __future__ import annotations

from sqlalchemy.engine import Connection

version = "006_todo_to_handoff"


def _table_exists(conn: Connection, name: str) -> bool:
    rows = conn.exec_driver_sql(
        "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
        (name,),
    ).fetchall()
    return len(rows) > 0


def migrate(conn: Connection) -> None:
    if not _table_exists(conn, "todo"):
        return

    if not _table_exists(conn, "handoff"):
        conn.exec_driver_sql(
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
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX ix_handoff_project_id ON handoff (project_id)")
        conn.exec_driver_sql("CREATE INDEX ix_handoff_pitchman ON handoff (pitchman)")
        conn.exec_driver_sql("CREATE INDEX ix_handoff_next_check ON handoff (next_check)")
        conn.exec_driver_sql("CREATE INDEX ix_handoff_deadline ON handoff (deadline)")

    conn.exec_driver_sql(
        """
        INSERT OR IGNORE INTO handoff (
            id, project_id, need_back, pitchman,
            next_check, deadline, notes, created_at
        )
        SELECT
            id, project_id, name, helper,
            next_check, deadline, notes, created_at
        FROM todo
        """
    )

    if not _table_exists(conn, "check_in"):
        conn.exec_driver_sql(
            """
            CREATE TABLE check_in (
                id INTEGER PRIMARY KEY,
                handoff_id INTEGER NOT NULL REFERENCES handoff(id),
                check_in_date DATE NOT NULL,
                note TEXT,
                check_in_type TEXT NOT NULL,
                created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        conn.exec_driver_sql("CREATE INDEX ix_check_in_handoff_id ON check_in (handoff_id)")
        conn.exec_driver_sql("CREATE INDEX ix_check_in_check_in_type ON check_in (check_in_type)")

    conn.exec_driver_sql(
        """
        INSERT INTO check_in (handoff_id, check_in_date, note, check_in_type, created_at)
        SELECT id,
               COALESCE(DATE(completed_at), DATE(created_at)),
               NULL,
               'concluded',
               COALESCE(completed_at, created_at)
        FROM todo
        WHERE LOWER(status) = 'done'
        """
    )

    conn.exec_driver_sql(
        """
        INSERT INTO check_in (handoff_id, check_in_date, note, check_in_type, created_at)
        SELECT id,
               COALESCE(DATE(completed_at), DATE(created_at)),
               'canceled',
               'concluded',
               COALESCE(completed_at, created_at)
        FROM todo
        WHERE LOWER(status) = 'canceled'
        """
    )

    conn.exec_driver_sql("DROP TABLE todo")
