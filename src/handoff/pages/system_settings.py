"""System Settings page implementation for Handoff.

This page centralises app updates, code backup restore, data export, log
download, and a compact About section so that operational controls live in
one place.
"""

from __future__ import annotations

import io
import json
import platform
import zipfile
from datetime import datetime
from typing import Any

import pandas as pd
import streamlit as st
from loguru import logger

from handoff.backup_schema import BackupPayload
from handoff.docs import get_readme_intro
from handoff.logging import _get_logs_dir
from handoff.models import CheckInType
from handoff.rulebook import (
    DeadlineWithinDaysCondition,
    LatestCheckInTypeIsCondition,
    NextCheckDueCondition,
    RulebookSettings,
    RuleCondition,
    RuleDefinition,
    is_built_in_rule,
)
from handoff.services.handoff_service import get_rulebook_section_preview_counts
from handoff.services.settings_service import (
    DEADLINE_NEAR_DAYS_MAX,
    get_export_payload,
    get_rulebook_settings,
    import_payload,
    reset_rulebook_settings,
    save_rulebook_settings,
)
from handoff.update_ui import render_update_panel
from handoff.version import __version__ as APP_VERSION

CSV_HANDOFF_COLUMNS = [
    "id",
    "project_id",
    "need_back",
    "pitchman",
    "next_check",
    "deadline",
    "notes",
    "created_at",
]


def _handoffs_csv_text(payload: dict[str, Any]) -> str:
    """Return a CSV export for the current handoff payload shape."""
    handoffs = payload.get("handoffs", [])
    if not handoffs:
        return ",".join(CSV_HANDOFF_COLUMNS) + "\n"

    frame = pd.DataFrame(handoffs)
    for column in CSV_HANDOFF_COLUMNS:
        if column not in frame.columns:
            frame[column] = None
    return frame[CSV_HANDOFF_COLUMNS].to_csv(index=False)


def _format_condition(condition: RuleCondition) -> str:
    """Return a human-readable description of a rule condition.

    Args:
        condition: The rule condition to format.

    Returns:
        A short description of the condition (e.g., "Deadline within 3 day(s)").
    """
    if isinstance(condition, DeadlineWithinDaysCondition):
        return f"Deadline within {condition.days} day(s)"
    if isinstance(condition, LatestCheckInTypeIsCondition):
        label = condition.check_in_type.value.replace("_", " ")
        return f"Latest check-in is {label}"
    if isinstance(condition, NextCheckDueCondition):
        if condition.include_missing_next_check:
            return "Next check due or missing"
        return "Next check due"
    return "Unknown condition"


def _clear_rulebook_widget_state() -> None:
    """Remove rulebook widget keys from session state so form reloads from disk."""
    to_drop = [
        k
        for k in st.session_state
        if k.startswith("settings_rule_") or k.startswith("settings_add_")
    ]
    for k in to_drop:
        del st.session_state[k]


RESERVED_SECTION_ID = "upcoming"


def _slugify_section_id(name: str) -> str:
    """Derive a section_id from a display name.

    Lowercases, replaces spaces and hyphens with underscores. Reserves
    "upcoming" by prefixing with "custom_". Returns "custom_section" if empty.
    """
    slug = name.strip().lower().replace(" ", "_").replace("-", "_") or "custom_section"
    if slug == RESERVED_SECTION_ID:
        return f"custom_{slug}"
    return slug


def _next_unique_custom_rule_id(settings: RulebookSettings, section_id: str) -> str:
    """Generate a unique rule_id for a new custom section rule.

    Uses the pattern `custom_{section_id}` or `custom_{section_id}_{n}` if
    that ID already exists in the rulebook.

    Args:
        settings: The current rulebook settings.
        section_id: The target section_id for the new rule.

    Returns:
        A unique rule_id that is not yet in the rulebook.
    """
    base = f"custom_{section_id}"
    existing = {r.rule_id for r in settings.rules}
    if base not in existing:
        return base
    idx = 2
    while f"{base}_{idx}" in existing:
        idx += 1
    return f"{base}_{idx}"


