"""Additional tests for pages/system_settings.py to improve coverage.

Covers: _render_send_log_section, _render_about_section, import happy path.
"""

from __future__ import annotations

import json
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import MagicMock

from handoff.pages.system_settings import (
    _render_about_section,
    _render_data_export_section,
    _render_data_import_section,
    _render_send_log_section,
)


def _patch_streamlit(monkeypatch, **st_overrides) -> MagicMock:
    st_mock = MagicMock()
    st_mock.file_uploader.return_value = None
    st_mock.checkbox.return_value = False
    st_mock.button.return_value = False
    st_mock.download_button.return_value = None
    st_mock.session_state = {}
    for k, v in st_overrides.items():
        setattr(st_mock, k, v)
    monkeypatch.setattr("handoff.pages.system_settings.st", st_mock)
    return st_mock


class TestRenderSendLogSection:
    def test_no_log_files(self, monkeypatch, tmp_path: Path) -> None:
        """When no log files exist, shows 'No log files found' caption."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        monkeypatch.setattr("handoff.pages.system_settings._get_logs_dir", lambda: logs_dir)
        st_mock = _patch_streamlit(monkeypatch)

        _render_send_log_section()

        st_mock.caption.assert_any_call("No log files found.")

    def test_log_files_exist_creates_download(self, monkeypatch, tmp_path: Path) -> None:
        """When log files exist, a download button with zip is rendered."""
        logs_dir = tmp_path / "logs"
        logs_dir.mkdir()
        (logs_dir / "handoff.log").write_text("log content", encoding="utf-8")
        monkeypatch.setattr("handoff.pages.system_settings._get_logs_dir", lambda: logs_dir)
        st_mock = _patch_streamlit(monkeypatch)

        _render_send_log_section()

        st_mock.download_button.assert_called_once()
        call_kwargs = st_mock.download_button.call_args
        assert "log" in call_kwargs[1].get(
            "file_name", call_kwargs[0][0] if call_kwargs[0] else ""
        ).lower() or "log" in str(call_kwargs)


class TestRenderAboutSection:
    def test_renders_version_and_environment(self, monkeypatch) -> None:
        """About section shows version and environment info."""
        st_mock = _patch_streamlit(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_readme_intro", lambda: "Handoff helps you."
        )

        _render_about_section()

        st_mock.markdown.assert_any_call("### About Handoff")
        st_mock.write.assert_called_once_with("Handoff helps you.")
        # Should show Python version caption
        caption_calls = [str(c) for c in st_mock.caption.call_args_list]
        assert any("Python" in c for c in caption_calls)


class TestRenderDataExportSection:
    def test_renders_download_buttons(self, monkeypatch) -> None:
        """Export section creates JSON and CSV download buttons."""
        st_mock = _patch_streamlit(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_export_payload",
            lambda: {"projects": [], "handoffs": [], "check_ins": []},
        )

        _render_data_export_section()

        assert st_mock.download_button.call_count == 2

    def test_csv_download_uses_handoff_rows(self, monkeypatch) -> None:
        """CSV export should include current handoff rows instead of legacy todos."""
        st_mock = _patch_streamlit(monkeypatch)
        monkeypatch.setattr(
            "handoff.pages.system_settings.get_export_payload",
            lambda: {
                "projects": [],
                "handoffs": [
                    {
                        "id": 7,
                        "project_id": 3,
                        "need_back": "Launch checklist",
                        "pitchman": "Alex",
                        "next_check": "2026-03-12",
                        "deadline": "2026-03-14",
                        "notes": "Ship after QA",
                        "created_at": "2026-03-10T09:00:00",
                    }
                ],
                "check_ins": [],
            },
        )

        _render_data_export_section()

        csv_call = None
        for call in st_mock.download_button.call_args_list:
            if call.args and call.args[0] == "Download CSV (handoffs)":
                csv_call = call
                break
        assert csv_call is not None, "CSV download button call not found"
        assert csv_call.args[0] == "Download CSV (handoffs)"
        assert csv_call.kwargs["file_name"] == "handoff_handoffs.csv"
        assert "need_back" in csv_call.kwargs["data"]
        assert "Launch checklist" in csv_call.kwargs["data"]


class TestRenderDataImportSection:
    def test_valid_import_with_confirm_and_apply(self, monkeypatch) -> None:
        """Full import happy path: valid JSON, confirm checked, apply clicked."""
        payload = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "T",
                    "status": "handoff",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }
        uploaded = SimpleNamespace(getvalue=lambda: json.dumps(payload).encode("utf-8"))
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.file_uploader.return_value = uploaded
        st_mock.checkbox.return_value = True
        st_mock.button.return_value = True

        imported = {"called": False}

        def mock_import(p):
            imported["called"] = True

        monkeypatch.setattr("handoff.pages.system_settings.import_payload", mock_import)

        _render_data_import_section()

        assert imported["called"]
        st_mock.success.assert_called_once()

    def test_import_exception_shows_error(self, monkeypatch) -> None:
        """When import_payload raises, error message is shown."""
        payload = {
            "projects": [{"id": 1, "name": "P", "created_at": "2026-01-01T00:00:00"}],
            "todos": [
                {
                    "id": 1,
                    "project_id": 1,
                    "name": "T",
                    "status": "handoff",
                    "created_at": "2026-01-01T00:00:00",
                }
            ],
        }
        uploaded = SimpleNamespace(getvalue=lambda: json.dumps(payload).encode("utf-8"))
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.file_uploader.return_value = uploaded
        st_mock.checkbox.return_value = True
        st_mock.button.return_value = True

        monkeypatch.setattr(
            "handoff.pages.system_settings.import_payload",
            lambda p: (_ for _ in ()).throw(RuntimeError("DB broke")),
        )

        _render_data_import_section()

        st_mock.error.assert_called_once()
        assert "DB broke" in st_mock.error.call_args[0][0]

    def test_no_upload_returns_early(self, monkeypatch) -> None:
        """When nothing is uploaded, no validation runs."""
        st_mock = _patch_streamlit(monkeypatch)
        st_mock.file_uploader.return_value = None

        _render_data_import_section()

        st_mock.error.assert_not_called()
        st_mock.info.assert_not_called()
