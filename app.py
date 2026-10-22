"""porchPiracyAI — Streamlit entry point."""

from __future__ import annotations

import streamlit as st

st.set_page_config(
    page_title="porchPiracyAI",
    page_icon="🛡️",
    layout="wide",
    initial_sidebar_state="expanded",
)

pages = [
    st.Page("frontend/dashboard.py", title="Dashboard", icon="🛡️", default=True),
    st.Page("frontend/pages/1_Live_Monitor.py", title="Live Monitor", icon="📹"),
    st.Page("frontend/pages/2_Protection.py", title="Protection", icon="🔒"),
    st.Page("frontend/pages/3_Incidents.py", title="Incidents", icon="🚨"),
    st.Page("frontend/pages/4_Settings.py", title="Settings", icon="⚙️"),
    st.Page("frontend/pages/5_Notifications.py", title="Notifications", icon="🔔"),
]

nav = st.navigation(pages)
nav.run()
