"""Runtime health tests: verify the app starts and runs without errors.

These tests spawn the actual Streamlit process (uv run handoff), monitor stdout/stderr
for error patterns, and optionally use AppTest to programmatically interact with
the UI. The subprocess never exits on its own, so we run it for a fixed duration
and check that no Traceback/Error appears in the output.
"""

from __future__ import annotations

import re
import subprocess
import sys
import threading
import time
from pathlib import Path

WORKSPACE = Path(__file__).resolve().parents[1]
APP_PY = WORKSPACE / "app.py"

# Patterns that indicate startup or runtime failure.
ERROR_PATTERNS = [
    re.compile(r"Traceback\s*\(most recent call last\)", re.IGNORECASE),
    re.compile(r"Error:\s*.+", re.IGNORECASE),
    re.compile(r"ModuleNotFoundError|ImportError:", re.IGNORECASE),
    re.compile(r"streamlit\.exceptions\.StreamlitAPIException", re.IGNORECASE),
]

# Pattern indicating successful startup (Streamlit prints this when ready).
READY_PATTERN = re.compile(r"You can now view your Streamlit app", re.IGNORECASE)


def _run_app_subprocess(
    *,
    db_path: Path,
    duration_seconds: float = 10.0,
    extra_wait_after_ready: float = 3.0,
) -> tuple[str, str, bool, bool]:
    """Run the Streamlit app as a subprocess and monitor stdout/stderr.

    Returns:
        (stdout, stderr, saw_ready, has_errors)
    """
    env = {
        **__import__("os").environ,
        "HANDOFF_DB_PATH": str(db_path),
        "STREAMLIT_SERVER_HEADLESS": "true",
    }

    cmd = [
        sys.executable,
        "-m",
        "streamlit",
        "run",
        str(APP_PY),
        "--server.headless",
        "true",
    ]

    proc = subprocess.Popen(
        cmd,
        cwd=str(WORKSPACE),
        env=env,
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        bufsize=1,
    )

    output_lines: list[str] = []
    saw_ready = False
    has_errors = False

    def read_output() -> None:
        nonlocal saw_ready, has_errors
        if proc.stdout is None:
            return
        for line in proc.stdout:
            output_lines.append(line)
            if READY_PATTERN.search(line):
                saw_ready = True
            for pat in ERROR_PATTERNS:
                if pat.search(line):
                    has_errors = True
                    break

    reader = threading.Thread(target=read_output, daemon=True)
    reader.start()

    try:
        # Wait for READY or duration, whichever comes first.
        elapsed = 0.0
        poll_interval = 0.2
        while elapsed < duration_seconds:
            proc.poll()
            if proc.returncode is not None:
                break
            if saw_ready:
                # Give extra time for any delayed errors (e.g. first request handling).
                time.sleep(extra_wait_after_ready)
                break
            time.sleep(poll_interval)
            elapsed += poll_interval
    finally:
        proc.terminate()
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()

    # Allow reader to finish reading any remaining output.
    reader.join(timeout=2)

    full_output = "".join(output_lines)
    return full_output, "", saw_ready, has_errors


def test_app_starts_without_errors_and_reports_ready(
    tmp_path: Path,
) -> None:
    """Run uv run handoff in a subprocess and verify no errors in stdout/stderr.

    The Streamlit process does not exit on its own. We run it for ~10 seconds,
    monitor output for Traceback/Error patterns, and assert we see the
    'You can now view your Streamlit app' ready message with no errors.
    """
    db_path = tmp_path / "health_check.db"
    stdout, _stderr, saw_ready, has_errors = _run_app_subprocess(
        db_path=db_path,
        duration_seconds=12.0,
        extra_wait_after_ready=3.0,
    )

    assert saw_ready, (
        "Expected Streamlit ready message in output. "
        "App may have failed to start. Output:\n" + stdout[-3000:]
    )
    assert not has_errors, "Found error patterns (Traceback, Error, etc.) in app output:\n" + stdout
