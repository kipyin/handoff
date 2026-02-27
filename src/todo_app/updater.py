"""In-app update panel and patch application helpers.

Patches for PyArmor-obfuscated distributions must be built with
``uv run todo build-obfuscated-patch`` from the obfuscated build output.
"""

import os
import shutil
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

from loguru import logger

ALLOWED_PREFIXES = ("app.py", "src/", "README.md", "RELEASE_NOTES.md")


def _get_app_root() -> Path:
    """Return the root directory where app.py lives."""
    return Path(__file__).resolve().parents[2]


def apply_patch_zip(file_like: BinaryIO, app_root: Path | None = None) -> str:
    """Apply a code-only patch zip to the given app root.

    Args:
        file_like: A binary file-like object positioned at the start of the zip.
        app_root: Optional explicit application root. Defaults to the directory
            returned by :func:`_get_app_root`.

    Returns:
        A human-readable status message.
    """
    if app_root is None:
        app_root = _get_app_root()

    file_like.seek(0)
    with zipfile.ZipFile(file_like) as zf:
        namelist = zf.namelist()
        target_version = None
        if "VERSION" in namelist:
            with zf.open("VERSION") as vf:
                target_version = vf.read().decode("utf-8").strip()

        # Build list of files to extract, enforcing allowed prefixes.
        members = []
        for name in namelist:
            if name.endswith("/"):
                continue
            if name == "VERSION":
                continue
            if name.startswith(ALLOWED_PREFIXES):
                members.append(name)
            else:
                logger.warning("Skipping unexpected path in patch zip: {}", name)

        if not members:
            return "No applicable files found in patch zip."

        # Create a simple timestamped backup of affected files.
        backup_root = app_root / "backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
        for name in members:
            target_path = app_root / name
            if target_path.exists():
                backup_path = backup_root / name
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(target_path, backup_path)

        for name in members:
            target_path = app_root / name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            with zf.open(name) as src, target_path.open("wb") as dst:
                shutil.copyfileobj(src, dst)

    _clear_pycache(app_root)

    if target_version:
        logger.info("Applied patch to update app to version {}", target_version)
        return f"Update applied. Target version: {target_version}."
    logger.info("Applied patch without explicit VERSION marker.")
    return "Update applied."


def _clear_pycache(app_root: Path) -> None:
    """Remove Python bytecode caches under the app root.

    This clears ``__pycache__`` directories for the main code areas that are
    updated by the patch so that Python regenerates fresh bytecode for the new
    sources on next start.
    """
    for base in (app_root, app_root / "src", app_root / "pages"):
        if not base.exists():
            continue
        for pycache_dir in base.rglob("__pycache__"):
            if pycache_dir.is_dir():
                shutil.rmtree(pycache_dir, ignore_errors=True)


def _get_backup_root(app_root: Path) -> Path:
    """Return the directory that holds timestamped backup snapshots."""
    return app_root / "backup"


def _iter_backup_snapshots(app_root: Path) -> list[Path]:
    """Return available backup snapshot directories, newest first.

    Snapshots are created by :func:`apply_patch_zip` under
    ``backup/<YYYYMMDD-HHMMSS>/``. This helper filters for directories only and
    sorts them in reverse chronological order based on their folder names.
    """
    backup_root = _get_backup_root(app_root)
    if not backup_root.exists():
        return []

    snapshots = [path for path in backup_root.iterdir() if path.is_dir()]
    snapshots.sort(key=lambda path: path.name, reverse=True)
    return snapshots


def _format_snapshot_label(snapshot: Path) -> str:
    """Return a human-friendly label for a backup snapshot directory."""
    name = snapshot.name
    try:
        dt = datetime.strptime(name, "%Y%m%d-%H%M%S")
    except ValueError:
        return name
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _restore_backup_snapshot(snapshot: Path, app_root: Path) -> str:
    """Restore all files from a backup snapshot into the app root.

    Args:
        snapshot: Path to a timestamped backup directory under ``backup/``.
        app_root: Application root where files should be restored.

    Returns:
        A human-readable status message.
    """
    if not snapshot.exists() or not snapshot.is_dir():
        raise FileNotFoundError(f"Backup snapshot not found: {snapshot}")

    for src in snapshot.rglob("*"):
        if src.is_dir():
            continue
        relative_path = src.relative_to(snapshot)
        target_path = app_root / relative_path
        target_path.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(src, target_path)

    _clear_pycache(app_root)
    logger.info("Restored backup snapshot from {}", snapshot)
    return "Backup restored."


def _schedule_shutdown(delay_seconds: float = 2.0) -> None:
    """Schedule a hard process exit after a short delay.

    This is used after applying a patch so that the Streamlit process – and any
    wrapper like `run.bat` – terminate automatically without requiring the user
    to manually close the terminal window.

    Args:
        delay_seconds: Number of seconds to wait before exiting.
    """

    def _shutdown() -> None:
        os._exit(0)

    timer = threading.Timer(delay_seconds, _shutdown)
    timer.daemon = True
    timer.start()
