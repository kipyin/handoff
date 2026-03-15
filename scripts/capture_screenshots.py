"""Capture screenshots for README documentation.

Seeds a temp DB, starts Streamlit, navigates to Now/Projects/Dashboard pages,
and saves PNGs to docs/screenshots/.
"""

from __future__ import annotations

import os
import subprocess
import sys
import time
import urllib.request

from playwright.sync_api import sync_playwright

from . import ROOT
from . import seed_demo as seed_demo_module

OUTPUT_DIR = ROOT / "docs" / "screenshots"
TEMP_DB = ROOT / "build" / "screenshot_capture.db"
CAPTURE_PORT = 8599  # Use a dedicated port to avoid capturing an existing app on 8501
BASE_URL = f"http://localhost:{CAPTURE_PORT}"
HEALTH_URL = f"{BASE_URL}/_stcore/health"
MAX_WAIT_ATTEMPTS = 30
WAIT_INTERVAL = 0.5
SCREENSHOT_DELAY = 1.0  # Seconds to wait for Streamlit to finish rendering before capture


def _wait_for_server() -> None:
    """Poll the Streamlit health endpoint until the server is ready."""
    for _ in range(MAX_WAIT_ATTEMPTS):
        try:
            with urllib.request.urlopen(HEALTH_URL, timeout=2) as resp:
                if resp.status == 200:
                    return
        except OSError:
            pass
        time.sleep(WAIT_INTERVAL)
    raise RuntimeError(
        f"Streamlit server did not become ready at {BASE_URL} within "
        f"{MAX_WAIT_ATTEMPTS * WAIT_INTERVAL}s"
    )


def main() -> None:
    """Capture Now, Projects, and Dashboard screenshots to docs/screenshots/."""
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    TEMP_DB.parent.mkdir(parents=True, exist_ok=True)
    db_path_resolved = str(TEMP_DB.resolve())

    try:
        seed_demo_module.seed_demo_db(TEMP_DB, force=True)

        import handoff.interfaces.streamlit.runtime_config  # noqa: F401

        env = {**os.environ, "HANDOFF_DB_PATH": db_path_resolved}
        env["STREAMLIT_SERVER_HEADLESS"] = "true"

        proc = subprocess.Popen(
            [
                sys.executable,
                "-m",
                "streamlit",
                "run",
                "app.py",
                "--server.port",
                str(CAPTURE_PORT),
            ],
            cwd=str(ROOT),
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        try:
            _wait_for_server()

            with sync_playwright() as p:
                try:
                    browser = p.chromium.launch(headless=True)
                except Exception as e:
                    if "Executable doesn't exist" in str(e):
                        raise SystemExit(
                            "Playwright browsers not installed. Run:\n"
                            "  uv run playwright install chromium"
                        ) from e
                    raise
                page = browser.new_page(viewport={"width": 1280, "height": 720})
                page.goto(BASE_URL, wait_until="networkidle")
                time.sleep(SCREENSHOT_DELAY)

                # Expand the second handoff to show the check-in trail
                expanders = page.locator("[data-testid='stExpander']")
                if expanders.count() >= 2:
                    second = expanders.nth(1).locator("summary").first
                    second.scroll_into_view_if_needed()
                    second.click(force=True)
                    time.sleep(0.5)

                page.screenshot(path=OUTPUT_DIR / "now-page.png")

                # Dashboard is in the main nav group
                page.get_by_role("link", name="Dashboard").click()
                page.wait_for_load_state("networkidle")
                time.sleep(SCREENSHOT_DELAY)
                page.screenshot(path=OUTPUT_DIR / "dashboard.png")

                # Projects is under Settings; click Settings to expand, then Projects
                page.get_by_text("Settings", exact=True).click()
                page.get_by_role("link", name="Projects").click()
                page.wait_for_load_state("networkidle")
                time.sleep(SCREENSHOT_DELAY)
                page.screenshot(path=OUTPUT_DIR / "projects-page.png")

                browser.close()
        finally:
            proc.terminate()
            try:
                proc.wait(timeout=10)
            except subprocess.TimeoutExpired:
                proc.kill()
                proc.wait()
    finally:
        if TEMP_DB.exists():
            TEMP_DB.unlink()
