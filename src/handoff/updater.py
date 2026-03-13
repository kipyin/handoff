"""In-app update panel and patch application helpers.

Patches for PyArmor-obfuscated distributions must be built with
uv run handoff build-patch from the obfuscated build output.
"""

import re
import shutil
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Any, BinaryIO

from loguru import logger

from .paths import get_app_root


def _log_app_action(action: str, **details: Any) -> None:
    """Log an application-level action (backup, update, restore). Delegates to handoff.logging."""
    import handoff.logging as _logging

    _logging.log_application_action(action, **details)


ALLOWED_PREFIXES = ("app.py", "src/", "README.md", "RELEASE_NOTES.md")
UPDATE_STAGING_DIR = "update"
# Backup and update are siblings under app_root: app_root/backup/, app_root/update/
BACKUP_DIR = "backup"


def _is_safe_member_path(name: str) -> bool:
    """Return True if *name* is a safe relative path with no traversal components."""
    if not name or name.startswith("/") or name.startswith("\\"):
        return False
    parts = Path(name).parts
    return ".." not in parts


def _read_patch_members(zf: zipfile.ZipFile) -> tuple[list[str], str | None]:
    """Read patch zip member names and optional VERSION from an open ZipFile.

    Skips directories, VERSION, paths with traversal components (``..``), and
    entries that don't start with ALLOWED_PREFIXES. Logs a warning for each
    rejected entry.

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
        if not _is_safe_member_path(name):
            logger.warning("Skipping unsafe path in patch zip: {}", name)
            continue
        if name.startswith(ALLOWED_PREFIXES):
            members.append(name)
        else:
            logger.warning("Skipping unexpected path in patch zip: {}", name)
    return members, target_version


def _extract_zip_to_dir(
    zf: zipfile.ZipFile, members: list[str], target_dir: Path
) -> tuple[list[str], list[str]]:
    """Extract named zip members into *target_dir*, preserving sub-paths.

    Continues past per-file failures so callers can report partial results.

    Returns:
        (extracted, failed) — lists of member names that succeeded and failed.

    """
    resolved_root = target_dir.resolve()
    target_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    failed: list[str] = []
    for name in members:
        dest = target_dir / name
        if not dest.resolve().is_relative_to(resolved_root):
            logger.warning("Path escapes target dir, skipping: {}", name)
            failed.append(name)
            continue
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            with zf.open(name) as src, dest.open("wb") as dst:
                shutil.copyfileobj(src, dst)
            extracted.append(name)
        except (PermissionError, OSError) as e:
            logger.warning("Could not extract {} to {}: {}", name, dest, e)
            failed.append(name)
    return extracted, failed


def _backup_existing_files(paths: list[str], app_root: Path, backup_root: Path) -> list[str]:
    """Copy files from *app_root* into *backup_root* for each path that exists.

    Returns:
        List of paths that were successfully backed up.

    """
    backed_up: list[str] = []
    for name in paths:
        source = app_root / name
        if not source.exists():
            continue
        dest = backup_root / name
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(source, dest)
            backed_up.append(name)
        except (PermissionError, OSError) as e:
            logger.warning("Could not backup {}: {}", name, e)
    return backed_up


def _get_app_root() -> Path:
    """Compatibility wrapper returning the application root directory."""
    return get_app_root()


def _backup_dir_name(app_version: str) -> str:
    """Return backup directory name: YYYYMMDD-HHMMSS-version<version>.

    Ensures backups sort by date and include the app version.

    Args:
        app_version: Current app version string (e.g. from handoff.version.__version__).

    Returns:
        Directory name for a backup snapshot.

    """
    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    return f"{timestamp}-version{app_version}"


def stage_patch_with_backup(
    file_like: BinaryIO,
    app_root: Path | None = None,
    app_version: str | None = None,
    upload_name: str | None = None,
) -> str:
    """Extract patch to update/, then create backup from app_root for paths in update/.

    Used when the user clicks Apply and Restart: the zip is extracted into update/
    first; the set of paths to backup is derived from the contents of update/
    (paths that will overwrite app_root when the launcher runs). Backup content
    is always copied from app_root (current installed files), not from update/.
    The launcher (handoff.bat) later copies update/ into the app root without
    starting Python, avoiding WinError 32 on locked .pyd files.

    Args:
        file_like: A binary file-like object positioned at the start of the zip.
        app_root: Optional explicit application root. Defaults to _get_app_root().
        app_version: Current app version for backup folder name.
        upload_name: Optional original patch zip filename (e.g. from an uploader).

    Returns:
        A human-readable status message.

    """
    if app_root is None:
        app_root = _get_app_root()
    if app_version is None:
        from handoff.version import __version__ as v

        app_version = v

    logger.info("Patch zip uploaded: {}", upload_name or "(no name)")

    file_like.seek(0)
    with zipfile.ZipFile(file_like) as zf:
        members, target_version = _read_patch_members(zf)

        if not members:
            return "No applicable files found in patch zip."

        staging = app_root / UPDATE_STAGING_DIR
        extracted, extract_failed = _extract_zip_to_dir(zf, members, staging)
        if not extracted:
            return f"Failed to extract patch to ./{UPDATE_STAGING_DIR}."
        if extract_failed:
            logger.warning("Some files could not be staged: {}", extract_failed)

    logger.info("Patch unzipped to {} containing: {}", staging, extracted)

    paths_to_backup = [p.relative_to(staging).as_posix() for p in staging.rglob("*") if p.is_file()]
    backup_dirname = _backup_dir_name(app_version)
    backup_root = app_root / BACKUP_DIR / backup_dirname
    backup_root.mkdir(parents=True, exist_ok=True)
    backed_up = _backup_existing_files(paths_to_backup, app_root, backup_root)
    logger.info("Backup of {} created at {}", backed_up, backup_root)
    _log_app_action(
        "app_backup",
        backup_path=str(backup_root),
        target_version=target_version or "(none)",
    )

    sentinel = app_root / LAST_UPDATE_BACKUP_FILE
    try:
        sentinel.write_text(f"{BACKUP_DIR}/{backup_dirname}", encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write {}: {}", sentinel, e)

    logger.info("Everything is in place and ready to update and restart.")
    logger.info("Program about to shut off in 2 seconds.")

    if target_version:
        logger.info("Staged patch for version {} in {}", target_version, staging)
        msg = (
            f"Update files are ready (target version: {target_version}). "
            "Close in 2s. "
            "Run handoff.bat again to complete the update."
        )
    else:
        logger.info("Staged patch in {}", staging)
        msg = "Update files are ready. Close in 2s. Run handoff.bat again to complete the update."

    if extract_failed:
        msg += f" Warning: {len(extract_failed)} file(s) could not be staged."
    return msg


def extract_patch_to_staging(file_like: BinaryIO, app_root: Path | None = None) -> str:
    """Extract a patch zip into app_root/update/ for the launcher to apply on next start.

    Does not overwrite files in the app root. For the in-app "Apply and Restart"
    flow, use stage_patch_with_backup() instead, which creates a backup first.
    This function is kept for tests and for callers that do not need a backup.

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
        extracted, extract_failed = _extract_zip_to_dir(zf, members, staging)
        if not extracted:
            return f"Failed to extract patch to ./{UPDATE_STAGING_DIR}."
        if extract_failed:
            logger.warning("Some files could not be staged: {}", extract_failed)

    if target_version:
        logger.info("Staged patch for version {} in {}", target_version, staging)
        msg = (
            f"Update files are ready (target version: {target_version}). "
            "The app will close in 2 seconds. "
            "Please run handoff.bat again to complete the update."
        )
    else:
        logger.info("Staged patch in {}", staging)
        msg = (
            "Update files are ready. The app will close in 2 seconds. "
            "Please run handoff.bat again to complete the update."
        )

    if extract_failed:
        msg += f" Warning: {len(extract_failed)} file(s) could not be staged."
    return msg


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

        from handoff.version import __version__ as app_version

        backup_dirname = _backup_dir_name(app_version)
        backup_root = app_root / BACKUP_DIR / backup_dirname
        backed_up = set(_backup_existing_files(members, app_root, backup_root))
        backup_failed = {m for m in members if m not in backed_up and (app_root / m).exists()}

        _extracted, extract_failed_list = _extract_zip_to_dir(zf, members, app_root)

    _clear_pycache(app_root)
    skipped = backup_failed | set(extract_failed_list)

    if target_version:
        logger.info("Applied patch to update app to version {}", target_version)
        _log_app_action("app_update", target_version=target_version)
        msg = f"Update applied. Target version: {target_version}."
    else:
        logger.info("Applied patch without explicit VERSION marker.")
        _log_app_action("app_update")
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

    from handoff.version import __version__ as app_version

    backup_dirname = _backup_dir_name(app_version)
    backup_root = app_root / BACKUP_DIR / backup_dirname
    member_names = [rel.as_posix() for rel in members]
    _backup_existing_files(member_names, app_root, backup_root)

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

    backup_path_str = f"{BACKUP_DIR}/{backup_dirname}"
    sentinel = app_root / LAST_UPDATE_BACKUP_FILE
    try:
        sentinel.write_text(backup_path_str, encoding="utf-8")
    except OSError as e:
        logger.warning("Could not write {}: {}", sentinel, e)

    logger.info("Applied staged update; backup at {}", backup_path_str)
    _log_app_action("app_update", backup_path=backup_path_str)
    return backup_path_str


