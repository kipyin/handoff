"""Build an experimental Windows handoff.exe launcher with PyInstaller.

This helper is intentionally minimal and aimed at exploration. It does not
replace the existing embedded-zip build, which remains the primary Windows
distribution path via scripts.build_zip.
"""

from __future__ import annotations

import shutil
import subprocess

from . import ROOT


def main() -> None:
    """Build an experimental handoff.exe via PyInstaller."""
    pyinstaller_exe = shutil.which("pyinstaller")
    if not pyinstaller_exe:
        raise RuntimeError(
            "PyInstaller CLI not found on PATH. "
            "Install it into the dev environment (for example with "
            "`uv add --group dev pyinstaller`) and retry."
        )

    launcher_src = ROOT / "src" / "handoff" / "__main__.py"
    if not launcher_src.is_file():
        raise RuntimeError(f"Expected launcher at {launcher_src} but it was not found.")

    dist_dir = ROOT / "dist"
    build_dir = ROOT / "build" / "pyinstaller"
    dist_dir.mkdir(parents=True, exist_ok=True)
    build_dir.mkdir(parents=True, exist_ok=True)

    cmd = [
        pyinstaller_exe,
        "--name",
        "handoff",
        "--onefile",
        "--console",
        "--distpath",
        str(dist_dir),
        "--workpath",
        str(build_dir),
        str(launcher_src),
    ]

    print("Building experimental handoff.exe with PyInstaller...")
    subprocess.run(cmd, check=True, cwd=ROOT)
    exe_path = dist_dir / "handoff.exe"
    if exe_path.is_file():
        print(f"handoff.exe created at {exe_path}")
    else:
        print(f"PyInstaller completed, but {exe_path} was not found. Check PyInstaller output.")
