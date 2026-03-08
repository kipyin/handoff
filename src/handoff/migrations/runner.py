"""Migration runner — applies numbered migration scripts in order."""

from __future__ import annotations

from loguru import logger
from sqlalchemy.engine import Connection, Engine

from handoff.migrations import scripts

SCHEMA_VERSION_TABLE = "schema_version"


def _ensure_schema_version_table(conn: Connection) -> None:
    """Create the schema_version table if it does not exist."""
    conn.exec_driver_sql(
        f"""
        CREATE TABLE IF NOT EXISTS {SCHEMA_VERSION_TABLE} (
            version TEXT PRIMARY KEY,
            applied_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
    )


def get_applied_versions(conn: Connection) -> set[str]:
    """Return the set of migration version strings that have been applied."""
    _ensure_schema_version_table(conn)
    result = conn.exec_driver_sql(f"SELECT version FROM {SCHEMA_VERSION_TABLE}")
    return {row[0] for row in result}


def run_pending_migrations(engine: Engine) -> None:
    """Run all pending migrations in order.

    Migrations are scripts in the scripts module, ordered by their numeric prefix.
    Each script exposes: version (str), migrate(conn: Connection) -> None.
    """
    with engine.begin() as conn:
        _ensure_schema_version_table(conn)
        applied = get_applied_versions(conn)

        for mod in scripts.ALL:
            if mod.version in applied:
                continue
            logger.info("Applying migration: {}", mod.version)
            mod.migrate(conn)
            conn.exec_driver_sql(
                f"INSERT INTO {SCHEMA_VERSION_TABLE} (version) VALUES (?)",
                (mod.version,),
            )
