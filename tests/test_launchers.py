import os
import subprocess

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

        # Create a tiny mock python.exe using PowerShell/C#.
        # This avoids "failed to locate pyvenv.cfg" and other Python startup issues
        # while verifying that the launcher correctly sets env vars and calls the exe.
        exe_path = python_dir / "python.exe"
        c_code = (
            "using System; "
            "class P { "
            "  static void Main() { "
            '    Console.WriteLine("MOCK_APP_STARTED"); '
            '    Console.WriteLine("ENV_PYTHONPATH=" + '
            'Environment.GetEnvironmentVariable("PYTHONPATH")); '
            '    Console.WriteLine("ENV_PYTHONHOME=" + '
            'Environment.GetEnvironmentVariable("PYTHONHOME")); '
            "  } "
            "}"
        )
        # Compile the C# code into a real EXE using built-in Windows tools
        subprocess.run(
            [
                "powershell",
                "-Command",
                (
                    f"Add-Type -TypeDefinition '{c_code}' "
                    f"-OutputAssembly '{exe_path}' "
                    "-OutputType ConsoleApplication"
                ),
            ],
            check=True,
        )

        # Create src dir (expected by PYTHONPATH in the scripts)
        (app_dir / "src").mkdir()

        return app_dir

    def test_handoff_bat_logic(self, mock_app_env):
        """Verify handoff.bat applies updates and launches the app."""
        # 1. Generate the launcher
        build_zip._write_handoff_bat()
        bat_path = mock_app_env / "handoff.bat"
        assert bat_path.exists()

        # 2. Setup update folder with a file
        update_dir = mock_app_env / "update"
        update_dir.mkdir()
        patch_file = update_dir / "patch_test.txt"
        patch_file.write_text("patched content", encoding="utf-8")

        # 3. Run the batch file
        # shell=True is needed to execute .bat files on Windows
        result = subprocess.run(
            [str(bat_path)],
            cwd=mock_app_env,
            capture_output=True,
            text=True,
            shell=True,
            check=True,
        )

        # 4. Assertions
        assert "Applying update..." in result.stdout
        assert "Update applied." in result.stdout
        assert "MOCK_APP_STARTED" in result.stdout

        # Verify environment variables were set correctly by the launcher
        assert "ENV_PYTHONPATH=" in result.stdout
        assert str(mock_app_env) in result.stdout
        assert str(mock_app_env / "src") in result.stdout
        assert "ENV_PYTHONHOME=" in result.stdout
        assert str(mock_app_env / "python") in result.stdout

        # Verify file was moved
        moved_file = mock_app_env / "patch_test.txt"
        assert moved_file.exists()
        assert moved_file.read_text(encoding="utf-8") == "patched content"

        # Verify update dir was removed
        assert not (mock_app_env / "update").exists()
