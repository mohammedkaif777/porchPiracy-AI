"""Incidents — list, detail, review and dismiss incidents."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import (
    empty_state,
    error_state,
    severity_badge,
    status_badge,
)
from frontend.styles import GLOBAL_CSS


def render() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.header("🚨 Incidents")

    try:
        incidents = api_client.get_incidents(limit=50)
    except Exception as exc:
        error_state(str(exc))
        return

    if not incidents:
        empty_state("No Incidents", "The system has not raised any incidents yet.")
        return

    for inc in incidents:
        sev = inc.get("severity", "LOW")
        status = inc.get("status", "OPEN")
        reasons = ", ".join(inc.get("reason_codes", []))
        incident_id = inc.get("incident_id", "")

        with st.expander(
            f"{severity_badge(sev)} {reasons} — {inc.get('start_s', 0):.1f}s",
            expanded=False,
        ):
            st.markdown(
                f"**ID:** `{incident_id[:12]}…`<br>"
                f"**Severity:** {severity_badge(sev)}<br>"
                f"**Status:** {status_badge(status)}<br>"
                f"**Time:** {inc.get('start_s', 0):.1f}s – {inc.get('end_s', 0):.1f}s<br>"
                f"**Reasons:** {reasons}",
                unsafe_allow_html=True,
            )

            if inc.get("explanation"):
                st.info(f"💡 {inc['explanation']}")

            # Review buttons.
            col1, col2 = st.columns(2)
            with col1:
                if st.button("✅ Review", key=f"review-{incident_id}"):
                    try:
                        api_client.review_incident(incident_id, "REVIEWED")
                        st.success("Marked as REVIEWED")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))
            with col2:
                if st.button("❌ Dismiss", key=f"dismiss-{incident_id}"):
                    try:
                        api_client.review_incident(incident_id, "DISMISSED")
                        st.success("Marked as DISMISSED")
                        st.rerun()
                    except Exception as exc:
                        st.error(str(exc))


render()
