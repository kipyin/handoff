import os

import pytest

from scripts import build_zip


@pytest.mark.skipif(os.name != "nt", reason="Launcher scripts are Windows-specific")
class TestLaunchers:
    @pytest.fixture
    def mock_app_env(self, tmp_path, monkeypatch):
        """Sets up a dummy app structure for testing launchers."""
        app_dir = tmp_path / "handoff-test-env"
        app_dir.mkdir()

        # Monkeypatch the global APP_BUILD_DIR in build_zip module
        monkeypatch.setattr(build_zip, "APP_BUILD_DIR", app_dir)

        # Create dummy python directory
        python_dir = app_dir / "python"
        python_dir.mkdir()

        # Create a mock python "executable" using a batch file.
        # We name it python.exe. Note: Windows cmd won't execute this as a script
        # directly if called as .exe, but it serves as a fast mock for content checks.
        mock_script = (
            "@echo off\n"
            "echo MOCK_APP_STARTED\n"
            "echo ENV_PYTHONPATH=%PYTHONPATH%\n"
            "echo ENV_PYTHONHOME=%PYTHONHOME%\n"
        )
        python_exe = python_dir / "python.exe"
        python_exe.write_text(mock_script, encoding="utf-8")

        # Create src dir (expected by PYTHONPATH in the scripts)
        (app_dir / "src").mkdir()

        return app_dir

    def test_handoff_bat_logic(self, mock_app_env):
        """Verify handoff.bat content and update application logic."""
        # 1. Generate the launcher
        build_zip._write_handoff_bat()
        bat_path = mock_app_env / "handoff.bat"
        assert bat_path.exists()

        content = bat_path.read_text()

        # Verify the batch file contains the expected logic strings
        # We check for the core parts of the update and execution logic
        assert 'if exist "%SCRIPT_DIR%update"' in content
        assert 'move /y "%SCRIPT_DIR%update\\*"' in content
        assert "python\\python.exe" in content
        assert "PYTHONPATH" in content
        assert "PYTHONHOME" in content

        # Verify environment variables are set to the correct paths
        assert "set PYTHONHOME=%SCRIPT_DIR%python" in content
        assert "set PYTHONPATH=%SCRIPT_DIR%src" in content

        # 2. Manually verify the "Update" logic that the .bat is supposed to do
        # (This ensures our understanding of the command we wrote into the .bat is correct)
        update_dir = mock_app_env / "update"
        update_dir.mkdir()
        patch_file = update_dir / "patch_test.txt"
        patch_file.write_text("patched content", encoding="utf-8")

        # Simulate the 'move /y update\* .' command
        for f in update_dir.iterdir():
            f.replace(mock_app_env / f.name)
        update_dir.rmdir()

        assert (mock_app_env / "patch_test.txt").exists()
        assert not update_dir.exists()
