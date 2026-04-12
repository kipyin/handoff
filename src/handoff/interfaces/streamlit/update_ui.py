"""Streamlit-specific update panel built on top of the pure updater core."""

from __future__ import annotations

import os
import threading
from contextlib import suppress

import streamlit as st
from loguru import logger

from handoff.bootstrap.paths import get_app_root
from handoff.updater import (
    LAST_UPDATE_BACKUP_FILE,
    _can_apply_patch,
    _format_snapshot_label,
    _iter_backup_snapshots,
    _parse_version,
    get_patch_version,
    stage_patch_with_backup,
    stage_restore_from_snapshot,
)


def _schedule_shutdown(delay_seconds: float = 2.0) -> None:
    """Schedule a hard process exit after a short delay."""

    def _shutdown() -> None:
        os._exit(0)

    timer = threading.Timer(delay_seconds, _shutdown)
    timer.daemon = True
    timer.start()


def render_update_panel(app_version: str) -> None:
    """Render the Streamlit update and restore UI."""
    st.markdown("### App updates")
    st.caption(
        "Upload a code-only patch zip (e.g. from a Handoff release). The patch is extracted to "
        "./update/ and the app will close in 2 seconds. Run handoff.bat again to apply the "
        "update and start the app."
    )

    app_root = get_app_root()
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
            patch_tuple = _parse_version(patch_version)
            app_tuple = _parse_version(app_version)
            if patch_tuple < app_tuple:
                st.warning(
                    f"This patch is older ({patch_version}) than the current app "
                    f"({app_version}). Applying may overwrite newer code."
                )
                apply_anyway = st.checkbox(
                    "I understand, apply this older patch anyway",
                    key="settings_apply_older_patch",
                )
        else:
            st.caption("Patch has no VERSION file.")

    if patch_file is not None:
        can_apply = _can_apply_patch(patch_version, app_version, apply_anyway)
        if st.button("Apply and Restart", key="settings_apply_patch", disabled=not can_apply):
            patch_file.seek(0)
            try:
                msg = stage_patch_with_backup(
                    patch_file,
                    app_root=app_root,
                    app_version=app_version,
                    upload_name=patch_file.name,
                )
            except Exception as exc:
                logger.exception("Failed to stage patch update.")
                st.error(f"Failed to stage update: {exc}")
            else:
                st.success(msg)
                _schedule_shutdown(2.0)

    sentinel = app_root / LAST_UPDATE_BACKUP_FILE
    if sentinel.exists():
        with suppress(OSError):
            backup_path = sentinel.read_text(encoding="utf-8").strip()
            st.info(
                f"Update applied. A backup of the previous files was saved to **{backup_path}**."
            )
        with suppress(OSError):
            sentinel.unlink()

    st.markdown("### Restore from backup")
    st.caption(
        "Restore code from a timestamped backup created when applying a patch. "
        "Pick a snapshot and click Restore and Restart; the backup is staged to ./update/. "
        "The app will close. Run handoff.bat again to apply the restore "
        "(same as updating)."
    )
    snapshots = _iter_backup_snapshots(app_root)
    if not snapshots:
        st.caption("No backup snapshots found.")
        return

    labels = [_format_snapshot_label(snapshot) for snapshot in snapshots]
    selected = st.selectbox(
        "Backup snapshot",
        range(len(snapshots)),
        format_func=lambda i: labels[i],
        key="settings_restore_snapshot",
    )
    if selected is not None and st.button("Restore and Restart", key="settings_restore_backup"):
        snapshot_path = snapshots[selected]
        try:
            msg = stage_restore_from_snapshot(snapshot_path, app_root=app_root)
        except Exception as exc:
            logger.exception("Failed to stage restore snapshot.")
            st.error(f"Failed to stage restore: {exc}")
        else:
            st.success(msg)
            _schedule_shutdown()
