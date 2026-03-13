"""Regression tests for the handoff.core package export contract."""

from __future__ import annotations

import importlib
from datetime import date

import handoff.core as core
from handoff.core import handoff_lifecycle, models


def test_core_package_reexports_models_and_lifecycle_helpers() -> None:
    """handoff.core re-exports the expected shared domain API."""
    assert core.CheckInType is models.CheckInType
    assert core.Project is models.Project
    assert core.Handoff is models.Handoff
    assert core.CheckIn is models.CheckIn
    assert core.handoff_is_open is handoff_lifecycle.handoff_is_open
    assert core.handoff_is_closed is handoff_lifecycle.handoff_is_closed
    assert core.get_handoff_close_date is handoff_lifecycle.get_handoff_close_date
    assert set(core.__all__) == {
        "CheckIn",
        "CheckInType",
        "Handoff",
        "Project",
        "get_handoff_close_date",
        "handoff_is_closed",
        "handoff_is_open",
    }


def test_core_package_exports_drive_lifecycle_logic() -> None:
    """Lifecycle helpers from handoff.core work end-to-end with re-exported models."""
    handoff = core.Handoff(project_id=1, need_back="Follow up")
    handoff.check_ins = [
        core.CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 10),
            check_in_type=core.CheckInType.ON_TRACK,
        ),
        core.CheckIn(
            handoff_id=1,
            check_in_date=date(2026, 3, 12),
            check_in_type=core.CheckInType.CONCLUDED,
        ),
    ]

    assert core.handoff_is_open(handoff) is False
    assert core.handoff_is_closed(handoff) is True
    assert core.get_handoff_close_date(handoff) == date(2026, 3, 12)


def test_core_package_reload_keeps_model_identity() -> None:
    """Reloading handoff.core keeps model identities stable for callers."""
    before_project = core.Project
    before_handoff = core.Handoff
    reloaded = importlib.reload(core)

    assert reloaded.Project is before_project
    assert reloaded.Handoff is before_handoff
