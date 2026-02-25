"""Build a Windows-only zip distribution with an embedded Python runtime.

Usage:
    uv run python build_zip.py
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import urllib.request
import zipfile
from pathlib import Path

import tomllib


ROOT = Path(__file__).resolve().parent
BUILD_ROOT = ROOT / "build"
DIST_ROOT = ROOT / "dist"
APP_FOLDER_NAME = "todo-app"
APP_BUILD_DIR = BUILD_ROOT / APP_FOLDER_NAME
PYTHON_DIR = APP_BUILD_DIR / "python"

# Keep in sync with pyproject requires-python (>=3.11)
PY_VERSION = "3.11.9"
EMBED_ZIP_NAME = f"python-{PY_VERSION}-embed-amd64.zip"
EMBED_ZIP_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/{EMBED_ZIP_NAME}"
EMBED_ZIP_PATH = BUILD_ROOT / EMBED_ZIP_NAME


def _read_project_metadata() -> tuple[str, str]:
    """Return (name, version) from pyproject.toml."""
    pyproject = ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    name = project.get("name", "todo-app")
    version = project.get("version", "0.0.0")
    return name, version


def _prepare_dirs() -> None:
    if APP_BUILD_DIR.exists():
        shutil.rmtree(APP_BUILD_DIR, ignore_errors=True)
    APP_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)


def _download_embedded_python() -> None:
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    if EMBED_ZIP_PATH.exists():
        return
    print(f"Downloading embedded Python {PY_VERSION} from {EMBED_ZIP_URL}...")
    with urllib.request.urlopen(EMBED_ZIP_URL) as resp, EMBED_ZIP_PATH.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _extract_embedded_python() -> None:
    print("Extracting embedded Python...")
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(EMBED_ZIP_PATH, "r") as zf:
        zf.extractall(PYTHON_DIR)

    # Configure pythonXX._pth so that Lib/site-packages is on sys.path.
    major_minor = "".join(PY_VERSION.split(".")[:2])
    pth_name = f"python{major_minor}._pth"
    pth_path = PYTHON_DIR / pth_name
    if pth_path.exists():
        lines = pth_path.read_text(encoding="utf-8").splitlines()
        # Ensure Lib\site-packages and current dir are listed, and import site is enabled.
        wanted_paths = {"Lib\\site-packages", "."}
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Drop any existing 'import site' to control placement.
            if stripped.startswith("import site"):
                continue
            new_lines.append(line)
        for p in sorted(wanted_paths):
            if p not in [l.strip() for l in new_lines]:
                new_lines.append(p)
        if not any(l.strip().startswith("import site") for l in new_lines):
            new_lines.append("import site")
        pth_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")

    # Ensure Lib/site-packages exists for target installs.
    site_packages = PYTHON_DIR / "Lib" / "site-packages"
    site_packages.mkdir(parents=True, exist_ok=True)


def _install_deps_into_embedded() -> None:
    """Install runtime dependencies into the embedded Python.

    Always use `uv pip` targeting the embedded interpreter so that compiled
    wheels (e.g. numpy) match Python 3.11, regardless of the host Python
    used to run this script.
    """
    site_packages = PYTHON_DIR / "Lib" / "site-packages"
    reqs = ["streamlit>=1.40.0", "sqlmodel>=0.0.22", "loguru>=0.7.0", "platformdirs>=4.0.0"]
    print("Installing dependencies into embedded Python site-packages...")

    uv_cmd = shutil.which("uv")
    if not uv_cmd:
        raise RuntimeError(
            "The 'uv' CLI is required to build the embedded distribution. "
            "Install uv from https://docs.astral.sh/uv/ and retry."
        )

    embedded_python = PYTHON_DIR / "python.exe"

    for req in reqs:
        print(f"  - {req}")
        cmd = [
            uv_cmd,
            "pip",
            "install",
            "--python",
            str(embedded_python),
            req,
            "-t",
            str(site_packages),
        ]
        subprocess.run(cmd, check=True)


def _copy_app_code() -> None:
    print("Copying application code...")
    shutil.copy2(ROOT / "app.py", APP_BUILD_DIR / "app.py")
    src_pkg = ROOT / "src" / "todo_app"
    dst_pkg = APP_BUILD_DIR / "src" / "todo_app"
    if dst_pkg.exists():
        shutil.rmtree(dst_pkg)
    shutil.copytree(src_pkg, dst_pkg)


def _write_run_bat() -> None:
    print("Writing run.bat launcher...")
    content = textwrap.dedent(
        r"""
        @echo off
        setlocal

        set SCRIPT_DIR=%~dp0
        cd /d "%SCRIPT_DIR%"

        set PYTHONHOME=%SCRIPT_DIR%python
        set PYTHONPATH=%SCRIPT_DIR%;%SCRIPT_DIR%src

        "%SCRIPT_DIR%python\python.exe" -m streamlit run app.py
        endlocal
        """
    ).lstrip()
    (APP_BUILD_DIR / "run.bat").write_text(content, encoding="utf-8")


def _make_zip(name: str, version: str) -> Path:
    zip_name = f"{name}-{version}-windows-embed.zip"
    dist_path = DIST_ROOT / zip_name
    if dist_path.exists():
        dist_path.unlink()
    print(f"Creating zip at {dist_path}...")
    with zipfile.ZipFile(dist_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in APP_BUILD_DIR.rglob("*"):
            if path.is_file():
                rel_path = path.relative_to(BUILD_ROOT)
                zf.write(path, rel_path)
    return dist_path


def main() -> None:
    name, version = _read_project_metadata()
    print(f"Building {name} {version} (Windows embedded Python zip)...")
    _prepare_dirs()
    _download_embedded_python()
    _extract_embedded_python()
    _install_deps_into_embedded()
    _copy_app_code()
    _write_run_bat()
    out_zip = _make_zip(name, version)
    print()
    print("Build complete.")
    print(f"Zip file: {out_zip}")
    print("To run:")
    print("  1. Extract the zip.")
    print("  2. Open the extracted folder.")
    print("  3. Double-click run.bat.")
    print("Your SQLite database will be stored in your user data directory (e.g. %APPDATA%\\todo-app\\todo.db).")


if __name__ == "__main__":
    main()

