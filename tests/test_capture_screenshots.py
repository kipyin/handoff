"""Tests for screenshot capture automation for README documentation."""

from __future__ import annotations

import contextlib
import subprocess
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from typer.testing import CliRunner

import scripts.capture_screenshots as capture_screenshots_module
import scripts.dev_cli as dev_cli

RUNNER = CliRunner()


class TestWaitForServer:
    """Tests for _wait_for_server timeout and retry logic."""

    def test_wait_for_server_succeeds_on_first_attempt(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_wait_for_server returns immediately when health endpoint is ready."""
        mock_response = MagicMock()
        mock_response.status = 200
        mock_response.__enter__ = MagicMock(return_value=mock_response)
        mock_response.__exit__ = MagicMock(return_value=None)

        monkeypatch.setattr("urllib.request.urlopen", lambda *_args, **_kwargs: mock_response)

        # Should complete without raising
        capture_screenshots_module._wait_for_server()

    def test_wait_for_server_retries_on_connection_errors(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_wait_for_server retries after connection errors (OSError)."""
        attempt_count = [0]

        def fake_urlopen_with_response(*_args, **_kwargs):
            attempt_count[0] += 1
            if attempt_count[0] < 3:
                raise OSError("Connection refused")
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen_with_response)
        monkeypatch.setattr("time.sleep", lambda _: None)  # Mock sleep to speed up test

        capture_screenshots_module._wait_for_server()

        assert attempt_count[0] >= 3

    def test_wait_for_server_raises_timeout_after_max_attempts(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_wait_for_server raises RuntimeError when max attempts exceeded."""

        def fake_urlopen(*_args, **_kwargs):
            raise OSError("Connection refused")

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda _: None)

        with pytest.raises(RuntimeError) as exc_info:
            capture_screenshots_module._wait_for_server()

        assert "did not become ready" in str(exc_info.value)
        assert "8599" in str(exc_info.value)

    def test_wait_for_server_respects_timeout_parameter(
        self, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """_wait_for_server passes timeout to urlopen."""
        call_args = []

        def fake_urlopen_with_response(*args, **kwargs):
            call_args.append((args, kwargs))
            if len(call_args) == 1:
                raise OSError("Connection refused")
            mock_response = MagicMock()
            mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen_with_response)
        monkeypatch.setattr("time.sleep", lambda _: None)

        capture_screenshots_module._wait_for_server()

        # Verify that timeout was passed to urlopen
        assert any("timeout" in kwargs for _args, kwargs in call_args)

    def test_wait_for_server_checks_status_200(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """_wait_for_server only succeeds on HTTP 200 status."""
        attempt_count = [0]

        def fake_urlopen(*_args, **_kwargs):
            attempt_count[0] += 1
            mock_response = MagicMock()
            if attempt_count[0] == 1:
                mock_response.status = 503  # Service unavailable
            else:
                mock_response.status = 200
            mock_response.__enter__ = MagicMock(return_value=mock_response)
            mock_response.__exit__ = MagicMock(return_value=None)
            return mock_response

        monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)
        monkeypatch.setattr("time.sleep", lambda _: None)

        capture_screenshots_module._wait_for_server()

        assert attempt_count[0] >= 2


class TestCaptureScreenshotsMain:
    """Integration tests for capture_screenshots.main() orchestration."""

    def test_main_creates_output_directory(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() creates OUTPUT_DIR if it doesn't exist."""
        output_dir = tmp_path / "docs" / "screenshots"
        temp_db = tmp_path / "build" / "test.db"

        monkeypatch.setattr(capture_screenshots_module, "OUTPUT_DIR", output_dir)
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        def fake_subprocess_popen(*_args, **_kwargs):
            mock_proc = MagicMock()
            mock_proc.terminate = MagicMock()
            mock_proc.wait = MagicMock(return_value=0)
            return mock_proc

        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr("subprocess.Popen", fake_subprocess_popen)
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr(
            "scripts.capture_screenshots.sync_playwright", MagicMock(side_effect=KeyboardInterrupt)
        )

        with contextlib.suppress(KeyboardInterrupt):
            capture_screenshots_module.main()

        assert output_dir.exists()

    def test_main_seeds_demo_database(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() calls seed_demo_db with force=True."""
        temp_db = tmp_path / "test.db"
        seed_calls = []

        def fake_seed(db, *, force):
            seed_calls.append({"db": db, "force": force})
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr(
            "subprocess.Popen",
            MagicMock(
                return_value=MagicMock(terminate=MagicMock(), wait=MagicMock(return_value=0))
            ),
        )
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr(
            "scripts.capture_screenshots.sync_playwright", MagicMock(side_effect=KeyboardInterrupt)
        )

        with contextlib.suppress(KeyboardInterrupt):
            capture_screenshots_module.main()

        assert seed_calls == [{"db": temp_db, "force": True}]

    def test_main_launches_streamlit_with_correct_env(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() launches Streamlit with HANDOFF_DB_PATH and STREAMLIT_SERVER_HEADLESS."""
        temp_db = tmp_path / "test.db"
        popen_calls = []

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        def fake_popen(*args, **kwargs):
            popen_calls.append({"args": args, "kwargs": kwargs})
            mock_proc = MagicMock()
            mock_proc.terminate = MagicMock()
            mock_proc.wait = MagicMock(return_value=0)
            return mock_proc

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr(
            "scripts.capture_screenshots.sync_playwright", MagicMock(side_effect=KeyboardInterrupt)
        )

        with contextlib.suppress(KeyboardInterrupt):
            capture_screenshots_module.main()

        assert len(popen_calls) == 1
        kwargs = popen_calls[0]["kwargs"]
        assert kwargs["env"]["HANDOFF_DB_PATH"] == str(temp_db.resolve())
        assert kwargs["env"]["STREAMLIT_SERVER_HEADLESS"] == "true"

    def test_main_terminates_subprocess_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() calls proc.terminate() and proc.wait() after screenshots."""
        temp_db = tmp_path / "test.db"

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        mock_proc = MagicMock()

        def fake_popen(*_args, **_kwargs):
            return mock_proc

        def fake_playwright():
            raise RuntimeError("Test early exit")

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr("scripts.capture_screenshots.sync_playwright", fake_playwright)

        with pytest.raises(RuntimeError):
            capture_screenshots_module.main()

        mock_proc.terminate.assert_called_once()
        mock_proc.wait.assert_called()

    def test_main_kills_process_if_wait_timeout(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() kills process if terminate doesn't work within timeout."""
        temp_db = tmp_path / "test.db"

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        mock_proc = MagicMock()
        # First wait() times out, then second wait() succeeds
        mock_proc.wait.side_effect = [subprocess.TimeoutExpired("cmd", 10), None]

        def fake_popen(*_args, **_kwargs):
            return mock_proc

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr("subprocess.Popen", fake_popen)
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr(
            "scripts.capture_screenshots.sync_playwright",
            MagicMock(side_effect=RuntimeError("exit")),
        )

        with pytest.raises(RuntimeError):
            capture_screenshots_module.main()

        mock_proc.kill.assert_called_once()

    def test_main_deletes_temp_db_on_success(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() deletes TEMP_DB after completion."""
        temp_db = tmp_path / "test.db"

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr(
            "subprocess.Popen",
            MagicMock(
                return_value=MagicMock(terminate=MagicMock(), wait=MagicMock(return_value=0))
            ),
        )
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr(
            "scripts.capture_screenshots.sync_playwright",
            MagicMock(side_effect=RuntimeError("exit")),
        )

        with pytest.raises(RuntimeError):
            capture_screenshots_module.main()

        assert not temp_db.exists()

    def test_main_deletes_temp_db_on_error(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() deletes TEMP_DB even when an exception occurs."""
        temp_db = tmp_path / "test.db"

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr("subprocess.Popen", MagicMock(side_effect=RuntimeError("boom")))

        with pytest.raises(RuntimeError):
            capture_screenshots_module.main()

        assert not temp_db.exists()

    def test_main_handles_missing_playwright_browser(
        self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """main() handles missing Playwright browser gracefully."""
        temp_db = tmp_path / "test.db"

        def fake_seed(db, *, force):
            db.parent.mkdir(parents=True, exist_ok=True)
            db.write_text("seed")

        class FakePlaywright:
            def __enter__(self):
                self.chromium = MagicMock()
                self.chromium.launch.side_effect = Exception("Executable doesn't exist")
                return self

            def __exit__(self, *_):
                pass

        monkeypatch.setattr(
            capture_screenshots_module, "OUTPUT_DIR", tmp_path / "docs" / "screenshots"
        )
        monkeypatch.setattr(capture_screenshots_module, "TEMP_DB", temp_db)
        monkeypatch.setattr("scripts.capture_screenshots.seed_demo_module.seed_demo_db", fake_seed)
        monkeypatch.setattr(
            "subprocess.Popen",
            MagicMock(
                return_value=MagicMock(terminate=MagicMock(), wait=MagicMock(return_value=0))
            ),
        )
        monkeypatch.setattr("scripts.capture_screenshots._wait_for_server", MagicMock())
        monkeypatch.setattr("scripts.capture_screenshots.sync_playwright", FakePlaywright)

        with pytest.raises(SystemExit):
            capture_screenshots_module.main()

        assert not temp_db.exists()


class TestCaptureScreenshotsCommand:
    """Tests for capture-screenshots dev CLI command."""

    def test_capture_screenshots_cli_command_exists(self) -> None:
        """capture-screenshots command is registered in dev CLI."""
        result = RUNNER.invoke(dev_cli.app, ["capture-screenshots", "--help"])

        assert result.exit_code == 0
        assert "README screenshots" in result.stdout or "Capture" in result.stdout

    def test_capture_screenshots_cli_invokes_main(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """capture-screenshots command delegates to capture_screenshots_module.main()."""
        calls = []

        def fake_main():
            calls.append("main_called")

        monkeypatch.setattr(capture_screenshots_module, "main", fake_main)

        result = RUNNER.invoke(dev_cli.app, ["capture-screenshots"])

        assert result.exit_code == 0
        assert calls == ["main_called"]
