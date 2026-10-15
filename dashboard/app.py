"""
dashboard/app.py

Streamlit dashboard for the threat detection system.
Run from the repo root (with the API already running):
    streamlit run dashboard/app.py
"""

from datetime import datetime

import streamlit as st

import api_client
from components import threat_panel, reliability_panel

st.set_page_config(page_title="Cloud Threat Detection", layout="wide")

st.title("Autonomous Threat Detection and Mitigation")

# ---------------------------------------------------------------- sidebar
with st.sidebar:
    st.header("Settings")
    api_url = st.text_input("API URL", value="http://127.0.0.1:8000")
    refresh_s = st.slider("Refresh every (seconds)", min_value=2, max_value=30, value=5)
    paused = st.toggle("Pause auto-refresh", value=False)
    event_limit = st.slider("Events to load", min_value=20, max_value=500, value=200, step=20)
    st.caption("The dashboard only reads from the API. Start traffic with "
               "`python -m src.orchestrator` or POST /respond.")


# ------------------------------------------------------- refreshing body
def render_dashboard():
    health, health_err = api_client.get_health(api_url)
    metrics, metrics_err = api_client.get_metrics(api_url)
    events, events_err = api_client.get_events(api_url, event_limit)

    if health_err or metrics_err or events_err:
        st.error(f"Cannot reach the API at {api_url}. Start it with "
                 "`uvicorn src.api.main:app --reload`.")
        st.caption(health_err or metrics_err or events_err)
        return

    k1, k2, k3, k4 = st.columns(4)
    k1.metric("Total events", metrics["total_events"])
    k2.metric("Detected threats", metrics["detected_threats"])
    k3.metric("Mitigated incidents", metrics["mitigated_incidents"])
    k4.metric("Service status", health["status"].upper(),
              help="Model loaded" if health["model_loaded"] else "Model NOT loaded")

    if metrics["total_events"] == 0:
        st.info("No events yet. Run `python -m src.orchestrator` or send a sample to POST /respond.")

    threat_panel.render(events, metrics)
    reliability_panel.render(metrics)
    st.caption(f"Last refreshed {datetime.now().strftime('%H:%M:%S')}")


# st.fragment(run_every=...) re-runs only this section on a timer
run_every = None if paused else f"{refresh_s}s"
live = st.fragment(run_every=run_every)(render_dashboard)
live()
