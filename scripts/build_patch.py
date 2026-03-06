"""Build a code-only patch zip from the obfuscated build output.

Regenerates obfuscated code from current source (same steps as build-zip for
app code and PyArmor), then packages app.py, src/, and docs into the patch zip.
Use the resulting patch with the in-app updater on PyArmor-obfuscated distributions.
"""

from __future__ import annotations

import zipfile
from pathlib import Path

from handoff.version import __version__

from . import ROOT

BUILD_APP_DIR = ROOT / "build" / "handoff"
DIST_ROOT = ROOT / "dist"


def build_patch(*, include_pages: bool = True) -> Path:
    """Build a patch zip from current source by regenerating obfuscated code.

    Copies app code into build/handoff, runs PyArmor to produce obfuscated
    src/handoff and runtime, copies docs, then zips app.py, src/, and
    optionally pages/ into the patch. No prior build-zip run is required.

    Args:
        include_pages: If True, include the root-level pages/ directory
            when present (build_full does not copy pages by default).

    Returns:
        Path to the created patch zip under dist/.

    Raises:
        RuntimeError: If PyArmor or source copy fails.

    """
    from . import build_full

    BUILD_APP_DIR.mkdir(parents=True, exist_ok=True)
    build_full._copy_app_code()
    build_full._obfuscate_app_code_with_pyarmor()
    build_full._copy_docs()

    src_dir = BUILD_APP_DIR / "src"
    handoff_dir = src_dir / "handoff"
    if not handoff_dir.is_dir():
        raise RuntimeError(
            f"Obfuscation did not produce package at {handoff_dir}. "
            "Check PyArmor installation and source tree."
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
