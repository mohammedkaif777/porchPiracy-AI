"""Home dashboard page for porchPiracyAI."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import (
    empty_state,
    error_state,
    event_feed,
    severity_badge,
    simulated_badge,
    status_card,
    threat_badge,
)
from frontend.styles import DANGER, GLOBAL_CSS, PRIMARY, SUCCESS, WARNING


def render() -> None:
    """Render the home dashboard."""
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.markdown(
        '<h1 style="text-align:center;">🛡️ <span style="color:#6C63FF;">porch</span>'
        '<span style="color:#FF6584;">Piracy</span>AI</h1>',
        unsafe_allow_html=True,
    )
    st.markdown(
        '<p style="text-align:center;color:#A0AEC0;">'
        "AI-powered porch piracy detection and prevention</p>",
        unsafe_allow_html=True,
    )
    st.divider()

    try:
        health = api_client.get_health()
        protection = api_client.get_protection_status()
        incidents = api_client.get_incidents(limit=10)
        events = api_client.get_events(limit=20)
        notifications = api_client.get_notifications(limit=5)
    except Exception as exc:
        error_state(f"Cannot connect to the backend: {exc}")
        return

    # --- Status cards ---
    col1, col2, col3, col4 = st.columns(4)
    with col1:
        state = protection.get("state", "IDLE")
        color = SUCCESS if state == "IDLE" else (WARNING if "ACTIVE" in state else DANGER)
        status_card("Protection", state, color)
    with col2:
        threat = protection.get("threat_level", "NONE")
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Threat Level</div>'
            f'<div style="padding:8px 0;">{threat_badge(threat)}</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        status_card("Incidents", len(incidents), DANGER if incidents else SUCCESS)
    with col4:
        status_card("Notifications", len(notifications), PRIMARY)

    st.divider()

    # --- Recent events and incidents ---
    left, right = st.columns([3, 2])
    with left:
        st.subheader("📡 Recent Events")
        event_feed(events)
    with right:
        st.subheader("🚨 Recent Incidents")
        if incidents:
            for inc in incidents[:5]:
                sev = inc.get("severity", "LOW")
                st.markdown(
                    f'<div class="event-item">'
                    f'{severity_badge(sev)} '
                    f'<strong>{", ".join(inc.get("reason_codes", []))}</strong>'
                    f'<br><span style="color:#A0AEC0;font-size:0.85em;">'
                    f'{inc.get("start_s", 0):.1f}s – {inc.get("end_s", 0):.1f}s</span>'
                    f"</div>",
                    unsafe_allow_html=True,
                )
        else:
            empty_state("All Clear", "No incidents have been raised.")


render()