def _add_custom_section(
    *,
    settings: RulebookSettings,
    name: str,
    section_id: str,
    add_condition_type: str,
    add_condition_days: int,
    add_condition_include_missing: bool,
    add_priority: int,
    add_match_reason: str,
) -> None:
    """Create and persist a new custom section rule, then reload the form.

    Constructs a new rule with the specified condition and saves it to the
    rulebook. Sets a success flash message and triggers a Streamlit rerun.

    Args:
        settings: Current rulebook settings.
        name: Display name for the custom section.
        section_id: Section identifier.
        add_condition_type: "next_check_due" or "deadline_within_days";
            any other value is treated as delayed check-in.
        add_condition_days: Days parameter for deadline condition.
        add_condition_include_missing: Whether to include items with missing
            next check.
        add_priority: Rule priority (lower = checked first).
        add_match_reason: Optional explanation shown when items match this rule.
    """
    rule_id = _next_unique_custom_rule_id(settings, section_id)
    if add_condition_type == "next_check_due":
        conditions = (
            NextCheckDueCondition(include_missing_next_check=add_condition_include_missing),
        )
    elif add_condition_type == "deadline_within_days":
        conditions = (DeadlineWithinDaysCondition(days=add_condition_days),)
    else:
        conditions = (LatestCheckInTypeIsCondition(check_in_type=CheckInType.DELAYED),)
    new_rule = RuleDefinition(
        rule_id=rule_id,
        name=name,
        section_id=section_id,
        priority=add_priority,
        enabled=True,
        match_reason=add_match_reason,
        conditions=conditions,
    )
    new_settings = RulebookSettings(
        version=settings.version,
        rules=(*settings.rules, new_rule),
        first_match_wins=settings.first_match_wins,
        open_items_fallback_section=settings.open_items_fallback_section,
        concluded_section=settings.concluded_section,
    )
    save_rulebook_settings(new_settings)
    _clear_rulebook_widget_state()
    st.session_state["settings_rulebook_flash"] = (
        "Custom section added. Refresh the Now page to see it."
    )
    st.rerun()


def _collect_edited_rule(
    rule: RuleDefinition, rule_idx: int, edited_enabled: bool, edited_priority: int
) -> RuleDefinition:
    """Build a RuleDefinition with updated enabled, priority, and conditions from form state.

    Reads the current session state for condition widgets identified by rule_idx
    and condition index, then constructs a new RuleDefinition with the provided
    enabled and priority values while preserving rule identity and match_reason.

    Args:
        rule: The original rule definition to update.
        rule_idx: Index of the rule in the sorted rules list (for session key lookup).
        edited_enabled: Whether the rule is enabled in the form.
        edited_priority: Priority value from the form.

    Returns:
        A new RuleDefinition with updated enabled, priority, and conditions,
        preserving the original rule_id, name, section_id, and match_reason.
    """
    new_conditions: list[RuleCondition] = []
    for cond_idx, cond in enumerate(rule.conditions):
        key_prefix = f"settings_rule_{rule_idx}_cond_{cond_idx}"
        if isinstance(cond, DeadlineWithinDaysCondition):
            days = st.session_state.get(key_prefix + "_days", cond.days)
            days = max(0, min(DEADLINE_NEAR_DAYS_MAX, int(days)))
            new_conditions.append(DeadlineWithinDaysCondition(days=days))
        elif isinstance(cond, LatestCheckInTypeIsCondition):
            raw = st.session_state.get(key_prefix + "_check_in_type", cond.check_in_type.value)
            new_conditions.append(LatestCheckInTypeIsCondition(check_in_type=CheckInType(str(raw))))
        elif isinstance(cond, NextCheckDueCondition):
            include = st.session_state.get(
                key_prefix + "_include_missing", cond.include_missing_next_check
            )
            new_conditions.append(NextCheckDueCondition(include_missing_next_check=bool(include)))
    return RuleDefinition(
        rule_id=rule.rule_id,
        name=rule.name,
        section_id=rule.section_id,
        priority=edited_priority,
        enabled=edited_enabled,
        match_reason=rule.match_reason,
        conditions=tuple(new_conditions),
    )


