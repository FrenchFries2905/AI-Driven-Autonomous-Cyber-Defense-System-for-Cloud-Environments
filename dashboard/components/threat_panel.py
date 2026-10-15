"""
dashboard/components/threat_panel.py

Panel showing detected threats: counts by class, model confidence over
time, and the log of mitigation actions taken.
"""

import pandas as pd
import streamlit as st

LOG_ROWS = 50  # how many recent events to show in the table


def events_to_frame(events: list) -> pd.DataFrame:
    df = pd.DataFrame(events)
    if df.empty:
        return df
    df["timestamp_utc"] = pd.to_datetime(df["timestamp_utc"])
    return df


def render(events: list, metrics: dict) -> None:
    df = events_to_frame(events)

    left, right = st.columns(2)

    with left:
        st.subheader("Events by class")
        counts = metrics.get("events_by_class", {})
        if counts:
            chart_df = pd.DataFrame({"events": counts}).sort_values("events", ascending=False)
            st.bar_chart(chart_df)
        else:
            st.caption("No events yet.")

    with right:
        st.subheader("Model confidence per event")
        if not df.empty:
            conf = df.sort_values("id").set_index("id")["confidence"]
            st.line_chart(conf)
        else:
            st.caption("No events yet.")

    st.subheader("Mitigation actions log")
    if df.empty:
        st.caption("No events yet.")
        return

    table = pd.DataFrame({
        "Time (UTC)": df["timestamp_utc"].dt.strftime("%H:%M:%S"),
        "Source IP": df["source_ip"],
        "Class": df["predicted_class"],
        "Confidence": df["confidence"].round(2),
        "Risk": df["risk_level"],
        "Action": df["action"],
        "Target": df["target"],
        "Result": df["success"].map({1: "OK", 0: "FAILED"}),
        "MTTR (ms)": df["mttr_ms"].round(1),
        "Reasoning": df["reasoning"],
    }).head(LOG_ROWS)
    st.dataframe(table, hide_index=True)
