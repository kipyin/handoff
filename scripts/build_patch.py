"""Build a code-only patch zip from the obfuscated build output.

Use this after build-zip to produce a patch that can be applied by the
in-app updater on PyArmor-obfuscated distributions. The patch contains
obfuscated src/handoff, the PyArmor runtime, and optionally app.py
and pages/ from the last build.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from handoff.version import __version__

from . import ROOT

BUILD_APP_DIR = ROOT / "build" / "handoff"
DIST_ROOT = ROOT / "dist"


def build_patch(*, include_pages: bool = True) -> Path:
    """Build a patch zip from the obfuscated build tree and return its path.

    Requires that build-zip has been run so that build/handoff
    contains app.py, src/handoff (obfuscated), and
    src/pyarmor_runtime_*.

    Args:
        include_pages: If True, include the root-level pages/ directory
            when present in the build (build_zip does not copy pages by default,
            so this is only relevant if you add pages to the build dir).

    Returns:
        Path to the created patch zip under dist/.

    Raises:
        RuntimeError: If the build directory is missing or lacks obfuscated code.

    """
    if not BUILD_APP_DIR.is_dir():
        raise RuntimeError(
            f"Obfuscated build not found at {BUILD_APP_DIR}. Run 'uv run handoff build-zip' first."
        )

    src_dir = BUILD_APP_DIR / "src"
    handoff_dir = src_dir / "handoff"
    if not handoff_dir.is_dir():
        raise RuntimeError(
            f"Expected obfuscated package at {handoff_dir}. "
            "Run 'uv run handoff build-zip' to produce an obfuscated build."
        )

    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    zip_name = f"handoff-{__version__}-patch.zip"
    zip_path = DIST_ROOT / zip_name

    if zip_path.exists():
        zip_path.unlink()

    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        zf.writestr("VERSION", __version__)

        # Include top-level documentation in the patch.
        for filename in ("README.md", "RELEASE_NOTES.md"):
            doc = ROOT / filename
            if doc.is_file():
                zf.write(doc, filename)

        app_py = BUILD_APP_DIR / "app.py"
        if app_py.is_file():
            zf.write(app_py, "app.py")

        for path in src_dir.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel = path.relative_to(BUILD_APP_DIR)
                zf.write(path, rel.as_posix())

        if include_pages:
            pages_dir = ROOT / "pages"
            if pages_dir.is_dir():
                for path in pages_dir.rglob("*"):
                    if path.is_file():
                        rel = path.relative_to(ROOT)
                        zf.write(path, rel.as_posix())

    return zip_path