def _render_rulebook_section() -> None:
    """Render an editable rulebook UI with save, reset, and conditions per rule.

    Displays all rules in expandable sections sorted by priority, allowing users
    to toggle enabled status, adjust priority, and edit condition parameters.
    Shows preview counts for each section. Provides Save and Reset buttons to
    persist or revert changes.
    """
    flash = st.session_state.pop("settings_rulebook_flash", None)
    if flash:
        st.success(flash)
    st.markdown("### Open-item rules")
    settings = get_rulebook_settings()
    preview_counts = get_rulebook_section_preview_counts(settings)
    section_labels = sorted({rule.section_id.replace("_", " ").title() for rule in settings.rules})
    sections_str = ", ".join(section_labels) if section_labels else "configured Now-page sections"
    fallback_label = settings.open_items_fallback_section.replace("_", " ").title()
    fallback_count = preview_counts.get(settings.open_items_fallback_section, 0)
    fallback_note = f" ({fallback_count} item{'s' if fallback_count != 1 else ''})"
    st.caption(
        f"Rules that group open handoffs into Now-page sections ({sections_str}). "
        f"First matching enabled rule wins. Unmatched items fall back to "
        f"{fallback_label}{fallback_note}."
    )

    ordered_rules = sorted(
        enumerate(settings.rules),
        key=lambda item: (item[1].priority, item[0]),
    )
    edited_rules: list[tuple[int, bool, int]] = []

    for rule_idx, rule in ordered_rules:
        count = preview_counts.get(rule.section_id, 0)
        count_suffix = f" · {count}"
        with st.expander(
            f"**{rule.name}** — {rule.section_id.replace('_', ' ').title()}{count_suffix}",
            expanded=False,
        ):
            enabled = st.checkbox(
                "Enabled",
                value=rule.enabled,
                key=f"settings_rule_{rule_idx}_enabled",
            )
            priority = st.number_input(
                "Priority (lower = checked first)",
                min_value=0,
                max_value=999,
                value=rule.priority,
                step=1,
                key=f"settings_rule_{rule_idx}_priority",
            )
            st.caption("Conditions (all must match):")
            for cond_idx, cond in enumerate(rule.conditions):
                key_prefix = f"settings_rule_{rule_idx}_cond_{cond_idx}"
                if isinstance(cond, DeadlineWithinDaysCondition):
                    st.number_input(
                        "Deadline within days",
                        min_value=0,
                        max_value=DEADLINE_NEAR_DAYS_MAX,
                        value=cond.days,
                        step=1,
                        key=key_prefix + "_days",
                    )
                elif isinstance(cond, LatestCheckInTypeIsCondition):
                    options = [
                        CheckInType.ON_TRACK.value,
                        CheckInType.DELAYED.value,
                    ]
                    try:
                        index = options.index(cond.check_in_type.value)
                    except ValueError:
                        index = 0
                        st.warning(
                            "A saved rule uses an unsupported check-in type. "
                            "Falling back to a default value.",
                            icon="⚠️",
                        )
                    st.selectbox(
                        "Latest check-in type",
                        options=options,
                        index=index,
                        key=key_prefix + "_check_in_type",
                    )
                elif isinstance(cond, NextCheckDueCondition):
                    st.checkbox(
                        "Include items with missing next check date",
                        value=cond.include_missing_next_check,
                        key=key_prefix + "_include_missing",
                    )
            if not is_built_in_rule(rule) and st.button(
                "Remove this section",
                key=f"settings_rule_{rule_idx}_remove",
            ):
                new_rules = [r for r in settings.rules if r.rule_id != rule.rule_id]
                if new_rules:
                    save_rulebook_settings(
                        RulebookSettings(
                            version=settings.version,
                            rules=tuple(new_rules),
                            first_match_wins=settings.first_match_wins,
                            open_items_fallback_section=settings.open_items_fallback_section,
                            concluded_section=settings.concluded_section,
                        )
                    )
                else:
                    reset_rulebook_settings()
                _clear_rulebook_widget_state()
                st.rerun()
        edited_rules.append((rule_idx, enabled, priority))

    # Add custom section form
    with (
        st.expander("Add custom section", expanded=False),
        st.form(key="settings_add_section_form"),
    ):
        add_name = st.text_input(
            "Section name",
            placeholder="e.g. Blocked",
            key="settings_add_section_name",
        )
        add_condition_type = st.selectbox(
            "Condition",
            options=[
                "next_check_due",
                "deadline_within_days",
                "latest_check_in_type_is",
            ],
            format_func=lambda x: {
                "next_check_due": "Next check due",
                "deadline_within_days": "Deadline within N days",
                "latest_check_in_type_is": "Latest check-in is delayed",
            }[x],
            key="settings_add_condition_type",
        )
        add_condition_days = st.number_input(
            "Days (for deadline)",
            min_value=0,
            max_value=DEADLINE_NEAR_DAYS_MAX,
            value=7,
            step=1,
            key="settings_add_condition_days",
        )
        add_condition_include_missing = st.checkbox(
            "Include items with missing next check",
            value=False,
            key="settings_add_condition_include_missing",
        )
        add_priority = st.number_input(
            "Priority (lower = checked first)",
            min_value=0,
            max_value=999,
            value=25,
            step=1,
            key="settings_add_priority",
        )
        add_match_reason = st.text_input(
            "Match reason (optional)",
            placeholder="e.g. Next check is due.",
            key="settings_add_match_reason",
        )
        if st.form_submit_button("Add section"):
            name = (add_name or "").strip()
            if not name:
                st.error("Section name is required.")
            else:
                section_id = _slugify_section_id(name)
                existing_ids = {r.section_id for r in settings.rules}
                if section_id in existing_ids:
                    st.error(
                        "A section with that name already exists. "
                        "Use a different name or remove the existing section first."
                    )
                else:
                    try:
                        _add_custom_section(
                            settings=settings,
                            name=name,
                            section_id=section_id,
                            add_condition_type=add_condition_type,
                            add_condition_days=int(add_condition_days),
                            add_condition_include_missing=add_condition_include_missing,
                            add_priority=int(add_priority),
                            add_match_reason=(add_match_reason or "").strip(),
                        )
                    except ValueError as exc:
                        st.error(f"Invalid configuration: {exc}")

    col1, col2 = st.columns(2)
    with col1:
        if st.button("Save changes", key="settings_rulebook_save"):
            try:
                edited_by_idx = {
                    rule_idx: (enabled, priority) for rule_idx, enabled, priority in edited_rules
                }
                new_rules_list: list[RuleDefinition] = []
                for rule_idx, rule in enumerate(settings.rules):
                    enabled, priority = edited_by_idx[rule_idx]
                    new_rule = _collect_edited_rule(rule, rule_idx, enabled, priority)
                    new_rules_list.append(new_rule)
                new_settings = RulebookSettings(
                    version=settings.version,
                    rules=tuple(new_rules_list),
                    first_match_wins=settings.first_match_wins,
                    open_items_fallback_section=settings.open_items_fallback_section,
                    concluded_section=settings.concluded_section,
                )
                save_rulebook_settings(new_settings)
                st.success("Rulebook saved. The Now page will use this from the next refresh.")
            except (ValueError, KeyError, TypeError) as exc:
                st.error(f"Invalid configuration: {exc}")

    with col2:
        if st.button("Reset to defaults", key="settings_rulebook_reset"):
            reset_rulebook_settings()
            _clear_rulebook_widget_state()
            st.success(
                "Rulebook reset to built-in defaults. "
                "The Now page will use this from the next refresh."
            )
            st.rerun()


