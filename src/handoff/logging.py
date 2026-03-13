"""Central logging configuration for the Handoff app.

This module configures loguru to:

- Log structured messages to standard output (for Streamlit and CLI runs).
- Write a rotating log file under the user's data directory (e.g. APPDATA on
  Windows), alongside the SQLite database.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

from loguru import logger
from platformdirs import user_data_dir

_CONFIGURED = False


def log_application_action(action: str, **details: Any) -> None:
    """Log an application-level action for audit (export, import, backup, update).

    Best-effort: never raises. Used by UI and updater so audit logging cannot
    break core flows.
    """
    try:
        from handoff.db import get_db_path

        db_path = str(get_db_path())
    except Exception:
        db_path = "(unknown)"
    parts = [f"action={action}", f"db_path={db_path}"]
    for k, v in details.items():
        parts.append(f"{k}={v}")
    logger.info("application " + " ".join(parts))


def _get_logs_dir() -> Path:
    """Return the directory where log files should be written.

    Log files are stored under the user's data directory (e.g. APPDATA on Windows).
    """
    data_dir = Path(user_data_dir("handoff", "handoff"))
    logs_dir = data_dir / "logs"
    logs_dir.mkdir(parents=True, exist_ok=True)
    return logs_dir


def configure_logging() -> None:
    """Configure loguru sinks for stdout and a rotating file.

    Safe to call multiple times; configuration is applied only once.
    """
    global _CONFIGURED
    if _CONFIGURED:
        return

    logs_dir = _get_logs_dir()
    log_path = logs_dir / "handoff.log"

    # Remove the default loguru handler to avoid duplicate logs, then add our
    # stdout + file sinks.
    logger.remove()
    logger.add(
        sink=lambda msg: print(msg, end=""),
        level="INFO",
        backtrace=False,
        diagnose=False,
    )
    logger.add(
        log_path,
        level="INFO",
        rotation="10 MB",
        retention="14 days",
        compression="zip",
        backtrace=False,
        diagnose=False,
    )

    _CONFIGURED = True
