"""Settings — view and update tunable thresholds."""

from __future__ import annotations

import streamlit as st

from frontend import api_client
from frontend.components import error_state
from frontend.styles import GLOBAL_CSS


def render() -> None:
    st.markdown(GLOBAL_CSS, unsafe_allow_html=True)
    st.header("⚙️ Settings")
    st.caption("Adjust detection thresholds and system configuration.")

    try:
        current = api_client.get_settings()
    except Exception as exc:
        error_state(str(exc))
        return

    with st.form("settings_form"):
        st.subheader("Protection & Detection")
        protection_timeout = st.number_input(
            "Protection timeout (minutes)",
            min_value=1,
            max_value=10080,
            value=current.get("protection_timeout_minutes", 360),
        )
        loiter_threshold = st.number_input(
            "Loiter threshold (seconds)",
            min_value=0.5,
            max_value=3600.0,
            value=float(current.get("loiter_threshold_seconds", 8.0)),
            step=0.5,
        )
        near_distance = st.number_input(
            "Near-package distance (px)",
            min_value=1.0,
            max_value=5000.0,
            value=float(current.get("near_package_distance_px", 150.0)),
        )
        frame_stride = st.number_input(
            "Frame stride",
            min_value=1,
            max_value=30,
            value=current.get("frame_stride", 2),
        )
        detection_conf = st.slider(
            "Detection confidence threshold",
            min_value=0.01,
            max_value=0.99,
            value=float(current.get("detection_conf_threshold", 0.45)),
            step=0.01,
        )
        cooldown = st.number_input(
            "Incident cooldown (seconds)",
            min_value=0.0,
            max_value=3600.0,
            value=float(current.get("incident_cooldown_seconds", 30.0)),
        )

        st.divider()
        st.subheader("System Info (read-only)")
        st.text(f"Ring mode: {current.get('ring_mode', 'local')}")
        st.text(f"LLM enabled: {current.get('llm_enabled', False)}")

        submitted = st.form_submit_button("💾 Save Settings", use_container_width=True)
        if submitted:
            try:
                api_client.update_settings(
                    {
                        "protection_timeout_minutes": int(protection_timeout),
                        "loiter_threshold_seconds": loiter_threshold,
                        "near_package_distance_px": near_distance,
                        "frame_stride": int(frame_stride),
                        "detection_conf_threshold": detection_conf,
                        "incident_cooldown_seconds": cooldown,
                    }
                )
                st.success("✅ Settings updated successfully!")
            except Exception as exc:
                st.error(str(exc))


render()
