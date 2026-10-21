"""Notifications — view notification history."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import empty_state, error_state, simulated_badge
from frontend.styles import GLOBAL_CSS


def render() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.header("🔔 Notifications")
    st.caption("Notification history for all channels.")

    try:
        notifications = api_client.get_notifications(limit=100)
    except Exception as exc:
        error_state(str(exc))
        return

    if not notifications:
        empty_state("No Notifications", "Notifications will appear here as incidents are raised.")
        return

    st.subheader("Simulated Alexa deterrent")
    st.markdown(simulated_badge(), unsafe_allow_html=True)
    deterrents = [item for item in notifications if item.get("channel") == "deterrent"]
    if deterrents:
        for item in deterrents:
            st.info(item.get("message") or "Simulated Alexa: 'This package is being monitored.'")
    else:
        st.caption("A Simulated Alexa line appears when an incident is opened.")

    st.subheader("History")
    for n in notifications:
        channel = n.get("channel", "dashboard")
        message = n.get("message", "")
        is_sim = n.get("simulated", True)
        created = n.get("created_at", "")

        sim_tag = simulated_badge() if is_sim else ""
        channel_emoji = {"dashboard": "📊", "telegram": "📱", "deterrent": "🔊"}.get(channel, "📬")

        st.markdown(
            f"""
            <div class="event-item">
                <strong>{channel_emoji} {channel.upper()}</strong> {sim_tag}
                <span style="float:right;color:#A0AEC0;font-size:0.8em;">{created[:19] if created else ""}</span>
                <br><span style="color:#E2E8F0;">{message}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


render()
