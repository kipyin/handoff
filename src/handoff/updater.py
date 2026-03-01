"""In-app update panel and patch application helpers.

Patches for PyArmor-obfuscated distributions must be built with
uv run handoff build-patch from the obfuscated build output.
"""

import os
import shutil
import threading
import zipfile
from datetime import datetime
from pathlib import Path
from typing import BinaryIO

import streamlit as st
from loguru import logger

ALLOWED_PREFIXES = ("app.py", "src/", "README.md", "RELEASE_NOTES.md")
UPDATE_STAGING_DIR = "update"


def _read_patch_members(zf: zipfile.ZipFile) -> tuple[list[str], str | None]:
    """Read patch zip member names and optional VERSION from an open ZipFile.

    Skips directories and VERSION; includes only names that start with ALLOWED_PREFIXES.
    Logs a warning for any other non-directory entry.

    Args:
        zf: An open zipfile.ZipFile positioned at the start.

    Returns:
        Tuple of (list of member paths to extract, optional version string from VERSION file).

    """
    namelist = zf.namelist()
    target_version = None
    if "VERSION" in namelist:
        with zf.open("VERSION") as vf:
            target_version = vf.read().decode("utf-8").strip()

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
    return members, target_version


def _get_app_root() -> Path:
    """Return the root directory where app.py lives.

    Returns:
        Path to the application root (parent of src/).

    """
    return Path(__file__).resolve().parents[2]


def extract_patch_to_staging(file_like: BinaryIO, app_root: Path | None = None) -> str:
    """Extract a patch zip into app_root/update/ for run.bat to apply on next start.

    Does not overwrite files in the app root. The app should then shut down so
    that run.bat can copy from ./update into the app root and remove ./update.

    Args:
        file_like: A binary file-like object positioned at the start of the zip.
        app_root: Optional explicit application root. Defaults to the directory
            returned by _get_app_root().

    Returns:
        A human-readable status message.

    """
    if app_root is None:
        app_root = _get_app_root()

    file_like.seek(0)
    with zipfile.ZipFile(file_like) as zf:
        members, target_version = _read_patch_members(zf)

        if not members:
            return "No applicable files found in patch zip."

        staging = app_root / UPDATE_STAGING_DIR
        staging.mkdir(parents=True, exist_ok=True)
        for name in members:
            target_path = staging / name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zf.open(name) as src, target_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            except (PermissionError, OSError) as e:
                logger.warning("Could not extract {} to staging: {}", name, e)
                return f"Failed to extract to ./{UPDATE_STAGING_DIR}: {e}"

    if target_version:
        logger.info("Staged patch for version {} in {}", target_version, staging)
        return (
            f"Update files are ready (target version: {target_version}). "
            "The app will close in 2 seconds. Please run run.bat again to complete the update."
        )
    logger.info("Staged patch in {}", staging)
    return (
        "Update files are ready. The app will close in 2 seconds. "
        "Please run run.bat again to complete the update."
    )


def apply_patch_zip(file_like: BinaryIO, app_root: Path | None = None) -> str:
    """Apply a code-only patch zip to the given app root.

    Args:
        file_like: A binary file-like object positioned at the start of the zip.
        app_root: Optional explicit application root. Defaults to the directory
            returned by _get_app_root().

    Returns:
        A human-readable status message.

    """
    if app_root is None:
        app_root = _get_app_root()

    file_like.seek(0)
    with zipfile.ZipFile(file_like) as zf:
        members, target_version = _read_patch_members(zf)

        if not members:
            return "No applicable files found in patch zip."

        skipped: list[str] = []

        # Create a simple timestamped backup of affected files.
        backup_root = app_root / "backup" / datetime.now().strftime("%Y%m%d-%H%M%S")
        for name in members:
            target_path = app_root / name
            if target_path.exists():
                backup_path = backup_root / name
                backup_path.parent.mkdir(parents=True, exist_ok=True)
                try:
                    shutil.copy2(target_path, backup_path)
                except (PermissionError, OSError) as e:
                    logger.warning("Could not backup {}: {}", name, e)
                    skipped.append(name)

        for name in members:
            target_path = app_root / name
            target_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                with zf.open(name) as src, target_path.open("wb") as dst:
                    shutil.copyfileobj(src, dst)
            except (PermissionError, OSError) as e:
                logger.warning("Could not extract {}: {}", name, e)
                if name not in skipped:
                    skipped.append(name)

    _clear_pycache(app_root)

    if target_version:
        logger.info("Applied patch to update app to version {}", target_version)
        msg = f"Update applied. Target version: {target_version}."
    else:
        logger.info("Applied patch without explicit VERSION marker.")
        msg = "Update applied."

    if skipped:
        msg += (
            " Some files could not be updated while the app is running (e.g. PyArmor runtime). "
            "Restart the app and re-apply the patch to update them, or ignore if not needed."
        )
    return msg


