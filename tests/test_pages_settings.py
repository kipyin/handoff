"""Tests for Settings page helpers."""

from __future__ import annotations

import json
from types import SimpleNamespace
from unittest.mock import MagicMock

from handoff.pages.settings import _render_data_import_section


def _patch_streamlit(monkeypatch, uploaded) -> MagicMock:
    """Replace the Streamlit module in the settings page with a mock."""
    st_mock = MagicMock()
    st_mock.file_uploader.return_value = uploaded
    st_mock.checkbox.return_value = False
    st_mock.button.return_value = False
    monkeypatch.setattr("handoff.pages.settings.st", st_mock)
    return st_mock


def test_render_data_import_section_rejects_non_utf8(monkeypatch) -> None:
    """Invalid byte content shows a clear UTF-8 error."""
    uploaded = SimpleNamespace(getvalue=lambda: b"\xff")
    st_mock = _patch_streamlit(monkeypatch, uploaded)

    _render_data_import_section()

    st_mock.error.assert_called_once_with(
        "Could not read the file as UTF-8 text. Please upload a JSON backup."
    )


def test_render_data_import_section_rejects_invalid_json(monkeypatch) -> None:
    """Malformed JSON shows a clean parse error."""
    uploaded = SimpleNamespace(getvalue=lambda: b"{not json")
    st_mock = _patch_streamlit(monkeypatch, uploaded)

    _render_data_import_section()

    st_mock.error.assert_called_once_with("Invalid JSON file. Please upload a Handoff JSON backup.")


def test_render_data_import_section_rejects_invalid_backup_shape(monkeypatch) -> None:
    """Unexpected JSON structure shows a clean validation error."""
    uploaded = SimpleNamespace(getvalue=lambda: json.dumps({"projects": []}).encode("utf-8"))
    st_mock = _patch_streamlit(monkeypatch, uploaded)

    _render_data_import_section()

    st_mock.error.assert_called_once_with(
        "Invalid backup file. Expected a Handoff backup with 'projects' and 'todos' lists."
    )
