"""Streamlit UI for in-app updates and backup restore.

This module hosts the interactive panel used on the Settings page to upload and
apply code-only patch zips and to restore timestamped backups created by the
updater core in :mod:`todo_app.updater`.
"""

from __future__ import annotations

from io import BytesIO

import streamlit as st
from loguru import logger

from .updater import (
    _format_snapshot_label,
    _get_app_root,
    _iter_backup_snapshots,
    _restore_backup_snapshot,
    _schedule_shutdown,
    apply_patch_zip,
)


def render_update_panel(current_version: str) -> None:
    """Render an in-app panel for uploading updates and restoring backups."""
    app_root = _get_app_root()

    st.markdown("### App updates")
    st.caption(
        "Upload a code-only patch zip to update the app in-place. "
        "The app will restart automatically after a successful update."
    )

    uploaded = st.file_uploader("Upload update.zip", type="zip", key="update_zip")

    # Persist the uploaded file across reruns (for example after autosave on the
    # main table, which triggers st.rerun()). This ensures the \"Apply and
    # Restart\" button remains available as long as a patch has been selected
    # once in this session.
    stored_bytes_key = "update_zip_bytes"
    stored_name_key = "update_zip_name"

    if uploaded is not None:
        st.session_state[stored_bytes_key] = uploaded.getvalue()
        st.session_state[stored_name_key] = uploaded.name

    file_bytes: bytes | None = st.session_state.get(stored_bytes_key)

    if file_bytes is not None:
        st.caption(f"Current version: {current_version}")
        apply_clicked = st.button(
            "Apply and Restart",
            type="primary",
            key="apply_update_button",
        )

        if apply_clicked:
            logger.info("User requested update apply from Settings UI.")
            with st.spinner("Applying update..."):
                try:
                    message = apply_patch_zip(BytesIO(file_bytes), app_root=app_root)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to apply patch zip: {}", exc)
                    st.error("Update failed. See logs for details.")
                else:
                    # Clear stored patch so the user must explicitly select the
                    # next update they want to apply.
                    for key in (stored_bytes_key, stored_name_key):
                        if key in st.session_state:
                            del st.session_state[key]

                    st.success(message)
                    st.info(
                        "Update applied. The app will close automatically in a moment; "
                        "reopen it to use the new version."
                    )
                    _schedule_shutdown()

    st.divider()
    st.markdown("### Restore from backup")
    st.caption(
        "Before applying a patch, the updater creates a timestamped backup of affected "
        "files under the app's backup directory. You can restore one of those snapshots "
        "here if an update misbehaves."
    )

    snapshots = _iter_backup_snapshots(app_root)
    if not snapshots:
        st.caption(
            "No backups found yet. Backups are created automatically before applying "
            "a code-only patch."
        )
        return

    labels = [_format_snapshot_label(snapshot) for snapshot in snapshots]
    label_to_snapshot = dict(zip(labels, snapshots, strict=False))

    selected_label = st.selectbox(
        "Choose a backup snapshot to restore",
        options=labels,
        key="restore_backup_choice",
    )

    restore_clicked = st.button(
        "Restore selected backup and Restart",
        type="secondary",
        key="restore_backup_button",
        disabled=not selected_label,
    )

    if restore_clicked and selected_label:
        logger.info("User requested backup restore from Settings UI: {}", selected_label)
        with st.spinner("Restoring backup..."):
            try:
                message = _restore_backup_snapshot(
                    label_to_snapshot[selected_label],
                    app_root=app_root,
                )
            except PermissionError as exc:
                logger.exception("Failed to restore backup due to permissions: {}", exc)
                st.error(
                    "Restore failed. The app directory may be read-only. See logs for details."
                )
            except Exception as exc:  # noqa: BLE001
                logger.exception("Failed to restore backup snapshot: {}", exc)
                st.error("Restore failed. See logs for details.")
            else:
                st.success(message)
                st.info(
                    "Backup restored. The app will close automatically in a moment; "
                    "reopen it to use the restored version."
                )
                _schedule_shutdown()

