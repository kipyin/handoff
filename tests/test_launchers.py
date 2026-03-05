import os
import subprocess
import sys
import shutil
from pathlib import Path
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
        
        # Create dummy python environment
        python_dir = app_dir / "python"
        python_dir.mkdir()
        
        # Copy current python executable and its DLLs to act as the embedded one.
        # This is needed so the launchers can successfully execute "%SCRIPT_DIR%python\python.exe"
        py_exe = Path(sys.executable)
        shutil.copy(py_exe, python_dir / "python.exe")
        for dll in py_exe.parent.glob("*.dll"):
            shutil.copy(dll, python_dir)
        
        # Create a dummy handoff module so -m handoff works.
        # The launchers add the app root to PYTHONPATH.
        (app_dir / "handoff.py").write_text("print('MOCK_APP_STARTED')", encoding="utf-8")
        
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
            check=True
        )
        
        # 4. Assertions
        assert "Applying update..." in result.stdout
        assert "Update applied." in result.stdout
        assert "MOCK_APP_STARTED" in result.stdout
        
        # Verify file was moved
        moved_file = mock_app_env / "patch_test.txt"
        assert moved_file.exists()
        assert moved_file.read_text(encoding="utf-8") == "patched content"
        
        # Verify update dir was removed
        assert not update_dir.exists()

    def test_handoff_ps1_logic(self, mock_app_env):
        """Verify handoff.ps1 applies updates and launches the app."""
        # 1. Generate the launcher
        build_zip._write_handoff_ps1()
        ps1_path = mock_app_env / "handoff.ps1"
        assert ps1_path.exists()
        
        # 2. Setup update folder with a file
        update_dir = mock_app_env / "update"
        update_dir.mkdir()
        patch_file = update_dir / "patch_test.txt"
        patch_file.write_text("patched content", encoding="utf-8")
        
        # 3. Run the PowerShell script
        # We call powershell.exe explicitly
        result = subprocess.run(
            ["powershell", "-ExecutionPolicy", "Bypass", "-File", str(ps1_path)],
            cwd=mock_app_env,
            capture_output=True,
            text=True,
            check=True
        )
        
        # 4. Assertions
        assert "Applying update..." in result.stdout
        assert "Update applied." in result.stdout
        assert "MOCK_APP_STARTED" in result.stdout
        
        # Verify file was moved
        moved_file = mock_app_env / "patch_test.txt"
        assert moved_file.exists()
        assert moved_file.read_text(encoding="utf-8") == "patched content"
        
        # Verify update dir was removed
        assert not update_dir.exists()
