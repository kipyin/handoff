"""Tests for update_ui module — Streamlit update panel and shutdown helper."""

from __future__ import annotations

import threading
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

from handoff.interfaces.streamlit.update_ui import _schedule_shutdown, render_update_panel


def test_schedule_shutdown_starts_daemon_timer() -> None:
    """_schedule_shutdown creates a daemon timer that will eventually call os._exit."""
    timers_started: list[threading.Timer] = []

    original_init = threading.Timer.__init__

    def track_timer(self, interval, function, *args, **kwargs):
        original_init(self, interval, function, *args, **kwargs)
        timers_started.append(self)

    with (
        patch.object(threading.Timer, "__init__", track_timer),
        patch.object(threading.Timer, "start"),
    ):
        _schedule_shutdown(delay_seconds=99.0)

    assert len(timers_started) == 1
    assert timers_started[0].daemon is True


class TestRenderUpdatePanel:
    """Tests for render_update_panel via Streamlit mocking."""

    def _make_st_mock(self, **overrides) -> MagicMock:
        st = MagicMock()
        st.file_uploader.return_value = None
        st.checkbox.return_value = False
        st.button.return_value = False
        st.selectbox.return_value = 0
        st.session_state = {}
        for k, v in overrides.items():
            setattr(st, k, v)
        return st

    def test_no_patch_uploaded(self, monkeypatch: MagicMock, tmp_path: Path) -> None:
        """When no file is uploaded, basic UI is rendered without errors."""
        st_mock = self._make_st_mock()
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)

        render_update_panel("2026.3.1")

        st_mock.markdown.assert_any_call("### App updates")
        st_mock.markdown.assert_any_call("### Restore from backup")
        st_mock.caption.assert_any_call("No backup snapshots found.")

    def test_patch_uploaded_newer_version(self, monkeypatch, tmp_path: Path) -> None:
        """Uploaded patch with newer version shows version caption and apply button."""
        patch_file = SimpleNamespace(name="patch.zip", seek=lambda _: None)
        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = patch_file
        st_mock.button.return_value = False

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.get_patch_version", lambda f: "2026.4.0"
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._parse_version",
            lambda v: tuple(int(x) for x in v.split(".")),
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._can_apply_patch", lambda pv, av, aa: True
        )

        render_update_panel("2026.3.1")

        st_mock.caption.assert_any_call("Patch version: 2026.4.0")

    def test_patch_uploaded_older_version_shows_warning(self, monkeypatch, tmp_path: Path) -> None:
        """Uploaded patch with older version shows a warning and the override checkbox."""
        patch_file = SimpleNamespace(name="old_patch.zip", seek=lambda _: None)
        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = patch_file
        st_mock.button.return_value = False

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.get_patch_version", lambda f: "2026.2.0"
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._parse_version",
            lambda v: tuple(int(x) for x in v.split(".")),
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._can_apply_patch", lambda pv, av, aa: False
        )

        render_update_panel("2026.3.1")

        st_mock.warning.assert_called_once()
        warning_msg = st_mock.warning.call_args[0][0]
        assert "older" in warning_msg.lower()

    def test_patch_no_version_file(self, monkeypatch, tmp_path: Path) -> None:
        """Uploaded patch without VERSION file shows appropriate caption."""
        patch_file = SimpleNamespace(name="noversion.zip", seek=lambda _: None)
        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = patch_file
        st_mock.button.return_value = False

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.get_patch_version", lambda f: None
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._can_apply_patch", lambda pv, av, aa: True
        )

        render_update_panel("2026.3.1")

        st_mock.caption.assert_any_call("Patch has no VERSION file.")

    def test_apply_button_triggers_staging_and_shutdown(self, monkeypatch, tmp_path: Path) -> None:
        """Clicking Apply triggers stage_patch_with_backup and _schedule_shutdown."""
        patch_file = SimpleNamespace(name="patch.zip", seek=lambda _: None)
        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = patch_file
        st_mock.button.return_value = True

        staged = {"called": False}
        shutdown = {"called": False}

        def mock_stage(f, app_root, app_version, upload_name):
            staged["called"] = True
            return "Update staged."

        def mock_shutdown(delay):
            shutdown["called"] = True

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.get_patch_version", lambda f: "2026.4.0"
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._parse_version",
            lambda v: tuple(int(x) for x in v.split(".")),
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._can_apply_patch", lambda pv, av, aa: True
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.stage_patch_with_backup", mock_stage
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._schedule_shutdown", mock_shutdown
        )

        render_update_panel("2026.3.1")

        assert staged["called"]
        assert shutdown["called"]
        st_mock.success.assert_called_once_with("Update staged.")

    def test_apply_button_staging_error_shows_error_without_shutdown(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """Exceptions from stage_patch_with_backup should not crash or trigger shutdown."""
        patch_file = SimpleNamespace(name="patch.zip", seek=lambda _: None)
        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = patch_file
        st_mock.button.return_value = True

        shutdown = {"called": False}

        def mock_stage(*_args, **_kwargs):
            raise OSError("permission denied")

        def mock_shutdown(*_args):
            shutdown["called"] = True

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.get_patch_version", lambda _f: "2026.4.0"
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._parse_version",
            lambda v: tuple(int(x) for x in v.split(".")),
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._can_apply_patch", lambda _pv, _av, _aa: True
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.stage_patch_with_backup", mock_stage
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._schedule_shutdown", mock_shutdown
        )

        render_update_panel("2026.3.1")

        assert not shutdown["called"]
        st_mock.error.assert_called_once()
        assert "Failed to stage update" in st_mock.error.call_args[0][0]

    def test_sentinel_file_shown_and_removed(self, monkeypatch, tmp_path: Path) -> None:
        """Sentinel file triggers info message and is removed."""
        sentinel = tmp_path / ".last_update_backup"
        sentinel.write_text("backup/20260301-120000", encoding="utf-8")

        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = None

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)

        render_update_panel("2026.3.1")

        st_mock.info.assert_called_once()
        info_msg = st_mock.info.call_args[0][0]
        assert "backup/20260301-120000" in info_msg
        assert not sentinel.exists()

    def test_restore_snapshots_displayed(self, monkeypatch, tmp_path: Path) -> None:
        """When backup snapshots exist, selectbox and restore button are rendered."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        (backup_dir / "20260301-120000").mkdir()

        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = None
        st_mock.selectbox.return_value = 0
        st_mock.button.return_value = False

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)

        render_update_panel("2026.3.1")

        st_mock.selectbox.assert_called_once()

    def test_restore_button_triggers_staging(self, monkeypatch, tmp_path: Path) -> None:
        """Clicking Restore triggers stage_restore_from_snapshot and shutdown."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        snapshot_dir = backup_dir / "20260301-120000"
        snapshot_dir.mkdir()
        (snapshot_dir / "app.py").write_text("old", encoding="utf-8")

        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = None
        st_mock.selectbox.return_value = 0
        st_mock.button.return_value = True

        restored = {"called": False}
        shutdown = {"called": False}

        def mock_restore(snapshot, app_root):
            restored["called"] = True
            return "Restore staged."

        def mock_shutdown(*args):
            shutdown["called"] = True

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.stage_restore_from_snapshot", mock_restore
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._schedule_shutdown", mock_shutdown
        )

        render_update_panel("2026.3.1")

        assert restored["called"]
        assert shutdown["called"]
        st_mock.success.assert_called_with("Restore staged.")

    def test_restore_button_staging_error_shows_error_without_shutdown(
        self,
        monkeypatch,
        tmp_path: Path,
    ) -> None:
        """Exceptions from stage_restore_from_snapshot should not crash or trigger shutdown."""
        backup_dir = tmp_path / "backup"
        backup_dir.mkdir()
        snapshot_dir = backup_dir / "20260301-120000"
        snapshot_dir.mkdir()

        st_mock = self._make_st_mock()
        st_mock.file_uploader.return_value = None
        st_mock.selectbox.return_value = 0
        st_mock.button.return_value = True

        shutdown = {"called": False}

        def mock_restore(*_args, **_kwargs):
            raise OSError("permission denied")

        def mock_shutdown(*_args):
            shutdown["called"] = True

        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.st", st_mock)
        monkeypatch.setattr("handoff.interfaces.streamlit.update_ui.get_app_root", lambda: tmp_path)
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui.stage_restore_from_snapshot", mock_restore
        )
        monkeypatch.setattr(
            "handoff.interfaces.streamlit.update_ui._schedule_shutdown", mock_shutdown
        )

        render_update_panel("2026.3.1")

        assert not shutdown["called"]
        st_mock.error.assert_called_once()
        assert "Failed to stage restore" in st_mock.error.call_args[0][0]
