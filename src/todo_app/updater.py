"""In-app update panel and patch application helpers.

Patches for PyArmor-obfuscated distributions must be built with
``uv run todo build-obfuscated-patch`` (from the obfuscated build output);
``build-patch`` produces source-only patches for dev or non-obfuscated installs.
"""

import os
import shutil
import threading
import zipfile
from datetime import datetime
from io import BytesIO
from pathlib import Path
from typing import BinaryIO

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


def render_update_panel(current_version: str) -> None:
    """Render a sidebar panel for uploading and applying patch zips."""
    app_root = _get_app_root()
    with st.sidebar.expander("Update app"):
        st.caption(f"Current version: {current_version}")

        uploaded = st.file_uploader("Upload update.zip", type="zip", key="update_zip")

        # Persist the uploaded file across reruns (for example after clicking
        # "Save changes" on the main table, which triggers st.rerun()). This
        # ensures the "Apply and Restart" button remains available as long as a
        # patch has been selected once in this session.
        stored_bytes_key = "update_zip_bytes"
        stored_name_key = "update_zip_name"

        if uploaded is not None:
            st.session_state[stored_bytes_key] = uploaded.getvalue()
            st.session_state[stored_name_key] = uploaded.name

        file_bytes: bytes | None = st.session_state.get(stored_bytes_key)

        if file_bytes is None:
            # No patch selected yet; show only the uploader.
            return

        has_unsaved_todos = bool(st.session_state.get("main_has_unsaved_changes", False))
        if has_unsaved_todos:
            st.warning(
                "You have unsaved changes on the Todos table. "
                "Please click **Save changes** there before applying an update."
            )

        apply_clicked = st.button(
            "Apply and Restart",
            type="primary",
            key="apply_update_button",
            disabled=has_unsaved_todos,
        )

        if apply_clicked:
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
