"""Reusable Streamlit UI components."""

from __future__ import annotations

import streamlit as st

from frontend.styles import (
    SEVERITY_COLORS,
    STATUS_COLORS,
    THREAT_COLORS,
)


def status_card(label: str, value: str | int, color: str | None = None) -> None:
    """Render a styled metric card."""
    c = color or "#6C63FF"
    st.markdown(
        f"""
        <div class="metric-card">
            <div class="metric-label">{label}</div>
            <div class="metric-value" style="color:{c}">{value}</div>
        </div>
        """,
        unsafe_allow_html=True,
    )


def threat_badge(level: str) -> str:
    """Return an HTML badge for a threat level."""
    color = THREAT_COLORS.get(level, "#A0AEC0")
    return f'<span class="badge" style="background:rgba({_hex_to_rgb(color)},0.15);color:{color};">{level}</span>'


def severity_badge(severity: str) -> str:
    """Return an HTML badge for a severity."""
    css_class = f"badge-{severity.lower()}"
    return f'<span class="badge {css_class}">{severity}</span>'


def status_badge(status: str) -> str:
    """Return an HTML badge for an incident status."""
    color = STATUS_COLORS.get(status, "#A0AEC0")
    return f'<span class="badge" style="background:rgba({_hex_to_rgb(color)},0.15);color:{color};">{status}</span>'


def simulated_badge() -> str:
    """Return a small 'Simulated' badge."""
    return '<span class="badge-simulated">Simulated</span>'


def event_feed(events: list[dict], max_items: int = 20) -> None:
    """Render a vertical event feed."""
    if not events:
        empty_state("No events yet", "Events will appear here as they are detected.")
        return
    for event in events[:max_items]:
        event_type = event.get("type", "UNKNOWN")
        ts = event.get("timestamp_s", 0)
        confidence = event.get("confidence", 0)
        st.markdown(
            f"""
            <div class="event-item">
                <strong>{event_type}</strong>
                <span style="float:right;color:#A0AEC0;font-size:0.85em;">{ts:.1f}s</span>
                <br><span style="color:#A0AEC0;font-size:0.85em;">
                Confidence: {confidence:.0%}</span>
            </div>
            """,
            unsafe_allow_html=True,
        )


def timeline(events: list[dict]) -> None:
    """Render a simple timeline chart of events."""
    if not events:
        return
    import pandas as pd

    df = pd.DataFrame(events)
    if "timestamp_s" in df.columns and "type" in df.columns:
        chart_data = df[["timestamp_s", "type"]].copy()
        chart_data["count"] = 1
        st.bar_chart(chart_data.set_index("timestamp_s")["count"])


def empty_state(title: str, message: str) -> None:
    """Render a friendly empty state."""
    st.markdown(
        f"""
        <div style="text-align:center;padding:40px 20px;color:#A0AEC0;">
            <div style="font-size:3em;margin-bottom:10px;">📦</div>
            <h3 style="color:#E2E8F0;margin-bottom:8px;">{title}</h3>
            <p>{message}</p>
        </div>
        """,
        unsafe_allow_html=True,
    )


def error_state(message: str) -> None:
    """Render an error state with a retry hint."""
    st.error(f"⚠️ {message}")
    st.caption("Check that the backend is running on http://localhost:8000")


def _hex_to_rgb(hex_color: str) -> str:
    """Convert '#RRGGBB' to 'R, G, B'."""
    h = hex_color.lstrip("#")
    return f"{int(h[0:2], 16)}, {int(h[2:4], 16)}, {int(h[4:6], 16)}"
