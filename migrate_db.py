# migrate_db.py
import os
import platform
import sqlite3
from pathlib import Path

def get_db_path():
    """Determine the database path based on the OS and app name."""
    if platform.system() == "Windows":
        # Based on the logs provided in the prompt
        return Path(os.path.expanduser("~")) / "AppData/Local/handoff/handoff/todo.db"
    else:
        # Fallback for macOS/Linux if needed
        return Path(os.path.expanduser("~")) / "Library/Application Support/handoff/todo.db"

db_path = get_db_path()

if not db_path.exists():
    print(f"DB not found at {db_path}")
else:
    print(f"Connecting to {db_path}...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    
    # Truncate the deadline strings to just the date part (first 10 chars)
    # This converts '2026-02-24 00:00:00.000000' to '2026-02-24'
    # This ensures SQLAlchemy's Date type can parse the string correctly.
    cursor.execute(
        "UPDATE todo SET deadline = SUBSTR(deadline, 1, 10) "
        "WHERE deadline IS NOT NULL AND LENGTH(deadline) > 10;"
    )
    
    rows_affected = cursor.rowcount
    conn.commit()
    print(f"Successfully migrated {rows_affected} rows in {db_path}")
    conn.close()
