"""Protection — start/end sessions, view status."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import error_state, simulated_badge, status_card, threat_badge
from frontend.styles import DANGER, GLOBAL_CSS, SUCCESS, WARNING


def render() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.header("🛡️ Protection Session")

    try:
        status = api_client.get_protection_status()
    except Exception as exc:
        error_state(str(exc))
        return

    state = status.get("state", "IDLE")
    threat = status.get("threat_level", "NONE")
    source = status.get("source", "—")
    remaining = status.get("seconds_remaining")

    col1, col2, col3 = st.columns(3)
    with col1:
        color = SUCCESS if state == "IDLE" else (WARNING if "ACTIVE" in state else DANGER)
        status_card("State", state, color)
    with col2:
        st.markdown(
            f'<div class="metric-card"><div class="metric-label">Threat Level</div>'
            f'<div style="padding:8px 0;">{threat_badge(threat)}</div></div>',
            unsafe_allow_html=True,
        )
    with col3:
        if remaining is not None:
            mins = remaining // 60
            secs = remaining % 60
            status_card("Time Remaining", f"{mins}m {secs}s")
        else:
            status_card("Source", source or "—")
    if source == "SIMULATED_DELIVERY":
        st.markdown(simulated_badge(), unsafe_allow_html=True)
    st.caption("Protection state and incident state are independent.")

    st.divider()

    # --- Controls ---
    col_a, col_b, col_c = st.columns(3)
    with col_a:
        if st.button("🟢 Start Manual Protection", use_container_width=True):
            try:
                result = api_client.start_protection()
                st.success(f"Protection started: {result.get('state')}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with col_b:
        if st.button("📦 Simulate Delivery", use_container_width=True):
            try:
                result = api_client.simulate_delivery()
                st.success(f"Delivery simulated: {result.get('state')}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))
    with col_c:
        if st.button("🔴 End Protection", use_container_width=True):
            try:
                result = api_client.end_protection()
                st.success(f"Protection ended: {result.get('state')}")
                st.rerun()
            except Exception as exc:
                st.error(str(exc))


render()
