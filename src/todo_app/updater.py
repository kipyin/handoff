"""In-app update panel and patch application helpers."""

from __future__ import annotations

from datetime import datetime
from pathlib import Path
from typing import BinaryIO
import shutil
import zipfile

import streamlit as st
from loguru import logger


ALLOWED_PREFIXES = ("app.py", "src/", "pages/")


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

    if target_version:
        logger.info("Applied patch to update app to version {}", target_version)
        return f"Update applied. Target version: {target_version}."
    logger.info("Applied patch without explicit VERSION marker.")
    return "Update applied."


def render_update_panel(current_version: str) -> None:
    """Render a sidebar panel for uploading and applying patch zips."""
    app_root = _get_app_root()
    with st.sidebar.expander("Update app"):
        st.caption(f"Current version: {current_version}")
        uploaded = st.file_uploader("Upload update.zip", type="zip", key="update_zip")
        if not uploaded:
            return

        if st.button("Apply update", type="primary", key="apply_update_button"):
            with st.spinner("Applying update..."):
                try:
                    message = apply_patch_zip(uploaded, app_root=app_root)
                except Exception as exc:  # noqa: BLE001
                    logger.exception("Failed to apply patch zip: {}", exc)
                    st.error("Update failed. See logs for details.")
                else:
                    st.success(message)
                    st.info("Please close and reopen the app to use the updated version.")
