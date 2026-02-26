"""Build a small code-only patch zip for the app.

The resulting archive contains application code and a VERSION marker, suitable
for applying on top of either a development checkout or an embedded zip build.
"""

from __future__ import annotations

import argparse
import zipfile
from pathlib import Path

from todo_app.version import __version__

from . import ROOT

DIST_ROOT = ROOT / "dist"


def _iter_files(include_pages: bool) -> list[Path]:
    """Return the list of files to include in the patch."""
    items: list[Path] = []

    app_py = ROOT / "app.py"
    if app_py.exists():
        items.append(app_py)

    src_root = ROOT / "src" / "todo_app"
    if src_root.exists():
        items.extend(path for path in src_root.rglob("*") if path.is_file())

    if include_pages:
        pages_root = ROOT / "pages"
        if pages_root.exists():
            items.extend(path for path in pages_root.rglob("*") if path.is_file())

    return items


def build_patch(*, include_pages: bool = True) -> Path:
    """Build a code-only patch zip and return its path."""
    DIST_ROOT.mkdir(parents=True, exist_ok=True)
    zip_name = f"todo-app-{__version__}-patch.zip"
    zip_path = DIST_ROOT / zip_name

    if zip_path.exists():
        zip_path.unlink()

    files = _iter_files(include_pages=include_pages)
    with zipfile.ZipFile(zip_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        # Write a VERSION marker so the updater can display target version.
        zf.writestr("VERSION", __version__)

        for path in files:
            rel_path = path.relative_to(ROOT)
            zf.write(path, rel_path.as_posix())

    return zip_path


def main() -> None:
    """CLI entrypoint for building a patch zip."""
    parser = argparse.ArgumentParser(description="Build a code-only patch zip for the app.")
    parser.add_argument(
        "--skip-pages",
        action="store_true",
        help="Exclude the pages/ directory from the patch.",
    )
    args = parser.parse_args()

    include_pages = not args.skip_pages
    path = build_patch(include_pages=include_pages)
    print(f"Created patch zip at {path}")


if __name__ == "__main__":
    main()