def _render_data_export_section() -> None:
    """Render JSON and CSV export controls for projects and handoffs."""
    st.markdown("### Data export")
    st.caption(
        "Download a snapshot of your data. Exports are read-only and do not modify the "
        "underlying SQLite database."
    )

    payload: dict[str, Any] = get_export_payload()

    json_text = json.dumps(payload, indent=2)
    st.download_button(
        "Download JSON backup",
        data=json_text,
        file_name="todo_backup.json",
        mime="application/json",
        key="settings_download_json_backup",
    )

    st.download_button(
        "Download CSV (handoffs)",
        data=_handoffs_csv_text(payload),
        file_name="handoff_handoffs.csv",
        mime="text/csv",
        key="settings_download_csv_backup",
    )


def _render_send_log_section() -> None:
    """Render a download button that zips all log files for easy sharing."""
    st.markdown("### Send log")
    st.caption(
        "Download a zip of all log files. Attach this when reporting an issue — "
        "you don't need to find the log folder yourself."
    )

    logs_dir = _get_logs_dir()
    log_files = sorted(logs_dir.iterdir()) if logs_dir.exists() else []
    log_files = [f for f in log_files if f.is_file()]

    if not log_files:
        st.caption("No log files found.")
        return

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        for log_file in log_files:
            zf.write(log_file, arcname=log_file.name)
    buf.seek(0)

    timestamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    st.download_button(
        "Download log zip",
        data=buf.getvalue(),
        file_name=f"handoff-logs-{timestamp}.zip",
        mime="application/zip",
        key="settings_download_logs",
    )


