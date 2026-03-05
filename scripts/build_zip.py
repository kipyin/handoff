"""Build a Windows-only zip with an embedded Python runtime.

This script is the moved version of the original `build_zip.py` and is
intended to be used via the Typer CLI:

    uv run python -m scripts.cli build-zip
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import textwrap
import tomllib
import urllib.request
import zipfile
from pathlib import Path

from . import ROOT

BUILD_ROOT = ROOT / "build"
DIST_ROOT = ROOT / "dist"
APP_FOLDER_NAME = "handoff"
APP_BUILD_DIR = BUILD_ROOT / APP_FOLDER_NAME
SRC_PLAIN_DIR = APP_BUILD_DIR / "src_plain"
PYTHON_DIR = APP_BUILD_DIR / "python"

PY_VERSION = f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}"
EMBED_ZIP_NAME = f"python-{PY_VERSION}-embed-amd64.zip"
EMBED_ZIP_URL = f"https://www.python.org/ftp/python/{PY_VERSION}/{EMBED_ZIP_NAME}"
EMBED_ZIP_PATH = BUILD_ROOT / EMBED_ZIP_NAME


def _read_project_metadata() -> tuple[str, str]:
    """Return (name, version) from pyproject.toml.

    Returns:
        Tuple of (project name, project version) from [project] section.

    """
    pyproject = ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    name = project.get("name", "handoff")
    version = project.get("version", "0.0.0")
    return name, version


def _get_runtime_deps() -> list[str]:
    """Return the list of runtime dependencies from pyproject.toml.

    Reads `[project.dependencies]` so the embedded environment matches the
    main application's runtime requirements.

    Returns:
        List of dependency specifier strings.

    """
    pyproject = ROOT / "pyproject.toml"
    with pyproject.open("rb") as f:
        data = tomllib.load(f)
    project = data.get("project", {})
    deps = project.get("dependencies", []) or []
    return list(deps)


def _prepare_dirs() -> None:
    """Create a clean build directory and ensure dist directory exists.

    Removes the existing application build directory under `build/` and then
    recreates it, along with the `dist/` output directory.
    """
    if APP_BUILD_DIR.exists():
        shutil.rmtree(APP_BUILD_DIR, ignore_errors=True)
    APP_BUILD_DIR.mkdir(parents=True, exist_ok=True)
    DIST_ROOT.mkdir(parents=True, exist_ok=True)


def _download_embedded_python() -> None:
    """Download the embedded Python zip for the configured version if missing.

    The archive is cached under `build/` so subsequent runs reuse it unless
    it is manually deleted.
    """
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    if EMBED_ZIP_PATH.exists():
        return
    print(f"Downloading embedded Python {PY_VERSION} from {EMBED_ZIP_URL}...")
    with urllib.request.urlopen(EMBED_ZIP_URL) as resp, EMBED_ZIP_PATH.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _configure_pth_file() -> None:
    """Configure `pythonXX._pth` so Lib/site-packages and current dir are on sys.path."""
    major_minor = "".join(PY_VERSION.split(".")[:2])
    pth_name = f"python{major_minor}._pth"
    pth_path = PYTHON_DIR / pth_name
    if pth_path.exists():
        lines = pth_path.read_text(encoding="utf-8").splitlines()
        # Include app root and src so `import handoff` resolves from bundled source.
        # In embedded Python mode, `PYTHONPATH` is ignored when a `pythonXX._pth`
        # file is present, and relative entries are resolved from the `python/`
        # directory (where this file lives), not from the current working dir.
        wanted_paths = {"Lib\\site-packages", ".", "..", "..\\src"}
        new_lines: list[str] = []
        for line in lines:
            stripped = line.strip()
            # Drop any existing 'import site' to control placement.
            if stripped.startswith("import site"):
                continue
            new_lines.append(line)
        for path_entry in sorted(wanted_paths):
            if path_entry not in [existing_line.strip() for existing_line in new_lines]:
                new_lines.append(path_entry)
        if not any(existing_line.strip().startswith("import site") for existing_line in new_lines):
            new_lines.append("import site")
        pth_path.write_text("\n".join(new_lines) + "\n", encoding="utf-8")


def _extract_embedded_python() -> None:
    """Extract the embedded Python zip and ensure site-packages is usable.

    Unpacks the embedded distribution into `PYTHON_DIR`, adjusts the
    `pythonXX._pth` file to allow imports from `Lib/site-packages`, and
    ensures the `Lib/site-packages` directory exists for dependency installs.
    """
    print("Extracting embedded Python...")
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(EMBED_ZIP_PATH, "r") as zf:
        zf.extractall(PYTHON_DIR)

    _configure_pth_file()

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
    print("Installing dependencies into embedded Python site-packages...")

    uv_cmd = shutil.which("uv")
    if not uv_cmd:
        raise RuntimeError(
            "The 'uv' CLI is required to build the embedded distribution. "
            "Install uv from https://docs.astral.sh/uv/ and retry."
        )

    embedded_python = PYTHON_DIR / "python.exe"
    reqs = _get_runtime_deps()
    for req in reqs:
        print(f"  - {req}")

    cmd = [
        uv_cmd,
        "pip",
        "install",
        "--python",
        str(embedded_python),
        "-t",
        str(site_packages),
        "--link-mode=copy",
        *reqs,
    ]  # noqa: E501
    subprocess.run(cmd, check=True)


def _copy_app_code() -> None:
    """Copy application entrypoint and package into the build directory.

    Any existing copy under the build directory is removed first. The removal
    ignores errors to tolerate transient Windows file locks (for example on
    `__pycache__`), mirroring a `Remove-Item -Recurse -Force` style cleanup.
    """
    print("Copying application code...")
    shutil.copy2(ROOT / "app.py", APP_BUILD_DIR / "app.py")
    src_pkg = ROOT / "src" / "handoff"
    if SRC_PLAIN_DIR.exists():
        shutil.rmtree(SRC_PLAIN_DIR, ignore_errors=True)
    SRC_PLAIN_DIR.mkdir(parents=True, exist_ok=True)
    dst_pkg = SRC_PLAIN_DIR / "handoff"
    shutil.copytree(src_pkg, dst_pkg, dirs_exist_ok=True)


def _copy_docs() -> None:
    """Copy top-level documentation files into the build directory.

    Includes README and release notes so they ship with the embedded
    distribution zip.
    """
    print("Copying documentation files...")
    for filename in ("README.md", "RELEASE_NOTES.md"):
        src = ROOT / filename
        if src.exists():
            shutil.copy2(src, APP_BUILD_DIR / filename)


def _obfuscate_app_code_with_pyarmor() -> None:
    """Obfuscate the application package in the build directory using PyArmor.

    This runs PyArmor against a copied source tree under SRC_PLAIN_DIR and
    writes obfuscated modules and the runtime package under APP_BUILD_DIR/src.
    """
    if not SRC_PLAIN_DIR.exists():
        raise RuntimeError(
            f"Expected plain sources in {SRC_PLAIN_DIR} before obfuscation; "
            "did you run _copy_app_code()?"
        )

    obf_root = APP_BUILD_DIR / "src"
    if obf_root.exists():
        shutil.rmtree(obf_root, ignore_errors=True)

    pyarmor_exe = shutil.which("pyarmor")
    if not pyarmor_exe:
        raise RuntimeError(
            "PyArmor CLI not found on PATH. Install with: uv sync (dev group includes pyarmor)."
        )
    pyarmor_cmd = [
        pyarmor_exe,
        "gen",
        "-r",
        "-O",
        str(obf_root),
        "handoff",
    ]

    print("Obfuscating application code with PyArmor...")
    try:
        subprocess.run(pyarmor_cmd, check=True, cwd=SRC_PLAIN_DIR)
    except subprocess.CalledProcessError as exc:  # noqa: TRY002
        raise RuntimeError(
            "PyArmor failed while obfuscating application code. "
            "Ensure PyArmor >=9.2.0 is installed in the development environment."
        ) from exc

    # Remove the plain sources so only obfuscated code is shipped.
    shutil.rmtree(SRC_PLAIN_DIR, ignore_errors=True)


def _write_handoff_bat() -> None:
    """Write a handoff.bat launcher that starts the Streamlit app.

    If ./update exists and has files, copies them into the app root using xcopy
    (no Python), then removes ./update. This avoids WinError 32 when overwriting
    PyArmor runtime .pyd files that would be locked if Python were running.
    """
    print("Writing handoff.bat launcher...")
    content = textwrap.dedent(
        r"""
        @echo off
        setlocal

        set SCRIPT_DIR=%~dp0
        cd /d "%SCRIPT_DIR%"

        set PYTHONHOME=%SCRIPT_DIR%python
        set PYTHONPATH=%SCRIPT_DIR%;%SCRIPT_DIR%src

        if exist "%SCRIPT_DIR%update\*" (
            echo Applying update...
            xcopy /E /Y "%SCRIPT_DIR%update\*" "%SCRIPT_DIR%" >nul
            rmdir /s /q "%SCRIPT_DIR%update" 2>nul
            echo Update applied.
        )

        "%SCRIPT_DIR%python\python.exe" -m handoff
        endlocal
        """
    ).lstrip()
    (APP_BUILD_DIR / "handoff.bat").write_text(content, encoding="utf-8")


def _make_zip(name: str, version: str) -> Path:
    """Create the final zip archive under `dist/` and return its path.

    Args:
        name: Application name from `pyproject.toml`.
        version: Application version from `pyproject.toml`.

    """
    zip_name = f"{name}-{version}-windows-embed.zip"
    dist_path = DIST_ROOT / zip_name
    if dist_path.exists():
        dist_path.unlink()
    print(f"Creating zip at {dist_path}...")
    with zipfile.ZipFile(dist_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in APP_BUILD_DIR.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel_path = path.relative_to(BUILD_ROOT)
                zf.write(path, rel_path)
    return dist_path


def main() -> None:
    """Build the full Windows embedded zip distribution for the app."""
    name, version = _read_project_metadata()

    # Update build directory to include version
    global APP_BUILD_DIR, SRC_PLAIN_DIR, PYTHON_DIR
    APP_BUILD_DIR = BUILD_ROOT / f"{name}-{version}"
    SRC_PLAIN_DIR = APP_BUILD_DIR / "src_plain"
    PYTHON_DIR = APP_BUILD_DIR / "python"

    print(f"Building {name} {version} (Windows embedded Python zip)...")
    _prepare_dirs()
    _download_embedded_python()
    _extract_embedded_python()
    _install_deps_into_embedded()
    _copy_app_code()
    _copy_docs()
    _obfuscate_app_code_with_pyarmor()
    _write_handoff_bat()
    out_zip = _make_zip(name, version)
    print()
    print("Build complete.")
    print(f"Zip file: {out_zip}")
    print("To run:")
    print("  1. Extract the zip.")
    print("  2. Open the extracted folder.")
    print("  3. Double-click handoff.bat.")
    print(
        "Your SQLite database will be stored in your user data directory "
        "(e.g. %APPDATA%\\handoff\\todo.db)."
    )


if __name__ == "__main__":
    main()