def _get_backup_root(app_root: Path) -> Path:
    """Return the directory that holds timestamped backup snapshots.

    Args:
        app_root: Application root directory.

    Returns:
        Path to the backup directory (app_root/backup).

    """
    return app_root / BACKUP_DIR


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

    Supports both legacy (YYYYMMDD-HHMMSS) and versioned (YYYYMMDD-HHMMSS-versionX.Y.Z) names.

    Args:
        snapshot: Path to a timestamped backup directory.

    Returns:
        Formatted date string, optionally with version
        (for example "2026-03-02 00:06:12  version 2026.3.1").

    """
    name = snapshot.name
    match = re.match(r"^(\d{8}-\d{6})(?:-version(.+))?$", name)
    if not match:
        return name
    try:
        dt = datetime.strptime(match.group(1), "%Y%m%d-%H%M%S")
        label = dt.strftime("%Y-%m-%d %H:%M:%S")
        if match.group(2):
            label += f"  version {match.group(2)}"
        return label
    except ValueError:
        return name


def stage_restore_from_snapshot(
    snapshot: Path,
    app_root: Path | None = None,
) -> str:
    """Stage a backup snapshot into update/ for the launcher to apply on next start.

    Copies the snapshot contents into app_root/update/ (clearing update/ first).
    The launcher (handoff.bat) then copies update/ into the app root and removes update/,
    so no Python process touches the app root and locked files (e.g. PyArmor .pyd) can be replaced.

    Args:
        snapshot: Path to a timestamped backup directory under backup/.
        app_root: Optional explicit application root. Defaults to _get_app_root().

    Returns:
        A human-readable status message.

    Raises:
        FileNotFoundError: If the snapshot path does not exist or is not a directory.

    """
    if app_root is None:
        app_root = _get_app_root()

    if not snapshot.exists() or not snapshot.is_dir():
        raise FileNotFoundError(f"Backup snapshot not found: {snapshot}")

    logger.info("Restore from snapshot: {}", snapshot)
    _log_app_action("app_restore", snapshot=str(snapshot), staged="true")

    staging = app_root / UPDATE_STAGING_DIR
    if staging.exists():
        shutil.rmtree(staging, ignore_errors=True)
    staging.mkdir(parents=True, exist_ok=True)

    staged: list[str] = []
    for src in snapshot.rglob("*"):
        if src.is_dir():
            continue
        rel = src.relative_to(snapshot)
        dest = staging / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        try:
            shutil.copy2(src, dest)
            staged.append(rel.as_posix())
        except (PermissionError, OSError) as e:
            logger.warning("Could not stage {} from snapshot: {}", rel, e)

    logger.info("Staged {} files to {}: {}", len(staged), staging, staged)
    logger.info("Everything is in place and ready to restore. Run handoff.bat again to apply.")
    logger.info("Program about to shut off in 2 seconds.")

    return "Backup staged to ./update/. Close in 2s. Run handoff.bat again to restore."


def _restore_backup_snapshot(snapshot: Path, app_root: Path) -> str:
    """Restore all files from a backup snapshot into the app root.

    Used for direct in-process restore (e.g. tests). For the Settings UI restore
    flow, use stage_restore_from_snapshot() so the launcher applies the restore
    without starting Python first.

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
    _log_app_action("app_restore", snapshot=str(snapshot), applied="true")
    return "Backup restored."


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


def _can_apply_patch(
    patch_version: str | None,
    app_version: str,
    apply_anyway: bool,
) -> bool:
    """Determine whether the Apply button should be enabled for a patch.

    Args:
        patch_version: Version string from the patch zip (or None if no VERSION file).
        app_version: Current app version string.
        apply_anyway: User checked "apply older patch anyway".

    Returns:
        True if the patch can be applied (version is >= app or apply_anyway, or
        version parsing fails and we allow apply).

    """
    if patch_version is None:
        return True
    try:
        return apply_anyway or _parse_version(patch_version) >= _parse_version(app_version)
    except (ValueError, TypeError):
        return True
