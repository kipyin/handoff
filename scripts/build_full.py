"""Build a distributable archive with an embedded/standalone Python runtime.

Supports Windows (embedded Python zip) and macOS (python-build-standalone).
Intended to be used via the Typer CLI:

    uv run handoff build --full              # Windows (default)
    uv run handoff build --full --platform mac   # macOS
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tarfile
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

PBS_VERSION = "20250317"


def _mac_archive_name() -> str:
    """Return the python-build-standalone archive name for the current macOS architecture."""
    import platform as _platform

    machine = _platform.machine()
    arch = "aarch64" if machine == "arm64" else "x86_64"
    return f"cpython-{PY_VERSION}+{PBS_VERSION}-{arch}-apple-darwin-install_only_stripped.tar.gz"


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


def _run_pyarmor_gen(pyarmor_cmd: list[str], *, cwd: Path) -> None:
    """Run a PyArmor command and replay captured output to the console."""
    try:
        result = subprocess.run(
            pyarmor_cmd,
            check=True,
            cwd=cwd,
            capture_output=True,
            text=True,
        )
    except subprocess.CalledProcessError as exc:
        if exc.stdout:
            print(exc.stdout, end="")
        if exc.stderr:
            print(exc.stderr, end="")
        raise

    if result.stdout:
        print(result.stdout, end="")
    if result.stderr:
        print(result.stderr, end="")


def _is_pyarmor_out_of_license(exc: subprocess.CalledProcessError) -> bool:
    """Return True if PyArmor failed because of a license error."""
    combined = "\n".join(
        part for part in (exc.output, exc.stdout, exc.stderr) if isinstance(part, str) and part
    )
    return "out of license" in combined.lower()


def _obfuscate_app_code_with_pyarmor(*, dry_run: bool = False) -> None:
    """Obfuscate the application package in the build directory using PyArmor.

    This runs PyArmor against a copied source tree under SRC_PLAIN_DIR and
    writes obfuscated modules and the runtime package under APP_BUILD_DIR/src.
    When dry_run is True, copies plain source to src/ instead (no PyArmor).
    """
    if not SRC_PLAIN_DIR.exists():
        raise RuntimeError(
            f"Expected plain sources in {SRC_PLAIN_DIR} before obfuscation; "
            "did you run _copy_app_code()?"
        )

    obf_root = APP_BUILD_DIR / "src"
    if obf_root.exists():
        shutil.rmtree(obf_root, ignore_errors=True)

    if dry_run:
        print("Dry run: copying plain source to src/ (skipping PyArmor)...")
        shutil.copytree(SRC_PLAIN_DIR / "handoff", obf_root / "handoff")
        return

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
        _run_pyarmor_gen(pyarmor_cmd, cwd=SRC_PLAIN_DIR)
    except subprocess.CalledProcessError as exc:  # noqa: TRY002
        if _is_pyarmor_out_of_license(exc):
            raise RuntimeError(
                "PyArmor reported 'out of license'. All source modules must stay under "
                "32KB so they can be obfuscated with the trial license. "
                "Run `uv run handoff sizecheck` to find oversized files."
            ) from exc
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
    zip_root = f"{name}-{version}"
    with zipfile.ZipFile(dist_path, "w", compression=zipfile.ZIP_DEFLATED) as zf:
        for path in APP_BUILD_DIR.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel_path = path.relative_to(APP_BUILD_DIR)
                zf.write(path, Path(zip_root) / rel_path)
    return dist_path


# ---------------------------------------------------------------------------
# macOS-specific helpers
# ---------------------------------------------------------------------------


def _download_standalone_python_mac() -> None:
    """Download a python-build-standalone macOS release if not already cached."""
    BUILD_ROOT.mkdir(parents=True, exist_ok=True)
    archive_name = _mac_archive_name()
    archive_path = BUILD_ROOT / archive_name
    if archive_path.exists():
        return
    url = f"https://github.com/astral-sh/python-build-standalone/releases/download/{PBS_VERSION}/{archive_name}"
    print(f"Downloading standalone Python {PY_VERSION} for macOS from {url}...")
    with urllib.request.urlopen(url) as resp, archive_path.open("wb") as f:
        shutil.copyfileobj(resp, f)


def _extract_standalone_python_mac() -> None:
    """Extract the standalone Python tarball into the build directory."""
    print("Extracting standalone Python for macOS...")
    PYTHON_DIR.mkdir(parents=True, exist_ok=True)
    archive_path = BUILD_ROOT / _mac_archive_name()
    with tarfile.open(archive_path, "r:gz") as tf:
        tf.extractall(PYTHON_DIR, filter="data")

    extracted = PYTHON_DIR / "python"
    if extracted.exists() and extracted.is_dir():
        for child in extracted.iterdir():
            child.rename(PYTHON_DIR / child.name)
        extracted.rmdir()


def _install_deps_into_mac_python() -> None:
    """Install runtime dependencies into the standalone macOS Python."""
    site_packages = (
        PYTHON_DIR
        / "lib"
        / f"python{sys.version_info.major}.{sys.version_info.minor}"
        / "site-packages"
    )
    site_packages.mkdir(parents=True, exist_ok=True)
    print("Installing dependencies into standalone macOS Python...")

    uv_cmd = shutil.which("uv")
    if not uv_cmd:
        raise RuntimeError(
            "The 'uv' CLI is required to build the distribution. "
            "Install uv from https://docs.astral.sh/uv/ and retry."
        )

    python_bin = PYTHON_DIR / "bin" / f"python{sys.version_info.major}.{sys.version_info.minor}"
    if not python_bin.exists():
        python_bin = PYTHON_DIR / "bin" / "python3"

    reqs = _get_runtime_deps()
    for req in reqs:
        print(f"  - {req}")

    cmd = [
        uv_cmd,
        "pip",
        "install",
        "--python",
        str(python_bin),
        "-t",
        str(site_packages),
        "--link-mode=copy",
        *reqs,
    ]
    subprocess.run(cmd, check=True)


def _write_handoff_sh() -> None:
    """Write a handoff.sh launcher for macOS."""
    print("Writing handoff.sh launcher...")
    content = textwrap.dedent("""\
        #!/usr/bin/env bash
        set -euo pipefail

        SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
        cd "$SCRIPT_DIR"

        export PYTHONHOME="$SCRIPT_DIR/python"
        export PYTHONPATH="$SCRIPT_DIR:$SCRIPT_DIR/src"

        if [ -d "$SCRIPT_DIR/update" ] && [ "$(ls -A "$SCRIPT_DIR/update")" ]; then
            echo "Applying update..."
            cp -R "$SCRIPT_DIR/update/"* "$SCRIPT_DIR/"
            rm -rf "$SCRIPT_DIR/update"
            echo "Update applied."
        fi

        PYVER_MAJOR=%d
        PYVER_MINOR=%d
        PYTHON_BIN="$SCRIPT_DIR/python/bin/python${PYVER_MAJOR}.${PYVER_MINOR}"
        if [ ! -x "$PYTHON_BIN" ]; then
            PYTHON_BIN="$SCRIPT_DIR/python/bin/python3"
        fi

        exec "$PYTHON_BIN" -m handoff "$@"
    """) % (sys.version_info.major, sys.version_info.minor)
    launcher = APP_BUILD_DIR / "handoff.sh"
    launcher.write_text(content, encoding="utf-8")
    launcher.chmod(0o755)


def _make_tar_gz(name: str, version: str) -> Path:
    """Create a .tar.gz archive for the macOS distribution."""
    tar_name = f"{name}-{version}-macos.tar.gz"
    dist_path = DIST_ROOT / tar_name
    if dist_path.exists():
        dist_path.unlink()
    print(f"Creating tar.gz at {dist_path}...")
    tar_root = f"{name}-{version}"
    with tarfile.open(dist_path, "w:gz") as tf:
        for path in APP_BUILD_DIR.rglob("*"):
            if path.is_file() and "__pycache__" not in path.parts:
                rel_path = path.relative_to(APP_BUILD_DIR)
                arcname = str(Path(tar_root) / rel_path)
                info = tf.gettarinfo(str(path), arcname=arcname)
                if path.name == "handoff.sh" or path.suffix == "" and "bin" in path.parts:
                    info.mode = 0o755
                with open(path, "rb") as fobj:
                    tf.addfile(info, fobj)
    return dist_path


def main(*, platform: str = "windows", dry_run: bool = False) -> None:
    """Build the full embedded/standalone distribution for the app.

    Args:
        platform: Target platform — ``"windows"`` or ``"mac"``.
        dry_run: If True, run copy/docs/launcher steps only; skip download,
            extract, deps install, obfuscation, and archive creation.
    """
    name, version = _read_project_metadata()

    global APP_BUILD_DIR, SRC_PLAIN_DIR, PYTHON_DIR
    APP_BUILD_DIR = BUILD_ROOT / f"{name}-{version}"
    SRC_PLAIN_DIR = APP_BUILD_DIR / "src_plain"
    PYTHON_DIR = APP_BUILD_DIR / "python"

    if dry_run:
        print(f"Dry run: building {name} {version} ({platform})...")
        _prepare_dirs()
        _copy_app_code()
        _copy_docs()
        _obfuscate_app_code_with_pyarmor(dry_run=True)
        if platform == "mac":
            _write_handoff_sh()
        else:
            _write_handoff_bat()
        print()
        print("Dry run complete. Skipped: download, extract, deps install, archive.")
        return

    if platform == "mac":
        print(f"Building {name} {version} (macOS standalone Python tar.gz)...")
        _prepare_dirs()
        _download_standalone_python_mac()
        _extract_standalone_python_mac()
        _install_deps_into_mac_python()
        _copy_app_code()
        _copy_docs()
        _obfuscate_app_code_with_pyarmor()
        _write_handoff_sh()
        out = _make_tar_gz(name, version)
        print()
        print("Build complete.")
        print(f"Archive: {out}")
        print("To run:")
        print("  1. Extract the archive: tar xzf " + out.name)
        print(f"  2. cd {name}-{version}")
        print("  3. ./handoff.sh")
    else:
        print(f"Building {name} {version} (Windows embedded Python zip)...")
        _prepare_dirs()
        _download_embedded_python()
        _extract_embedded_python()
        _install_deps_into_embedded()
        _copy_app_code()
        _copy_docs()
        _obfuscate_app_code_with_pyarmor()
        _write_handoff_bat()
        out = _make_zip(name, version)
        print()
        print("Build complete.")
        print(f"Zip file: {out}")
        print("To run:")
        print("  1. Extract the zip.")
        print("  2. Open the extracted folder.")
        print("  3. Double-click handoff.bat.")

    print(
        "Your SQLite database will be stored in your user data directory "
        "(e.g. ~/Library/Application Support/handoff/todo.db on macOS "
        "or %APPDATA%\\handoff\\todo.db on Windows)."
    )


if __name__ == "__main__":
    main()