def _render_data_import_section() -> None:
    """Render JSON import controls for restoring data from a backup."""
    st.markdown("### Data import")
    st.caption(
        "Restore from a JSON backup. **This will overwrite all existing data** "
        "(projects and todos)."
    )

    uploaded = st.file_uploader(
        "Upload a .json backup file",
        type=["json"],
        key="settings_import_file",
    )
    if uploaded is None:
        return

    try:
        raw_text = uploaded.getvalue().decode("utf-8")
        payload = BackupPayload.from_dict(json.loads(raw_text))
    except UnicodeDecodeError:
        st.error("Could not read the file as UTF-8 text. Please upload a JSON backup.")
        return
    except json.JSONDecodeError:
        st.error("Invalid JSON file. Please upload a Handoff JSON backup.")
        return
    except (KeyError, ValueError) as exc:
        logger.warning("Invalid backup upload: {}", exc)
        st.error(
            "Invalid backup file. Expected a Handoff backup with 'projects' and 'handoffs' lists."
        )
        return

    st.info(
        f"File contains **{len(payload.projects)}** projects and "
        f"**{len(payload.handoffs)}** handoffs."
    )

    confirm = st.checkbox(
        "I understand this will replace all existing projects and handoffs.",
        key="settings_import_confirm",
    )
    if confirm and st.button("Import and overwrite", key="settings_import_apply"):
        try:
            import_payload(payload.to_dict())
            st.success("Import complete — all data has been replaced.")
        except Exception as exc:
            st.error(f"Import failed: {exc}")


def _render_about_section() -> None:
    """Render a compact About section at the end of the System Settings page."""
    st.markdown("### About Handoff")
    st.caption(f"Version: {APP_VERSION}")

    st.write(get_readme_intro())

    system = platform.system()
    release = platform.release()
    python_version = platform.python_version()
    st.caption(f"Environment: Python {python_version} on {system} {release}")

    st.caption(
        "For a fuller overview and a detailed changelog, open the in-app README and Release "
        "notes pages from the navigation bar."
    )


def render_system_settings_page() -> None:
    """Render the System Settings page with update, backup, and about sections."""
    st.subheader("System Settings")
    st.write(
        "Use this page to apply code updates, restore backups created by updates, export "
        "or import your data, and download logs. An About section at the end summarises "
        "the app and environment."
    )

    # App updates and code backups (panel from handoff.updater).
    render_update_panel(APP_VERSION)

    st.divider()
    _render_rulebook_section()

    st.divider()
    _render_data_export_section()

    st.divider()
    _render_data_import_section()

    st.divider()
    _render_send_log_section()

    st.divider()
    _render_about_section()
