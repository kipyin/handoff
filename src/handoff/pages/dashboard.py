"""Dashboard page — at-a-glance pulse check for the Handoff app."""

from __future__ import annotations

from datetime import date

import streamlit as st

from handoff.services.dashboard_service import (
    get_cycle_time_by_project,
    get_dashboard_metrics,
    get_exportable_metrics,
    get_on_time_close_rate_trend,
    get_open_aging_profile,
    get_recent_activity,
)


def render_dashboard_page() -> None:
    """Render PM-operational dashboard metrics and reliability/flow views."""
    st.subheader("Dashboard")

    today = date.today()
    metrics = get_dashboard_metrics(today)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("At risk now", metrics.at_risk_now)
    with col2:
        st.metric(
            "Missed check-in",
            metrics.action_overdue,
            delta=f"{metrics.action_due_today} due today",
        )
    with col3:
        st.metric("Open handoffs", metrics.open_handoffs)
    with col4:
        st.metric(
            "Reopen rate (90d)",
            metrics.reopen_rate,
            delta=metrics.reopen_rate_detail,
        )

    st.caption(
        "Risk uses the System Settings deadline-near window. "
        "Missed check-in means the scheduled check date has passed."
    )

    st.markdown("---")
    st.markdown("#### Reliability")

    on_time_trend = get_on_time_close_rate_trend(today, weeks=8)
    if on_time_trend.empty:
        st.info("No closed handoffs with deadlines in the last 8 weeks.")
    else:
        st.markdown("On-time close rate trend (weekly)")
        st.line_chart(on_time_trend.set_index("week_label")[["on_time_rate"]])
        st.dataframe(
            on_time_trend[["week_label", "on_time_rate_pct", "total"]],
            use_container_width=True,
            hide_index=True,
        )

    st.markdown("#### Flow")
    aging = get_open_aging_profile(today)
    if aging.empty:
        st.caption("No open handoffs for aging analysis.")
    else:
        st.markdown("Open aging profile")
        st.bar_chart(aging.set_index("aging_bucket")[["handoffs"]])

    cycle_by_project = get_cycle_time_by_project(today, days=90)
    if cycle_by_project.empty:
        st.caption("No closed handoffs in the last 90 days for cycle-time analysis.")
    else:
        st.markdown("Cycle time by project (p50/p90, last 90 days)")
        st.dataframe(cycle_by_project, use_container_width=True, hide_index=True)

    st.markdown("---")
    st.markdown("#### Recent activity")
    activity = get_recent_activity(limit=15)
    if activity:
        for entry in activity:
            ts = entry.get("timestamp", "")
            entity = entry.get("entity_type", "?")
            ent_id = entry.get("entity_id", "")
            action = entry.get("action", "?")
            details = entry.get("details") or {}
            name = details.get("name", f"#{ent_id}") if isinstance(details, dict) else str(ent_id)
            st.caption(f"{ts} — {entity} {name}: {action}")
    else:
        st.caption("No recent activity.")

    st.markdown("---")
    st.markdown("#### Export metrics")
    export_data = get_exportable_metrics(today, weeks=12)
    if export_data.get("csv"):
        col_csv, col_json = st.columns(2)
        with col_csv:
            st.download_button(
                "Download CSV",
                data=export_data["csv"],
                file_name="handoff_metrics.csv",
                mime="text/csv",
                key="dashboard_export_csv",
            )
        with col_json:
            st.download_button(
                "Download JSON",
                data=export_data["json"],
                file_name="handoff_metrics.json",
                mime="application/json",
                key="dashboard_export_json",
            )
    else:
        st.caption("No concluded handoffs in the last 12 weeks to export.")