def _clear_pycache(app_root: Path) -> None:
    """Remove Python bytecode caches under the app root.

    This clears __pycache__ directories for the main code areas that are
    updated by the patch so that Python regenerates fresh bytecode for the new
    sources on next start.
    """
    for base in (app_root, app_root / "src"):
        if not base.exists():
            continue
        for pycache_dir in base.rglob("__pycache__"):
            if pycache_dir.is_dir():
                shutil.rmtree(pycache_dir, ignore_errors=True)


LAST_UPDATE_BACKUP_FILE = ".last_update_backup"


def apply_staged_update(app_root: Path | None = None) -> str | None:
    """Apply the staged update from app_root/update/ and create a timestamped backup.

    If app_root/update/ does not exist or has no files, returns None. Otherwise
    backs up any existing files that will be overwritten to backup/YYYYMMDD-HHMMSS/,
    copies update/ into the app root, removes update/, clears pycache, writes the
    backup path to .last_update_backup for the UI, and returns the backup path string.

    Args:
        app_root: Optional explicit application root. Defaults to _get_app_root().

    Returns:
        Relative backup path (e.g. "backup/20260301-143022") or None if no update.
    """
    if app_root is None:
        app_root = _get_app_root()

    staging = app_root / UPDATE_STAGING_DIR
    if not staging.exists() or not staging.is_dir():
        return None

    members: list[Path] = []
    for path in staging.rglob("*"):
        if path.is_file():
            members.append(path.relative_to(staging))

    if not members:
        return None

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    backup_root = app_root / "backup" / timestamp

    for rel in members:
        name = rel.as_posix()
        target_path = app_root / name
        if target_path.exists():
            backup_path = backup_root / name
            backup_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.copy2(target_path, backup_path)
            except (PermissionError, OSError) as e:
                logger.warning("Could not backup {}: {}", name, e)

    for rel in members:
        name = rel.as_posix()
        src_path = staging / name
        target_path = app_root / name
        target_path.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src_path, target_path)
        except (PermissionError, OSError) as e:
            logger.warning("Could not apply {}: {}", name, e)

    shutil.rmtree(staging, ignore_errors=True)
    _clear_pycache(app_root)

    backup_path_str = f"backup/{timestamp}"
    sentinel = app_root / LAST_UPDATE_BACKUP_FILE
    try:
        sentinel.write_text(backup_path_str, encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write {}: {}", sentinel, e)

    logger.info("Applied staged update; backup at {}", backup_path_str)
    return backup_path_str


def _get_backup_root(app_root: Path) -> Path:
    """Return the directory that holds timestamped backup snapshots.

    Args:
        app_root: Application root directory.

    Returns:
        Path to the backup directory (app_root/backup).

    """
    return app_root / "backup"


def _iter_backup_snapshots(app_root: Path) -> list[Path]:
    """Return available backup snapshot directories, newest first.

    Snapshots are created by apply_patch_zip under
    backup/YYYYMMDD-HHMMSS/. This helper filters for directories only and
    sorts them in reverse chronological order based on their folder names.

    Args:
        app_root: Application root directory.

    Returns:
        List of snapshot paths, newest first.

    """
    backup_root = _get_backup_root(app_root)
    if not backup_root.exists():
        return []

    snapshots = [path for path in backup_root.iterdir() if path.is_dir()]
    snapshots.sort(key=lambda path: path.name, reverse=True)
    return snapshots


def _format_snapshot_label(snapshot: Path) -> str:
    """Return a human-friendly label for a backup snapshot directory.

    Args:
        snapshot: Path to a timestamped backup directory.

    Returns:
        Formatted date string (e.g. YYYY-MM-DD HH:MM:SS), or directory name if not parseable.

    """
    name = snapshot.name
    try:
        dt = datetime.strptime(name, "%Y%m%d-%H%M%S")
    except ValueError:
        return name
    return dt.strftime("%Y-%m-%d %H:%M:%S")


def _restore_backup_snapshot(snapshot: Path, app_root: Path) -> str:
    """Restore all files from a backup snapshot into the app root.

    Args:
        snapshot: Path to a timestamped backup directory under backup/.
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


def _parse_version(version_str: str) -> tuple[int, ...]:
    """Parse a version string like '2026.2.23' into a comparable tuple of ints.

    Args:
        version_str: Version string (e.g. 2026.2.23).

    Returns:
        Tuple of integers for lexicographic comparison.

    """
    parts = version_str.strip().split(".")
    result = []
    for p in parts:
        try:
            result.append(int(p))
        except ValueError:
            result.append(0)
    return tuple(result)


def get_patch_version(file_like: BinaryIO) -> str | None:
    """Read the VERSION file from a patch zip without applying it.

    Args:
        file_like: A binary file-like object positioned at the start of the zip.

    Returns:
        The patch target version string, or None if no VERSION file is present.

    """
    file_like.seek(0)
    with zipfile.ZipFile(file_like) as zf:
        if "VERSION" not in zf.namelist():
            return None
        with zf.open("VERSION") as vf:
            return vf.read().decode("utf-8").strip()
    return None


def render_update_panel(app_version: str) -> None:
    """Render the Streamlit update and backup-restore panel on the Settings page.

    Shows an "App updates" section (patch zip upload, version check, apply and restart)
    and a "Restore from backup" section (snapshot list and restore).

    Args:
        app_version: Current app version string (e.g. from handoff.version.__version__).

    """
    st.markdown("### App updates")
    st.caption(
        "Upload a code-only patch zip (e.g. from a Handoff release). The patch is extracted to "
        "./update/ and the app will close in 2 seconds. Run run.bat again to apply the update and "
        "start the app."
    )

    app_root = _get_app_root()
    patch_file = st.file_uploader(
        "Patch zip",
        type=["zip"],
        key="settings_patch_zip_upload",
    )

    apply_anyway = False
    patch_version = None
    if patch_file is not None:
        patch_version = get_patch_version(patch_file)
        if patch_version:
            st.caption(f"Patch version: {patch_version}")
            try:
                patch_tuple = _parse_version(patch_version)
                app_tuple = _parse_version(app_version)
                if patch_tuple < app_tuple:
                    st.warning(
                        f"This patch is older ({patch_version}) than the current app ({app_version}). "
                        "Applying may overwrite newer code."
                    )
                    apply_anyway = st.checkbox(
                        "I understand, apply this older patch anyway",
                        key="settings_apply_older_patch",
                    )
            except (ValueError, TypeError):
                pass
        else:
            st.caption("Patch has no VERSION file.")

    if patch_file is not None:
        try:
            can_apply = (
                patch_version is None
                or apply_anyway
                or _parse_version(patch_version) >= _parse_version(app_version)
            )
        except (ValueError, TypeError):
            can_apply = True
        if st.button("Apply and Restart", key="settings_apply_patch", disabled=not can_apply):
            patch_file.seek(0)
            msg = extract_patch_to_staging(patch_file, app_root=app_root)
            st.success(msg)
            _schedule_shutdown(2.0)

    # One-time message after an update: show where the backup was saved.
    sentinel = app_root / LAST_UPDATE_BACKUP_FILE
    if sentinel.exists():
        try:
            backup_path = sentinel.read_text(encoding="utf-8").strip()
            st.info(
                f"Update applied. A backup of the previous files was saved to **{backup_path}**."
            )
        except OSError:
            pass
        try:
            sentinel.unlink()
        except OSError:
            pass

    st.markdown("### Restore from backup")
    st.caption(
        "Restore code from a timestamped backup created when applying a patch. "
        "Pick a snapshot and click Restore; the app will restart."
    )
    snapshots = _iter_backup_snapshots(app_root)
    if not snapshots:
        st.caption("No backup snapshots found.")
    else:
        labels = [_format_snapshot_label(s) for s in snapshots]
        snapshot_names = [s.name for s in snapshots]
        selected = st.selectbox(
            "Backup snapshot",
            range(len(snapshots)),
            format_func=lambda i: labels[i],
            key="settings_restore_snapshot",
        )
        if selected is not None and st.button("Restore and Restart", key="settings_restore_backup"):
            snapshot_path = snapshots[selected]
            msg = _restore_backup_snapshot(snapshot_path, app_root)
            st.success(msg)
            _schedule_shutdown()
