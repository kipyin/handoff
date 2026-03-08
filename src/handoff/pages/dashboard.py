"""Dashboard page — at-a-glance pulse check for the Handoff app."""

from __future__ import annotations

from datetime import date

import streamlit as st

from handoff.services.dashboard_service import (
    get_cycle_time_by_project,
    get_dashboard_metrics,
    get_deadline_adherence_trend,
    get_exportable_metrics,
    get_helper_load,
    get_per_helper_throughput,
    get_per_project_throughput,
    get_weekly_throughput,
)


def render_dashboard_page() -> None:
    """Render a compact dashboard with key metrics and charts."""
    st.subheader("Dashboard")

    today = date.today()
    metrics = get_dashboard_metrics(today)

    col1, col2, col3, col4 = st.columns(4)
    with col1:
        st.metric("Open handoffs", metrics.open_count)
    with col2:
        st.metric("Done this week", metrics.done_this_week, delta=metrics.done_week_delta)
    with col3:
        st.metric("Median cycle time", metrics.median_cycle_time)
    with col4:
        st.metric("On-time rate", metrics.on_time_rate)

    st.caption("Cycle time and on-time rate are based on the last 28 days.")

    st.markdown("---")

    # Weekly throughput (last 8 weeks)
    weekly = get_weekly_throughput(today, weeks=8)
    if not weekly.empty:
        st.markdown("#### Completed per week (last 8 weeks)")
        st.bar_chart(weekly.set_index("week_label"))
    else:
        st.info("No completed todos in the last 8 weeks.")

    # Per-project throughput (A6)
    project_throughput = get_per_project_throughput(today, weeks=8)
    if not project_throughput.empty:
        st.markdown("#### Per-project throughput (last 8 weeks)")
        st.dataframe(project_throughput, use_container_width=True, hide_index=True)

    # Per-helper throughput (A6)
    helper_throughput = get_per_helper_throughput(today, weeks=8)
    if not helper_throughput.empty:
        st.markdown("#### Per-helper throughput (last 8 weeks)")
        chart_df = helper_throughput[["helper", "completed"]].set_index("helper")
        st.bar_chart(chart_df)

    # Cycle time by project (A6)
    cycle_by_project = get_cycle_time_by_project(today, days=28)
    if not cycle_by_project.empty:
        st.markdown("#### Cycle time by project (last 28 days)")
        st.dataframe(cycle_by_project, use_container_width=True, hide_index=True)

    # Deadline adherence trend (A6)
    adherence_trend = get_deadline_adherence_trend(today, weeks=8)
    if not adherence_trend.empty:
        st.markdown("#### Deadline adherence trend (on-time rate per week)")
        st.line_chart(adherence_trend.set_index("week_label"))

    # Current helper load
    helper_load = get_helper_load()
    if not helper_load.empty:
        st.markdown("#### Current helper load")
        st.bar_chart(helper_load.set_index("helper"))

    # Export metrics (A6)
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
        st.caption("No completed todos in the last 12 weeks to export.")
